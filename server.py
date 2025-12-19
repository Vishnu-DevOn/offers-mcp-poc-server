"""
Multi-tenant Home Service Offers MCP server with path-based routing.

Each business gets isolated access to their offers via:
    /{business_id}/mcp

Example URLs:
    http://localhost:8000/bTCz63K65g2o8irCxQuiRCRwOro1m7O4XyUF3Nxb_-Y=/mcp
    http://localhost:8000/bBrP89H32x7y4krCxTujRDRxNqp1m5O8YzUG2Nxc_-W=/mcp
"""

import os
from typing import Any, Dict, List

import mcp.types as types
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

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

# ==============================================================================
# TENANT DATABASE (In-Memory)
# ==============================================================================


class TenantDatabase:
    """
    Manages tenant (business) data and offer filtering.

    In production, replace with PostgreSQL queries.
    """

    def __init__(self):
        # Build business index from offers
        self.businesses = self._build_business_index()

    def _build_business_index(self) -> Dict[str, Dict[str, Any]]:
        """Build index of businesses from offer data."""
        businesses = {}

        for offer in OFFERS:
            business_id = offer.get("businessId")
            if not business_id:
                continue

            if business_id not in businesses:
                businesses[business_id] = {
                    "business_id": business_id,
                    "name": offer.get("businessName", "Unknown Business"),
                    "city": offer.get("city"),
                    "state": offer.get("state"),
                    "active": True,
                }

        return businesses

    def get_business(self, business_id: str) -> Dict[str, Any]:
        """
        Get business by ID.

        Raises:
            HTTPException: If business not found or inactive.
        """
        business = self.businesses.get(business_id)

        if not business:
            raise HTTPException(
                status_code=404, detail=f"Business not found: {business_id}"
            )

        if not business.get("active", False):
            raise HTTPException(
                status_code=403, detail=f"Business inactive: {business_id}"
            )

        return business

    def get_offers_for_business(
        self, business_id: str, filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Get offers for specific business with optional filters.

        Args:
            business_id: The business ID to filter by
            filters: Optional filters (service_category, city, state)

        Returns:
            List of offers for this business
        """
        filters = filters or {}

        # First filter: Only offers for this business (TENANT ISOLATION)
        business_offers = [
            offer for offer in OFFERS if offer.get("businessId") == business_id
        ]

        # Apply additional filters
        filtered_offers = business_offers

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
# FASTMCP SERVER FACTORY
# ==============================================================================


def _widget_meta() -> Dict[str, Any]:
    """Generate widget metadata."""
    return {
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "resource_domains": [S3_BASE_URL],
            "connect_domains": [],
        },
    }


def create_business_mcp_server(
    business_id: str, business_data: Dict[str, Any]
) -> FastMCP:
    """
    Create FastMCP server instance scoped to a specific business.

    Each business gets:
    - Isolated resources (branded widget)
    - Isolated tools (business-specific offers)
    - Isolated data (can't see other businesses' offers)

    Args:
        business_id: The business identifier
        business_data: Business metadata

    Returns:
        FastMCP instance configured for this business
    """

    # Create FastMCP instance with business-specific name
    # Note: Removed stateless_http=True (deprecated in 2.13.x)
    mcp = FastMCP(
        name=f"Offers - {business_data['name']}",
    )

    # ========================================================================
    # RESOURCE HANDLERS (Widget UI)
    # ========================================================================

    @mcp._mcp_server.list_resources()
    async def list_resources_handler() -> List[types.Resource]:
        """List available resources for this business."""
        return [
            types.Resource(
                name=f"{business_data['name']} - Offers Widget",
                title=f"{business_data['name']} - Home Service Offers",
                uri=WIDGET_URI,
                description=f"Widget markup for displaying {business_data['name']} offers",
                mimeType=MIME_TYPE,
                _meta=_widget_meta(),
            )
        ]

    async def read_resource_handler(
        req: types.ReadResourceRequest,
    ) -> types.ServerResult:
        """Serve the widget HTML for this business."""
        if str(req.params.uri) != WIDGET_URI:
            return types.ServerResult(
                types.ReadResourceResult(
                    contents=[],
                    _meta={"error": f"Unknown resource: {req.params.uri}"},
                )
            )

        # Business-branded widget HTML
        html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{business_data['name']} - Offers</title>
    <link rel="stylesheet" href="{S3_BASE_URL}/offers-widget/assets/index.css" />
  </head>
  <body>
    <div id="root" data-business-id="{business_id}" data-business-name="{business_data['name']}"></div>
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

    # Register resource handler
    mcp._mcp_server.request_handlers[types.ReadResourceRequest] = read_resource_handler

    # ========================================================================
    # TOOL HANDLERS
    # ========================================================================

    @mcp._mcp_server.list_tools()
    async def list_tools_handler() -> List[types.Tool]:
        """List available tools for this business."""
        return [
            types.Tool(
                name="get_offers",
                title=f"Get {business_data['name']} Offers",
                description=(
                    f"Retrieves available home service offers for {business_data['name']}. "
                    f"Can optionally filter by service category, city, or state."
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
                    "openai/openWorldHint": False,
                    "readOnlyHint": True,
                },
            )
        ]

    async def call_tool_handler(req: types.CallToolRequest) -> types.ServerResult:
        """Handle tool execution for this business."""

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

        # Get business-specific offers with optional filters
        arguments = req.params.arguments or {}

        # CRITICAL: Tenant isolation happens here
        # Only this business's offers are returned
        filtered_offers = db.get_offers_for_business(business_id, arguments)

        # Prepare response
        count = len(filtered_offers)
        if count == 0:
            message = (
                f"No offers found for {business_data['name']} matching your criteria."
            )
        else:
            message = f"Found {count} offer{'s' if count != 1 else ''} for {business_data['name']}."

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

    # Register tool handler
    mcp._mcp_server.request_handlers[types.CallToolRequest] = call_tool_handler

    return mcp


# ==============================================================================
# CREATE MCP SERVERS AND MOUNT THEM
# ==============================================================================

from contextlib import asynccontextmanager
from typing import AsyncIterator


# Create MCP servers BEFORE FastAPI app (so we can access their lifespans)
business_mcp_servers = {}
for business_id, business_data in db.businesses.items():
    mcp_server = create_business_mcp_server(business_id, business_data)
    business_mcp_servers[business_id] = mcp_server


@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Combined lifespan manager for all MCP servers.

    CRITICAL: This initializes the session managers for ALL MCP servers.
    Each MCP server has its own session manager that must be initialized.
    Without this, you'll get "Task group is not initialized" errors.

    We nest all MCP app lifespans to ensure all session managers are initialized.
    """
    # Get all MCP ASGI apps
    mcp_apps = []
    for business_id, mcp_server in business_mcp_servers.items():
        mcp_app = mcp_server.http_app(path="/mcp")
        mcp_apps.append((business_id, mcp_app))

    # Mount all MCP apps BEFORE starting lifespans
    for business_id, mcp_app in mcp_apps:
        app.mount(f"/{business_id}", mcp_app, name=f"mcp_{business_id}")

    # Initialize ALL MCP session managers by nesting their lifespan contexts
    # This ensures each business's MCP server is properly initialized
    if len(mcp_apps) == 0:
        yield
    elif len(mcp_apps) == 1:
        async with mcp_apps[0][1].lifespan(app):
            yield
    elif len(mcp_apps) == 2:
        # Nest both lifespans
        async with mcp_apps[0][1].lifespan(app):
            async with mcp_apps[1][1].lifespan(app):
                yield
    else:
        # For more than 2, we need to nest dynamically
        # Build nested context managers
        async def nested_lifespans(index: int):
            if index >= len(mcp_apps):
                yield
            else:
                async with mcp_apps[index][1].lifespan(app):
                    async with nested_lifespans(index + 1):
                        yield

        async with nested_lifespans(0):
            yield


# Create main FastAPI app with combined lifespan
app = FastAPI(
    title="Multi-Tenant Home Service Offers MCP Server",
    description="Path-based multi-tenant MCP server for home service offers",
    version="2.0.0",
    lifespan=combined_lifespan,  # CRITICAL: Pass the lifespan manager
)

# CORS middleware (required for ChatGPT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ==============================================================================
# UTILITY ENDPOINTS
# ==============================================================================


@app.get("/")
async def root():
    """API root endpoint with available businesses."""
    businesses = [
        {"business_id": bid, "name": bdata["name"], "endpoint": f"/{bid}/mcp"}
        for bid, bdata in db.businesses.items()
    ]

    return {
        "name": "Multi-Tenant Home Service Offers MCP Server",
        "version": "2.0.0",
        "businesses": businesses,
        "total_businesses": len(businesses),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "total_businesses": len(db.businesses),
    }


@app.get("/businesses")
async def list_businesses():
    """List all available businesses (for debugging)."""
    businesses = []

    for business_id, business_data in db.businesses.items():
        offer_count = len(db.get_offers_for_business(business_id))
        businesses.append(
            {
                "business_id": business_id,
                "name": business_data["name"],
                "city": business_data["city"],
                "state": business_data["state"],
                "offer_count": offer_count,
                "endpoint": f"/{business_id}/mcp",
            }
        )

    return {
        "businesses": businesses,
        "total": len(businesses),
    }


@app.get("/businesses/{business_id}")
async def get_business_info(business_id: str):
    """Get detailed info about a specific business."""
    try:
        business = db.get_business(business_id)
        offers = db.get_offers_for_business(business_id)

        return {
            "business": business,
            "offer_count": len(offers),
            "endpoint": f"/{business_id}/mcp",
            "offers": offers,
        }
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})


# ==============================================================================
# LOCAL DEVELOPMENT ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 80)
    print("🚀 Multi-Tenant Home Service Offers MCP Server")
    print("=" * 80)
    print()
    print("Available Businesses:")
    for business_id, business_data in db.businesses.items():
        offer_count = len(db.get_offers_for_business(business_id))
        print(f"  • {business_data['name']}")
        print(f"    Endpoint: http://localhost:8000/{business_id}/mcp")
        print(f"    Offers: {offer_count}")
        print()

    print("Test with MCP Inspector:")
    first_business_id = list(db.businesses.keys())[0]
    print(
        f"  npx @modelcontextprotocol/inspector http://localhost:8000/{first_business_id}/mcp"
    )
    print()
    print("=" * 80)

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
