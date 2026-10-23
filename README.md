# covedataprotection-mcp

MCP server for **Cove Data Protection** (N-able's backup/BDR platform,
formerly N-able Backup / Backup Manager). Exposes the Backup Manager
JSON-RPC **Management Service** API as MCP tools.

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request
  supplies its own credentials via headers, used only for the lifetime of
  that single request.
- Supports concurrent requests; per-request credential isolation is done via
  Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Scope

**26 tools**, trimmed down from an original 247-tool full-schema build
(2026-08-04). MSPbots' own Cove Data Protection integration (confirmed live
via `/web/int/sys/integration/api/list` against the production platform) is
configured with exactly 6 APIs, mapped to these underlying JSON-RPC methods:

| MSPbots-configured API | JSON-RPC method | Covered here? |
|---|---|---|
| Cove Data Protection Devices | `EnumerateAccounts` | ✅ |
| Cove Data Protection Devices Detail | `GetAccountInfoById` | ✅ |
| Cove Data Protection Device Statistics | `EnumerateAccountStatistics` | ✅ |
| Cove Data Protection Users | `EnumerateUsers` | ✅ |
| Cove Data Protection Customers | `EnumeratePartners` | ✅ |
| Cove Data Protection Query Sessions | `QuerySessions` | ❌ Reporting Service, not Management Service — see Known Gaps |

The other 5 confirmed-real methods above were kept as-is, plus **same-category
core CRUD** (`Add`/`Get`/`Modify`/`Remove`) for each of the three resource
types they touch — `accounts` (9 tools), `partners` (9 tools), `users` (7
tools) — plus `GetServerInfo` (1 tool, connectivity self-test, used for the
original live-verification below). Every other category from the original
247-tool build (`notifications`, `storage_nodes`, `contacts`, `storage`,
`view_delivery`, `labels`, `jobs`, `custom_columns`, `branding`, `products`,
`eula`, `locations`, `countries`, `audit`, `email`, `regions`, `features`,
`permissions`, `templates` — 19 categories, ~221 tools) was removed entirely
as unused by MSPbots and out of scope for this server's purpose.

## Authentication

Cove has no static long-lived API key. Instead, every session starts with a
**Login** call (`partner` + `username` + `password`) that returns a
short-lived **visa** token (valid ~15 minutes), which must accompany every
subsequent call.

This server does **not** cache a visa across requests — caching one would
mean persisting session state, which conflicts with the "no credential
persistence" requirement. Instead, `api_client.CoveClient.call()` performs a
fresh Login on *every* tool invocation and discards the resulting visa
afterward, trading one extra HTTP round trip per call for full statelessness.

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-CoveDataProtection-Partner` | string | 是 | 无 | 无 | Login 的 `partner` 字段（登录所属的租户/合作伙伴名） | `Acme MSP (admin@example.com)` |
| `X-CoveDataProtection-Username` | string | 是 | 无 | 无 | Login 的 `username` 字段 | `mspbots` |
| `X-CoveDataProtection-Password` | string | 是 | 无 | 无 | Login 的 `password` 字段 | `••••••••` |

Missing any of the three headers returns `401`:
```json
{
  "error": "Missing credentials",
  "message": "This server requires the X-CoveDataProtection-Partner, X-CoveDataProtection-Username, and X-CoveDataProtection-Password headers",
  "required_headers": ["X-CoveDataProtection-Partner", "X-CoveDataProtection-Username", "X-CoveDataProtection-Password"],
  "optional_headers": []
}
```

## Environment Variables

| Variable | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `MCP_HTTP_PORT` | int | 否 | `8080` | HTTP 监听端口 |
| `MCP_HTTP_HOST` | string | 否 | `0.0.0.0` | HTTP 监听地址 |
| `COVEDATAPROTECTION_BASE_URL` | string | 否 | `https://api.backup.management/jsonapi` | Cove Management Service JSON-RPC 端点 |

## MCP Endpoint

- `POST /mcp` — MCP protocol (streamable HTTP transport)
- `GET /health` — health check, returns exactly `{"status": "ok"}` (pure local liveness probe; does not call the Cove API)

## Tool List

Tool names follow `covedataprotection_<snake_case_method_name>` — e.g. the
JSON-RPC method `EnumerateAccountStatistics` becomes
`covedataprotection_enumerate_account_statistics`. Parameter names mirror
the JSON-RPC method's own parameter names (camelCase → snake_case); complex
struct/enum-typed parameters are accepted as a `dict`/`str` and passed
through to the vendor API as-is — see **Known Gaps** for what that means in
practice.

