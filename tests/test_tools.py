"""tools/list snapshot + error-envelope mapping tests.

No network calls: tool enumeration goes through FastMCP's in-process
list_tools(), and the error-code mapping is tested directly against
CoveError, independent of any real HTTP request.
"""

import pytest

from covedataprotection_mcp.api_client import CoveError
from covedataprotection_mcp.config import Settings
from covedataprotection_mcp.server import create_mcp_server

# name -> (required params, expected annotation hints as (readOnly, destructive, idempotent))
EXPECTED_TOOLS = {
    "covedataprotection_add_account": ({"account_info", "home_node_info"}, (False, None, False)),
    "covedataprotection_enumerate_account_statistics": ({"query"}, (True, None, True)),
    "covedataprotection_enumerate_accounts": ({"partner_id"}, (True, None, True)),
    "covedataprotection_get_account_features": ({"account_id"}, (True, None, True)),
    "covedataprotection_get_account_info": ({"name", "password"}, (True, None, True)),
    "covedataprotection_get_account_info_by_id": ({"account_id"}, (True, None, True)),
    "covedataprotection_modify_account": (
        {"account_info", "force_remove_custom_column_values_in_old_scope"},
        (False, True, True),
    ),
    "covedataprotection_remove_account": ({"account_id"}, (False, True, True)),
    "covedataprotection_set_account_features": ({"account_id", "features"}, (False, True, True)),
    "covedataprotection_get_server_info": (set(), (True, None, True)),
    "covedataprotection_add_partner": (
        {"partner_info", "create_default_account"},
        (False, None, False),
    ),
    "covedataprotection_enumerate_child_partners": (
        {"partner_id", "fields", "partner_filter"},
        (True, None, True),
    ),
    "covedataprotection_enumerate_partners": (
        {"parent_partner_id", "fetch_recursively", "fields"},
        (True, None, True),
    ),
    "covedataprotection_get_partner_info": ({"name"}, (True, None, True)),
    "covedataprotection_get_partner_info_by_id": ({"partner_id"}, (True, None, True)),
    "covedataprotection_get_partner_tree": (
        {"partner_id", "fields", "filter", "children_limit", "partner_filter"},
        (True, None, True),
    ),
    "covedataprotection_get_root_partner_name": (set(), (True, None, True)),
    "covedataprotection_modify_partner": (
        {"partner_info", "force_remove_custom_column_values_in_old_scope"},
        (False, True, True),
    ),
    "covedataprotection_remove_partner": ({"partner_id"}, (False, True, True)),
    "covedataprotection_add_user": ({"user_info"}, (False, None, False)),
    "covedataprotection_enumerate_user_roles": (set(), (True, None, True)),
    "covedataprotection_enumerate_users": ({"partner_ids"}, (True, None, True)),
    "covedataprotection_get_user_info": (
        {"partner_id", "name_or_email", "password"},
        (True, None, True),
    ),
    "covedataprotection_get_user_info_by_id": ({"user_id"}, (True, None, True)),
    "covedataprotection_modify_user": ({"user_info"}, (False, True, True)),
    "covedataprotection_remove_user": ({"user_id"}, (False, True, True)),
}


@pytest.mark.asyncio
async def test_tools_list_snapshot():
    mcp = create_mcp_server(Settings())
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(EXPECTED_TOOLS), f"unexpected tool set: {names}"

    by_name = {t.name: t for t in tools}
    for name, (expected_required, (read_only, destructive, idempotent)) in EXPECTED_TOOLS.items():
        tool = by_name[name]
        required = set(tool.inputSchema.get("required", []))
        assert required == expected_required, f"{name}: required={required}"

        assert tool.annotations is not None, f"{name}: missing annotations"
        assert tool.annotations.readOnlyHint is read_only, f"{name}: readOnlyHint"
        if destructive is not None:
            assert tool.annotations.destructiveHint is destructive, f"{name}: destructiveHint"
        assert tool.annotations.idempotentHint is idempotent, f"{name}: idempotentHint"

        assert len(tool.description or "") <= 500, f"{name}: description too long"
        first_line = (tool.description or "").strip().splitlines()[0]
        assert len(first_line) <= 100, f"{name}: first line too long: {first_line!r}"
        assert "JSON-RPC" not in (tool.description or ""), f"{name}: leaks implementation detail"
        assert "API:" not in (tool.description or ""), f"{name}: leaks implementation detail"


@pytest.mark.asyncio
async def test_service_instructions_present_and_bounded():
    mcp = create_mcp_server(Settings())
    assert mcp.instructions
    assert len(mcp.instructions) <= 1500


@pytest.mark.parametrize(
    "status_code,expected_code,expected_retryable",
    [
        (0, "upstream_error", True),
        (400, "invalid_argument", False),
        (401, "unauthorized", False),
        (403, "unauthorized", False),
        (404, "not_found", False),
        (422, "invalid_argument", False),
        (429, "rate_limited", True),
        (500, "upstream_error", True),
        (503, "upstream_error", True),
    ],
)
def test_error_envelope_mapping(status_code, expected_code, expected_retryable):
    import json

    err = CoveError(status_code, "boom")
    envelope = json.loads(err.to_envelope())
    assert envelope["error"]["code"] == expected_code
    assert envelope["error"]["retryable"] is expected_retryable
    assert envelope["error"]["message"] == "boom"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raised_status,expected_code",
    [(400, "unauthorized"), (0, "upstream_error"), (503, "upstream_error"), (429, "rate_limited")],
)
async def test_login_rejection_is_unauthorized(monkeypatch, raised_status, expected_code):
    import json

    from covedataprotection_mcp.api_client import CoveClient

    async def fake_post(self, body):
        raise CoveError(raised_status, "Login failed")

    monkeypatch.setattr(CoveClient, "_post", fake_post)
    client = CoveClient("p", "u", "bad", "https://example.invalid")
    with pytest.raises(CoveError) as exc:
        await client.call("EnumerateAccounts")
    assert json.loads(exc.value.to_envelope())["error"]["code"] == expected_code
