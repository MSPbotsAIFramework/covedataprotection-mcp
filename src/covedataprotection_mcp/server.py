import contextvars
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import CoveClient
from .config import Settings

# Per-request credential isolation via contextvars.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent SSE connections are isolated.
# Value is (partner, username, password) — Cove has no static API key; every
# call re-authenticates via Login (see api_client.CoveClient).
_gateway_creds_var: contextvars.ContextVar[tuple[str, str, str] | None] = contextvars.ContextVar(
    "cove_gateway_creds", default=None
)


def get_client_from_context(settings: Settings) -> CoveClient | None:
    """Resolve the active CoveClient for the current request context."""
    creds = _gateway_creds_var.get()
    if not creds:
        return None
    partner, username, password = creds
    return CoveClient(partner, username, password, settings.covedataprotection_base_url)


class GatewayTokenMiddleware:
    """ASGI middleware.

    Reads X-CoveDataProtection-Partner, X-CoveDataProtection-Username, and
    X-CoveDataProtection-Password (all required) from request headers and
    stores them in the contextvar. Returns 401 if any is missing on /mcp
    requests.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        partner = request.headers.get("x-covedataprotection-partner")
        username = request.headers.get("x-covedataprotection-username")
        password = request.headers.get("x-covedataprotection-password")
        if not partner or not username or not password:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": (
                        "This server requires the X-CoveDataProtection-Partner, "
                        "X-CoveDataProtection-Username, and "
                        "X-CoveDataProtection-Password headers"
                    ),
                    "required_headers": [
                        "X-CoveDataProtection-Partner",
                        "X-CoveDataProtection-Username",
                        "X-CoveDataProtection-Password",
                    ],
                    "optional_headers": [],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set((partner, username, password))
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all Cove Data Protection tools."""
    # DNS-rebinding protection is a browser-oriented safeguard that rejects
    # non-localhost Host headers with 421. Disable it so the server works
    # correctly behind a reverse proxy or docker network.
    mcp = FastMCP(
        name="covedataprotection-mcp",
        instructions=(
            "Cove Data Protection (N-able's MSP backup/BDR platform, formerly "
            "N-able Backup) organizes data hierarchically: partners (MSP/customer "
            "tenants, which can nest child partners) each own accounts (backup "
            "devices/endpoints) and users (portal logins). Use this server for "
            "MSP backup-fleet questions: which customers/partners exist and how "
            "they nest (covedataprotection_enumerate_partners, "
            "_enumerate_child_partners, _get_partner_tree), which backup devices "
            "a partner has and their backup stats (covedataprotection_"
            "enumerate_accounts, _enumerate_account_statistics), which features "
            "are enabled on a device (_get_account_features), and who has portal "
            "access (covedataprotection_enumerate_users, _enumerate_user_roles). "
            "Typical flow: enumerate_partners to find a partner_id, then "
            "enumerate_accounts(partner_id=...) or enumerate_users(partner_ids=...) "
            "to see its devices/users, then a get_*_info_by_id / "
            "enumerate_account_statistics tool for details. Write tools "
            "(add/modify/remove/set_*) create, update, or delete real partners, "
            "accounts, or users in production — use only on an explicit request "
            "naming the exact resource, never as a guess or bulk action."
        ),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        stateless_http=True,
        json_response=True,
    )

    client_factory: Callable[[], CoveClient | None] = lambda: get_client_from_context(settings)

    from .tools import (
        accounts,
        misc,
        partners,
        users,
    )

    accounts.register(mcp, client_factory)
    misc.register(mcp, client_factory)
    partners.register(mcp, client_factory)
    users.register(mcp, client_factory)

    return mcp