| Category | Tool | JSON-RPC Method | Params |
|---|---|---|---|
| accounts | `covedataprotection_add_account` | AddAccount | account_info(required), home_node_info(required) |
| accounts | `covedataprotection_enumerate_account_statistics` | EnumerateAccountStatistics | query(required) |
| accounts | `covedataprotection_enumerate_accounts` | EnumerateAccounts | partner_id(required) |
| accounts | `covedataprotection_get_account_features` | GetAccountFeatures | account_id(required) |
| accounts | `covedataprotection_get_account_info` | GetAccountInfo | name(required), password(required) |
| accounts | `covedataprotection_get_account_info_by_id` | GetAccountInfoById | account_id(required) |
| accounts | `covedataprotection_modify_account` | ModifyAccount | account_info(required), force_remove_custom_column_values_in_old_scope(required) |
| accounts | `covedataprotection_remove_account` | RemoveAccount | account_id(required) |
| accounts | `covedataprotection_set_account_features` | SetAccountFeatures | account_id(required), features(required) |
| misc | `covedataprotection_get_server_info` | GetServerInfo | none |
| partners | `covedataprotection_add_partner` | AddPartner | partner_info(required), create_default_account(required) |
| partners | `covedataprotection_enumerate_child_partners` | EnumerateChildPartners | partner_id(required), fields(required), partner_filter(required), range(optional) |
| partners | `covedataprotection_enumerate_partners` | EnumeratePartners | parent_partner_id(required), fetch_recursively(required), fields(required) |
| partners | `covedataprotection_get_partner_info` | GetPartnerInfo | name(required) |
| partners | `covedataprotection_get_partner_info_by_id` | GetPartnerInfoById | partner_id(required) |
| partners | `covedataprotection_get_partner_tree` | GetPartnerTree | partner_id(required), fields(required), filter(required), children_limit(required), partner_filter(required) |
| partners | `covedataprotection_get_root_partner_name` | GetRootPartnerName | none |
| partners | `covedataprotection_modify_partner` | ModifyPartner | partner_info(required), force_remove_custom_column_values_in_old_scope(required) |
| partners | `covedataprotection_remove_partner` | RemovePartner | partner_id(required) |
| users | `covedataprotection_add_user` | AddUser | user_info(required) |
| users | `covedataprotection_enumerate_user_roles` | EnumerateUserRoles | none |
| users | `covedataprotection_enumerate_users` | EnumerateUsers | partner_ids(required) |
| users | `covedataprotection_get_user_info` | GetUserInfo | partner_id(required), name_or_email(required), password(required) |
| users | `covedataprotection_get_user_info_by_id` | GetUserInfoById | user_id(required) |
| users | `covedataprotection_modify_user` | ModifyUser | user_info(required) |
| users | `covedataprotection_remove_user` | RemoveUser | user_id(required) |

## 测试示例

```bash
# Health check
curl -s http://localhost:8080/health

# Call a tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-CoveDataProtection-Partner: <your-partner-name>" \
  -H "X-CoveDataProtection-Username: <your-username>" \
  -H "X-CoveDataProtection-Password: <your-password>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <session-id-from-initialize>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "covedataprotection_get_server_info",
      "arguments": {}
    }
  }'
```

Expected: `200` with the server version on valid credentials; on invalid
credentials, the `Login` call itself fails and every tool returns a
structured JSON error envelope, e.g.:

```json
{"error":{"code":"unauthorized","message":"<vendor error message>","retryable":false}}
```

`code` is one of the fixed values `not_configured` / `unauthorized` /
`not_found` / `invalid_argument` / `rate_limited` / `upstream_error`;
`retryable` tells the caller whether retrying the same call could succeed
(true only for `rate_limited` and `upstream_error`). Tools never raise
exceptions for business/vendor errors — this envelope is returned as the
normal tool result string.

**Live-verified** (2026-07-29): `covedataprotection_get_server_info` (zero
parameters) was called end-to-end through this running server with a real
partner/username/password and returned the actual Cove server version —
confirming the Login → visa → method-call pipeline works against the live
API, not just structurally.

## API Reference

