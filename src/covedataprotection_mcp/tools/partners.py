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
    async def covedataprotection_add_partner(
        partner_info: Annotated[
            dict,
            Field(description=f"New partner fields, per Cove's PartnerInfo struct ({_SCHEMA_HINT})."),
        ],
        create_default_account: Annotated[
            bool, Field(description="Whether to also create a default backup account for the new partner.")
        ],
    ) -> str:
        """Create a new partner (MSP/customer tenant) under a parent partner."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"partnerInfo": partner_info, "createDefaultAccount": create_default_account}
        try:
            result = await client.call("AddPartner", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_enumerate_child_partners(
        partner_id: Annotated[int, Field(description="Partner ID whose direct children to list.")],
        fields: Annotated[
            dict,
            Field(description=f"Which partner fields to include in the response ({_SCHEMA_HINT})."),
        ],
        partner_filter: Annotated[
            dict,
            Field(description=f"Filter criteria to narrow the child partners returned ({_SCHEMA_HINT})."),
        ],
        range: Annotated[
            dict | None,
            Field(description="Optional paging window (e.g. offset/count) over the result set."),
        ] = None,
    ) -> str:
        """List the direct child partners of a given partner (one level only —
        not the full subtree), with field selection and filtering.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {
            "partnerId": partner_id,
            "fields": fields,
            "partnerFilter": partner_filter,
            "range": range,
        }
        params = {k: v for k, v in params.items() if v is not None}
        try:
            result = await client.call("EnumerateChildPartners", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_enumerate_partners(
        parent_partner_id: Annotated[int, Field(description="Partner ID to list descendants of.")],
        fetch_recursively: Annotated[
            bool, Field(description="If true, include all descendant partners, not just direct children.")
        ],
        fields: Annotated[
            dict,
            Field(description=f"Which partner fields to include in the response ({_SCHEMA_HINT})."),
        ],
    ) -> str:
        """List partners under a parent partner, optionally including all descendants recursively."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {
            "parentPartnerId": parent_partner_id,
            "fetchRecursively": fetch_recursively,
            "fields": fields,
        }
        try:
            result = await client.call("EnumeratePartners", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_get_partner_info(
        name: Annotated[str, Field(description="Partner name to look up.")],
    ) -> str:
        """Get partner details by partner name. Requires an exact name match —
        a nickname or partial name will not resolve.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"name": name}
        try:
            result = await client.call("GetPartnerInfo", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_get_partner_info_by_id(
        partner_id: Annotated[int, Field(description="Partner ID to fetch details for.")],
    ) -> str:
        """Get partner details by numeric partner ID."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"partnerId": partner_id}
        try:
            result = await client.call("GetPartnerInfoById", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_get_partner_tree(
        partner_id: Annotated[int, Field(description="Root partner ID to build the tree from.")],
        fields: Annotated[
            dict,
            Field(description=f"Which partner fields to include for each node ({_SCHEMA_HINT})."),
        ],
        filter: Annotated[
            str,
            Field(
                description=(
                    "String filter EXPRESSION to narrow which descendants are "
                    "included (not a dict — see partner_filter below for the "
                    "dict-shaped one)."
                )
            ),
        ],
        children_limit: Annotated[int, Field(description="Maximum number of children to return per node.")],
        partner_filter: Annotated[
            dict,
            Field(
                description=(
                    f"Dict-shaped filter criteria applied to partner nodes in "
                    f"the tree — distinct from the `filter` string expression "
                    f"above ({_SCHEMA_HINT})."
                )
            ),
        ],
    ) -> str:
        """Get the hierarchical tree of a partner and its descendant partners."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {
            "partnerId": partner_id,
            "fields": fields,
            "filter": filter,
            "childrenLimit": children_limit,
            "partnerFilter": partner_filter,
        }
        try:
            result = await client.call("GetPartnerTree", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def covedataprotection_get_root_partner_name() -> str:
        """Get the name of the root (top-level) partner for this Cove environment."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call("GetRootPartnerName", {})
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True))
    async def covedataprotection_modify_partner(
        partner_info: Annotated[
            dict,
            Field(
                description=f"Partner fields to overwrite, per Cove's PartnerInfo struct — must include the partner's id ({_SCHEMA_HINT})."
            ),
        ],
        force_remove_custom_column_values_in_old_scope: Annotated[
            bool,
            Field(
                description="If moving the partner to a new parent scope, whether to drop custom-column values that don't exist in the new scope."
            ),
        ],
    ) -> str:
        """Update a partner's properties. Overwrites existing values; not
        reversible via this API. This replaces the entire object — call
        covedataprotection_get_partner_info_by_id first and merge your
        changes into the full record before calling, or unmentioned
        fields may be silently cleared. Default
        force_remove_custom_column_values_in_old_scope to false unless
        the user explicitly confirms dropping those values.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {
            "partnerInfo": partner_info,
            "forceRemoveCustomColumnValuesInOldScope": force_remove_custom_column_values_in_old_scope,
        }
        try:
            result = await client.call("ModifyPartner", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True))
    async def covedataprotection_remove_partner(
        partner_id: Annotated[int, Field(description="ID of the partner to permanently delete.")],
    ) -> str:
        """Permanently delete a partner by ID. Irreversible; only call with an
        explicit, confirmed partner ID — never one inferred from a name
        match without the user confirming the resolved ID first. CAUTION:
        partners can have child partners and backup accounts nested
        beneath them (see covedataprotection_enumerate_child_partners);
        this API's cascading behavior on those descendants is not
        independently confirmed, so check for children first and treat
        this as high-blast-radius until proven otherwise.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"partnerId": partner_id}
        try:
            result = await client.call("RemovePartner", params)
            return dump_json_capped(result)
        except CoveError as e:
            return e.to_envelope()
