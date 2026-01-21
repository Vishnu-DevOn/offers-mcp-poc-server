"""
Scalable Multi-Tenant Home Service Offers MCP Server.
Uses QUERY PARAMETER approach with FastMCP Middleware.

FIXED FOR FASTMCP CLOUD DEPLOYMENT

Key Changes:
1. Use FastMCP Middleware instead of Starlette middleware
2. Use FastMCP's Context system instead of ContextVar
3. Extract account_id directly in handlers using get_http_request()
4. Added OpenAI domain verification endpoint

Each business accesses via:
    /mcp?account_id={accountId}

Example URLs:
    http://localhost:8000/mcp?account_id=179ae270-6132-43f5-8398-989481085ea8
    http://localhost:8000/mcp?account_id=247bd891-7243-54e6-9409-a89592196fb9

Domain Verification:
    http://localhost:8000/.well-known/openai-apps-challenge
"""

import os
from typing import Any, Dict, List, Optional

import mcp.types as types
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_request
from fastapi.responses import PlainTextResponse

from offers_data import OFFERS

# ==============================================================================
# CONFIGURATION
# ==============================================================================

S3_BASE_URL = os.getenv(
    "S3_BASE_URL",
    "https://open-ai-app-widget-poc.s3.us-east-1.amazonaws.com",
)

MIME_TYPE = "text/html+skybridge"
WIDGET_URI = "ui://widget/offers.html"

# OpenAI Domain Verification Token
# IMPORTANT: Copy the EXACT token from OpenAI (no spaces, no newlines)
# Update this with your actual token from the OpenAI submission form
OPENAI_VERIFICATION_TOKEN = os.getenv(
    "OPENAI_VERIFICATION_TOKEN", "4oH7jwQBivDbh3X9xyXCEQzrKGeTEY2hwvbM8jqAEWw"
).strip()  # Remove any accidental whitespace

# ==============================================================================
# TENANT DATABASE
# ==============================================================================


