from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import CoveClient, CoveError
from ._common import NO_TOKEN

_SCHEMA_HINT = "see Schema_23.3.json (linked in README) for exact field names"


def register(mcp: FastMCP, client_factory: Callable[[], CoveClient | None]) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False))
    async def covedataprotection_add_user(
        user_info: Annotated[
            dict,
            Field(description=f"New user fields, per Cove's UserInfo struct ({_SCHEMA_HINT})."),
        ],
    ) -> str:
        """Create a new portal user account."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"userInfo": user_info}
        try:
            result = await client.call("AddUser", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_enumerate_user_roles() -> str:
        """List the available user role definitions."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("EnumerateUserRoles", {})
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_enumerate_users(
        partner_ids: Annotated[list[int], Field(description="Partner IDs whose portal users to list.")],
    ) -> str:
        """List portal users under the given partner IDs."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"partnerIds": partner_ids}
        try:
            result = await client.call("EnumerateUsers", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_get_user_info(
        partner_id: Annotated[int, Field(description="Partner ID the user belongs to.")],
        name_or_email: Annotated[str, Field(description="The user's login name or email address.")],
        password: Annotated[str, Field(description="The user's login password.")],
    ) -> str:
        """Look up a portal user by partner, name/email, and password.

        Only use this if the user has already explicitly supplied the
        login password themselves — never ask for or fabricate one.
        Prefer covedataprotection_get_user_info_by_id, which needs no
        password, whenever a user ID is available or resolvable via
        covedataprotection_enumerate_users.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"partnerId": partner_id, "nameOrEmail": name_or_email, "password": password}
        try:
            result = await client.call("GetUserInfo", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_get_user_info_by_id(
        user_id: Annotated[int, Field(description="User ID to fetch details for.")],
    ) -> str:
        """Get portal user details by numeric user ID."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"userId": user_id}
        try:
            result = await client.call("GetUserInfoById", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True))
    async def covedataprotection_modify_user(
        user_info: Annotated[
            dict,
            Field(
                description=f"User fields to overwrite, per Cove's UserInfo struct — must include the user's id ({_SCHEMA_HINT})."
            ),
        ],
    ) -> str:
        """Update a portal user's properties. Overwrites existing values; not
        reversible via this API. This replaces the entire object,
        including role/permissions — call
        covedataprotection_get_user_info_by_id first and merge your
        changes into the full record before calling, or unmentioned
        fields (including access level) may be silently reset.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"userInfo": user_info}
        try:
            result = await client.call("ModifyUser", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True))
    async def covedataprotection_remove_user(
        user_id: Annotated[int, Field(description="ID of the portal user to permanently delete.")],
    ) -> str:
        """Permanently delete a portal user by ID. Irreversible; only call
        with an explicit, confirmed user ID — never one inferred from a
        name match without the user confirming the resolved ID first.
        There is no suspend/disable option in this API — if the user
        asked to "deactivate" or "disable" someone, confirm they actually
        want permanent deletion before calling this.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"userId": user_id}
        try:
            result = await client.call("RemoveUser", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()
