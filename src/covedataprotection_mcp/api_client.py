import asyncio
from typing import Any

import httpx

from ._json import error_envelope

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_MAX_BACKOFF_SECONDS = 20.0

# One shared connection pool for the process lifetime. No credentials are
# ever stored on it: partner/username/password are passed per-call and used
# only to perform a fresh Login for that call (see CoveClient.call below),
# so sharing this pool across tenants/requests is safe — it carries no
# tenant-identifying state (see server.py's contextvar-based credential
# isolation, which is what actually keeps tenants apart).
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _http_client


# status_code -> (error code, retryable). status_code 0 means a network/
# connection-level failure (no response at all).
_STATUS_TO_CODE: dict[int, tuple[str, bool]] = {
    0: ("upstream_error", True),
    400: ("invalid_argument", False),
    401: ("unauthorized", False),
    403: ("unauthorized", False),
    404: ("not_found", False),
    422: ("invalid_argument", False),
    429: ("rate_limited", True),
}


def _classify(status_code: int) -> tuple[str, bool]:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "upstream_error", True
    return "invalid_argument", False


class CoveError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Cove Data Protection API error {status_code}: {message}")

    def to_envelope(self) -> str:
        code, retryable = _classify(self.status_code)
        return error_envelope(code, self.message, retryable)


class CoveClient:
    """Async httpx client wrapping the Cove Data Protection (N-able Backup
    Manager) JSON-RPC Management Service API.

    Unlike a static API key, this API requires an explicit Login exchange
    (partner/username/password) that returns a short-lived "visa" session
    token (valid ~15 minutes). Rather than caching a visa across requests —
    which would mean persisting cross-request state derived from a tenant's
    credentials — this client logs in fresh on every call() and discards the
    visa afterward, trading one extra HTTP round trip per call for full
    statelessness. The visa is never written to any module-level or global
    store, so concurrent requests from different tenants never observe each
    other's session.

    Reuses the module-level shared connection pool (see _get_http_client)
    across every request made through this instance, rather than opening a
    new connection per request.
    """

    def __init__(self, partner: str, username: str, password: str, base_url: str):
        self._partner = partner
        self._username = username
        self._password = password
        self._base_url = base_url

    async def call(self, method: str, params: dict | None = None) -> Any:
        visa = await self._login()
        return await self._invoke(method, params, visa)

    async def _login(self) -> str:
        body = {
            "jsonrpc": "2.0",
            "id": "login",
            "method": "Login",
            "params": {
                "partner": self._partner,
                "username": self._username,
                "password": self._password,
            },
        }
        try:
            data = await self._post(body)
        except CoveError as e:
            # Cove rejects bad credentials with HTTP 200 + a JSON-RPC error (e.g. data 2100),
            # which _raise_for_error files under 400. On Login that is a credential problem,
            # so report it as unauthorized; network (0) / 5xx / 429 keep their own codes.
            if e.status_code in (400, 422):
                raise CoveError(401, e.message) from e
            raise
        visa = data.get("visa")
        if not visa:
            raise CoveError(401, "Login succeeded but no visa was returned")
        return visa

    async def _invoke(self, method: str, params: dict | None, visa: str) -> Any:
        body = {
            "jsonrpc": "2.0",
            "visa": visa,
            "id": "jsonrpc",
            "method": method,
            "params": params or {},
        }
        data = await self._post(body)
        return data.get("result")

    async def _post(self, body: dict) -> dict:
        client = _get_http_client()

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.post(self._base_url, json=body)
            except httpx.RequestError as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))
                    continue
                raise CoveError(0, f"{e or type(e).__name__} (url={self._base_url})") from e

            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                delay = self._retry_delay(resp, attempt)
                await asyncio.sleep(delay)
                continue

            data = self._parse_body(resp)
            self._raise_for_error(resp, data)
            return data

        # Unreachable in practice (loop always returns or raises above), but
        # keeps type checkers happy and guards against future edits.
        if last_exc:
            raise CoveError(0, f"{last_exc}") from last_exc
        raise CoveError(0, "request failed with no response")

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                pass
        return min(2**attempt, _MAX_BACKOFF_SECONDS)

    def _parse_body(self, resp: httpx.Response) -> dict:
        if not resp.content:
            return {}
        try:
            parsed = resp.json()
            return parsed if isinstance(parsed, dict) else {"raw_response": parsed}
        except ValueError:
            return {"raw_response": resp.text}

    def _raise_for_error(self, resp: httpx.Response, data: dict) -> None:
        if "error" in data:
            err = data["error"]
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code") or str(err)
            else:
                msg = str(err)
            raise CoveError(resp.status_code if resp.status_code >= 400 else 400, msg)
        if resp.status_code >= 400:
            raise CoveError(resp.status_code, data.get("raw_response") or resp.text)