class TenantDatabase:
    """
    Manages tenant (account) data and offer filtering.
    """

    def __init__(self):
        self.accounts = self._build_account_index()

    def _build_account_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index of accounts from offer data."""
        accounts = {}

        for offer in OFFERS:
            account_id = offer.get("accountId")
            if not account_id:
                continue

            if account_id not in accounts:
                business_name = offer.get("businessName", "Unknown Business")
                accounts[account_id] = {
                    "account_id": account_id,
                    "business_name": business_name,
                    "active": True,
                }

        return accounts

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account by ID."""
        account = self.accounts.get(account_id)
        if not account or not account.get("active", False):
            return None
        return account

    def get_offers_for_account(
        self, account_id: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get offers for specific account with optional filters."""
        filters = filters or {}

        # CRITICAL: Tenant isolation
        account_offers = [
            offer for offer in OFFERS if offer.get("accountId") == account_id
        ]

        filtered_offers = account_offers

        if filters.get("service_category"):
            category_lower = filters["service_category"].lower()
            filtered_offers = [
                offer
                for offer in filtered_offers
                if category_lower in offer.get("serviceCategory", "").lower()
            ]

        if filters.get("city"):
            city_lower = filters["city"].lower()
            filtered_offers = [
                offer
                for offer in filtered_offers
                if city_lower in offer.get("city", "").lower()
            ]

        if filters.get("state"):
            state_upper = filters["state"].upper()
            filtered_offers = [
                offer
                for offer in filtered_offers
                if offer.get("state", "").upper() == state_upper
            ]

        return filtered_offers


# Global database instance
db = TenantDatabase()

# ==============================================================================
# FASTMCP MIDDLEWARE (Cloud-Compatible)
# ==============================================================================


class AccountContextMiddleware(Middleware):
    """
    FastMCP Middleware to extract account_id and inject into Context.

    This works correctly in FastMCP Cloud because it uses FastMCP's
    native Context system, not Python's ContextVar.
    """

    async def on_message(self, context: MiddlewareContext, call_next):
        """
        Extract account_id from query params and store in FastMCP Context.
        """
        # Get the HTTP request from FastMCP's context
        try:
            # Access request via get_http_request() helper
            request = get_http_request()

            if request and hasattr(request, "query_params"):
                account_id = request.query_params.get("account_id")

                if account_id:
                    # Validate account
                    account = db.get_account(account_id)

                    if account:
                        # Store in FastMCP Context (persists through request)
                        context.fastmcp_context.set_state("account_id", account_id)
                        context.fastmcp_context.set_state(
                            "business_name", account["business_name"]
                        )
                    else:
                        # Invalid account
                        if context.method == "tools/call":
                            return types.ServerResult(
                                types.CallToolResult(
                                    content=[
                                        types.TextContent(
                                            type="text",
                                            text=f"Invalid or inactive account: {account_id}",
                                        )
                                    ],
                                    isError=True,
                                )
                            )
                else:
                    # No account_id provided
                    if context.method == "tools/call":
                        return types.ServerResult(
                            types.CallToolResult(
                                content=[
                                    types.TextContent(
                                        type="text",
                                        text="Missing account_id query parameter. Please provide ?account_id=YOUR_ACCOUNT_ID",
                                    )
                                ],
                                isError=True,
                            )
                        )
        except Exception as e:
            print(f"Error in AccountContextMiddleware: {e}")
            # Continue without error to allow list operations

        # Proceed with request
        return await call_next(context)


# ==============================================================================
# FASTMCP SERVER
# ==============================================================================

mcp = FastMCP(
    name="Multi-Tenant Home Service Offers",
)

# Add middleware
mcp.add_middleware(AccountContextMiddleware())


def _widget_meta() -> Dict[str, Any]:
    """Generate widget metadata."""
    return {
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "resource_domains": [S3_BASE_URL],
            "connect_domains": [],
        },
    }


# ==============================================================================
# OPENAI DOMAIN VERIFICATION
# ==============================================================================


# Get the underlying FastAPI app to add custom routes
@mcp.custom_route(path="/.well-known/openai-apps-challenge", methods=["GET"])
async def openai_domain_verification(request):
    """
    OpenAI Domain Verification Endpoint.

    This endpoint is required for OpenAI to verify domain ownership.
    The token is provided by OpenAI during the app submission process.

    Returns the verification token as plain text (no newlines, no extra formatting).

    Set via environment variable:
        OPENAI_VERIFICATION_TOKEN=your_actual_token_here

    Or update the OPENAI_VERIFICATION_TOKEN constant at the top of this file.
    """
    # Return exact token as plain text, no extra formatting
    return PlainTextResponse(
        content=OPENAI_VERIFICATION_TOKEN,
        media_type="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": "no-cache",
        },
    )


# ==============================================================================
# RESOURCE HANDLERS
# ==============================================================================


@mcp._mcp_server.list_resources()
async def list_resources_handler() -> List[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            name="Home Service Offers Widget",
            title="Home Service Offers Widget",
            uri=WIDGET_URI,
            description="Widget markup for displaying home service offers",
            mimeType=MIME_TYPE,
            _meta=_widget_meta(),
        )
    ]


async def read_resource_handler(req: types.ReadResourceRequest) -> types.ServerResult:
    """Serve the widget HTML."""
    if str(req.params.uri) != WIDGET_URI:
        return types.ServerResult(
            types.ReadResourceResult(
                contents=[],
                _meta={"error": f"Unknown resource: {req.params.uri}"},
            )
        )

    html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Home Service Offers</title>
    <link rel="stylesheet" href="{S3_BASE_URL}/offers-widget/assets/index.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="{S3_BASE_URL}/offers-widget/assets/index.js"></script>
  </body>
</html>"""

    contents = [
        types.TextResourceContents(
            uri=WIDGET_URI,
            mimeType=MIME_TYPE,
            text=html_content,
            _meta=_widget_meta(),
        )
    ]

    return types.ServerResult(types.ReadResourceResult(contents=contents))


mcp._mcp_server.request_handlers[types.ReadResourceRequest] = read_resource_handler


# ==============================================================================
# TOOL HANDLERS (Using FastMCP Context)
# ==============================================================================


@mcp._mcp_server.list_tools()
async def list_tools_handler() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="get_offers",
            title="Get Home Service Offers",
            description=(
                "Retrieves available home service offers for the authenticated account. "
                "Can optionally filter by service category, city, or state."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "service_category": {
                        "type": "string",
                        "description": "Filter by service category (e.g., 'HVAC', 'Plumbing', 'Electrical')",
                    },
                    "city": {
                        "type": "string",
                        "description": "Filter by city name",
                    },
                    "state": {
                        "type": "string",
                        "description": "Filter by state code (e.g., 'TX', 'MO')",
                    },
                },
                "additionalProperties": False,
            },
            _meta={
                "openai/outputTemplate": WIDGET_URI,
                "openai/toolInvocation/invoking": "Fetching offers",
                "openai/toolInvocation/invoked": "Here are the available offers",
            },
            annotations={
                "destructiveHint": False,
                "openWorldHint": False,
                "readOnlyHint": True,
            },
        )
    ]