- Getting Started: https://developer.n-able.com/n-able-cove/docs/getting-started
- Authorization: https://developer.n-able.com/n-able-cove/docs/authorization
- Constructing a call: https://developer.n-able.com/n-able-cove/docs/construct-a-json-rpc-api-call
- Full method/struct/enum schema (JSON): https://documentation.n-able.com/covedataprotection/Schema_23.3.json

## Known Gaps

- **Trimmed from 247 to 26 tools on 2026-08-04.** The original build covered
  every method in the Management Service schema. Per a later scope decision,
  this was cut down to what MSPbots' own production integration config
  actually calls (verified live via `/web/int/sys/integration/api/list`
  against `app.mspbots.ai`, integration id `2026570354981494786`) plus
  same-category core CRUD — see the Scope section above for the exact
  API→method mapping and the full list of removed categories. The removed
  ~221 tools (`notifications`, `storage_nodes`, `contacts`, `storage`,
  `view_delivery`, `labels`, `jobs`, `custom_columns`, `branding`,
  `products`, `eula`, `locations`, `countries`, `audit`, `email`, `regions`,
  `features`, `permissions`, `templates`) are not in this build at all; if a
  future need requires one of them, the original schema
  (`Schema_23.3.json`, linked below) still documents its exact method
  signature and it can be re-added the same way the kept tools were
  generated.
- **This covers the Management Service only.** Cove's Getting Started guide
  describes a second, separate **Reporting Service** (`{host}/repserv_json`,
  runs per storage node) that provides backup/restore session statistics.
  MSPbots' own configuration calls a "Query Sessions" report against this
  Reporting Service — it is **not** part of the Management Service schema
  this MCP is generated from, and no public schema for the Reporting
  Service was found. This is the one MSPbots-configured endpoint this MCP
  does not cover; it can be added if the Reporting Service's method
  list/schema becomes available.
- **Complex struct/enum parameters are untyped (`dict`/`str`) rather than
  fully modeled.** The schema defines 106 structs and 78 enums; fully
  reproducing each one as a typed Python parameter was out of scope for a
  mechanically-generated server. Callers need to shape these dict
  arguments to match the vendor's schema (see the Structs section of
  `Schema_23.3.json` for exact field names) — each such parameter's
  description names the struct it maps to and points at that schema file.
- **No visa caching** — see the Authentication section above. Every tool
  call performs its own Login, which is simple and fully stateless but
  means 2 HTTP requests to the vendor per tool call instead of 1.
- All 26 tools were code-generated directly from the vendor's own schema
  file, not hand-written — parameter names/types are only as accurate as
  that schema. `covedataprotection_get_server_info` was the one tool
  live-verified end-to-end; the rest are structurally correct (schema
  validated, MCP-protocol tools/list confirmed) but not individually
  smoke-tested against real data.

## Vendor MCP SOP Compliance Notes

- **Tool count (26) exceeds the SOP's "should be ≤20" guideline.** Already
  trimmed 247 → 26 (see above); the remaining 26 map 1:1 to distinct
  JSON-RPC methods across 3 resource domains (accounts/partners/users) that
  cannot be merged without losing required-parameter distinctions (e.g.
  `get_*_info` by name+password vs. `get_*_info_by_id` by numeric ID are
  different lookup keys, not the same tool with an optional parameter).
- **No `limit` / `page_size` scalar parameter exists on any tool.** None of
  the 26 methods expose a first-class numeric page-size parameter — the one
  pagination-shaped field (`range` on `EnumerateChildPartners`) is an opaque
  vendor struct passed through as-is, and `children_limit` on
  `GetPartnerTree` is likewise passed straight to the vendor uninterpreted.
  There is nothing for this server to clamp against the SOP's default-50 /
  hard-cap-200 guidance; if the vendor schema's `range`/limit structs turn
  out to have their own documented per-page maximum, that should be
  enforced here instead of the SOP's generic fallback ceiling.
- **No credential env-var fallback.** `config.Settings` has no
  partner/username/password field; `get_client_from_context` returns `None`
  (→ `not_configured` envelope) whenever the per-request contextvar is
  unset. There is no code path that falls back to an environment variable.
- **Tool annotations**: every read tool (`get_*`, `enumerate_*`) is marked
  `readOnlyHint=True, idempotentHint=True`; `add_*` tools are
  `readOnlyHint=False, idempotentHint=False` (creating twice is not a
  no-op); `modify_*`/`set_*`/`remove_*` tools are
  `readOnlyHint=False, destructiveHint=True, idempotentHint=True`.