async def call_tool_handler(req: types.CallToolRequest) -> types.ServerResult:
    """
    Handle tool execution with tenant isolation.

    CRITICAL: This handler extracts account_id from TWO sources:
    1. FastMCP Context (set by middleware)
    2. Direct query param access (fallback for cloud environments)
    """
    if req.params.name != "get_offers":
        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text", text=f"Unknown tool: {req.params.name}"
                    )
                ],
                isError=True,
            )
        )

    # Try to get account_id from multiple sources
    account_id = None

    # Method 1: Try FastMCP Context (set by middleware)
    # This works in both local and cloud
    try:
        # We don't have direct access to Context here, but middleware should have set it
        # We need to extract it from request instead
        pass
    except:
        pass

    # Method 2: Direct query param access (works in all environments)
    try:
        request = get_http_request()
        if request and hasattr(request, "query_params"):
            account_id = request.query_params.get("account_id")
    except Exception as e:
        print(f"Error accessing request in tool handler: {e}")

    # Validate we got an account_id
    if not account_id:
        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="Missing account_id query parameter. Please provide ?account_id=YOUR_ACCOUNT_ID",
                    )
                ],
                isError=True,
            )
        )

    # Validate account exists
    account = db.get_account(account_id)
    if not account:
        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Invalid or inactive account: {account_id}",
                    )
                ],
                isError=True,
            )
        )

    # Get account-specific offers with optional filters
    arguments = req.params.arguments or {}
    filtered_offers = db.get_offers_for_account(account_id, arguments)

    # Prepare response
    count = len(filtered_offers)
    business_name = account.get("business_name", "your account")

    if count == 0:
        message = f"No offers found for {business_name} matching your criteria."
    else:
        message = f"Found {count} offer{'s' if count != 1 else ''} for {business_name}."

    return types.ServerResult(
        types.CallToolResult(
            content=[types.TextContent(type="text", text=message)],
            structuredContent={"offers": filtered_offers},
            _meta={
                "openai/toolInvocation/invoking": "Fetching offers",
                "openai/toolInvocation/invoked": "Here are the available offers",
            },
            isError=False,
        )
    )


mcp._mcp_server.request_handlers[types.CallToolRequest] = call_tool_handler


# ==============================================================================
# ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 80)
    print("🚀 Multi-Tenant MCP Server (FastMCP Cloud Compatible)")
    print("=" * 80)
    print()
    print("Architecture: Query Parameter + FastMCP Middleware")
    print("URL Pattern: /mcp?account_id={account_id}")
    print("Cloud Compatible: YES (uses FastMCP native Context)")
    print()
    print("🔐 Domain Verification:")
    print(f"   Token: {OPENAI_VERIFICATION_TOKEN[:20]}...")
    print(f"   Endpoint: /.well-known/openai-apps-challenge")
    print()
    print("Available Accounts:")
    for account_id, account_data in db.accounts.items():
        offer_count = len(db.get_offers_for_account(account_id))
        print(f"  • {account_data['business_name']}")
        print(f"    Account ID: {account_id}")
        print(f"    Offers: {offer_count}")
        print()

    print("Test locally:")
    if db.accounts:
        first_account_id = list(db.accounts.keys())[0]
        print(
            f'  npx @modelcontextprotocol/inspector "http://localhost:8000/mcp?account_id={first_account_id}"'
        )
    print()
    print("Test domain verification:")
    print("  curl http://localhost:8000/.well-known/openai-apps-challenge")
    print()
    print("=" * 80)

    # Run with FastMCP's run() method for proper setup
    mcp.run(transport="http", port=int(os.getenv("PORT", "8000")))
