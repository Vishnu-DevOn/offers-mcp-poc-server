"""
Home Service Offers MCP server implemented with FastMCP 2.13.1.

This uses low-level MCP handlers to bypass the FastMCP 2.13.1 bug where
@mcp.resource() doesn't include _meta in responses.
"""

import os
from typing import Any, Dict, List, Optional

import mcp.types as types
from fastmcp import FastMCP

# ------------------------------------------------------------------------------
# Initialize FastMCP server
# ------------------------------------------------------------------------------

mcp = FastMCP(
    "Home Service Offers",
    stateless_http=True,
)

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

S3_BASE_URL = os.getenv(
    "S3_BASE_URL",
    "https://open-ai-app-widget-poc.s3.us-east-1.amazonaws.com",
)

MIME_TYPE = "text/html+skybridge"
WIDGET_URI = "ui://widget/offers.html"

# ------------------------------------------------------------------------------
# Sample offers data
# ------------------------------------------------------------------------------

OFFERS = [
    {
        "businessId": "bTCz63K65g2o8irCxQuiRCRwOro1m7O4XyUF3Nxb_-Y=",
        "url": "https://www.onehourheatandair.com/lees-summit/about-us/what-to-expect/",
        "serviceCategory": "Emergency HVAC Service",
        "discountType": "amount",
        "discountValue": None,
        "priceCurrency": "USD",
        "price": None,
        "conditions": "Not valid with other offers.",
        "expirationDate": "2025-12-31",
        "stackable": None,
        "minimumPurchase": None,
        "description": "Get a free service call with any repair when you schedule with us!",
        "offerSource": "installer",
        "redemptionInstructions": "Call (816) 354-1077 to schedule and mention this offer.",
        "offerFeatures": ["free service call with repair"],
        "businessName": "One Hour Heating & Air Conditioning of Lee's Summit",
        "city": "Lee's Summit",
        "county": "Jackson County",
        "state": "MO",
        "zipcode": "64063",
        "location": None,
        "market": "Kansas City, MO-KS Metropolitan Statistical Area",
        "size": "Medium-to-Large",
    },
    {
        "businessId": "pLmb89K32f1x9jrDyRvjSDSxNqp2n8P5ZzVG4Oyc_-Z=",
        "url": "https://www.dallasplumbingpro.com/services/emergency-repair",
        "serviceCategory": "Plumbing",
        "discountType": "percentage",
        "discountValue": 20,
        "priceCurrency": "USD",
        "price": None,
        "conditions": "Valid for new customers only. Minimum $150 service.",
        "expirationDate": "2025-06-30",
        "stackable": False,
        "minimumPurchase": 150,
        "description": "20% off your first plumbing service call in Dallas!",
        "offerSource": "installer",
        "redemptionInstructions": "Call (214) 555-PIPE and mention promo code NEWCUST20.",
        "offerFeatures": [
            "20% discount",
            "new customer special",
            "emergency service available",
        ],
        "businessName": "Dallas Plumbing Professionals",
        "city": "Dallas",
        "county": "Dallas County",
        "state": "TX",
        "zipcode": "75201",
        "location": None,
        "market": "Dallas-Fort Worth-Arlington, TX Metropolitan Statistical Area",
        "size": "Large",
    },
    {
        "businessId": "hVaC12L54h3y8krEzSwiTETxOrq3o9Q6AzWH5Pzd_-A=",
        "url": "https://www.mckinneyhvac.com/cooling-services",
        "serviceCategory": "HVAC",
        "discountType": "amount",
        "discountValue": 75,
        "priceCurrency": "USD",
        "price": None,
        "conditions": "Cannot be combined with other promotions.",
        "expirationDate": "2025-08-15",
        "stackable": False,
        "minimumPurchase": None,
        "description": "$75 off AC tune-up and inspection service in McKinney area!",
        "offerSource": "installer",
        "redemptionInstructions": "Schedule online at mckinneyhvac.com or call (972) 555-COOL.",
        "offerFeatures": ["$75 savings", "complete AC inspection", "same day service"],
        "businessName": "McKinney HVAC Solutions",
        "city": "McKinney",
        "county": "Collin County",
        "state": "TX",
        "zipcode": "75070",
        "location": None,
        "market": "Dallas-Fort Worth-Arlington, TX Metropolitan Statistical Area",
        "size": "Medium",
    },
    {
        "businessId": "eLcT45M76k5z0lrFaUxkUFUyPrs4p0R7BaXI6Qae_-B=",
        "url": "https://www.texaselectricworks.com/residential-electrical",
        "serviceCategory": "Electrical",
        "discountType": "percentage",
        "discountValue": 15,
        "priceCurrency": "USD",
        "price": None,
        "conditions": "Valid Monday-Friday only. Excludes weekends and holidays.",
        "expirationDate": "2025-09-30",
        "stackable": None,
        "minimumPurchase": 200,
        "description": "Save 15% on electrical panel upgrades and rewiring services!",
        "offerSource": "installer",
        "redemptionInstructions": "Call (214) 555-VOLT to schedule. Mention code PANEL15.",
        "offerFeatures": ["15% discount", "licensed electricians", "free estimates"],
        "businessName": "Texas Electric Works",
        "city": "Dallas",
        "county": "Dallas County",
        "state": "TX",
        "zipcode": "75230",
        "location": None,
        "market": "Dallas-Fort Worth-Arlington, TX Metropolitan Statistical Area",
        "size": "Medium-to-Large",
    },
]

# ------------------------------------------------------------------------------
# Helper function for widget metadata
# ------------------------------------------------------------------------------


def _widget_meta() -> Dict[str, Any]:
    """Generate widget metadata for resources and tools."""
    return {
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "resource_domains": [S3_BASE_URL],
            "connect_domains": [],
        },
    }


# ------------------------------------------------------------------------------
# LOW-LEVEL RESOURCE HANDLERS (bypasses FastMCP 2.13.1 bug)
# ------------------------------------------------------------------------------


@mcp._mcp_server.list_resources()
async def _list_resources() -> List[types.Resource]:
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


async def _handle_read_resource(req: types.ReadResourceRequest) -> types.ServerResult:
    """Handle resource read requests."""
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


# Register the resource handler
mcp._mcp_server.request_handlers[types.ReadResourceRequest] = _handle_read_resource

# ------------------------------------------------------------------------------
# LOW-LEVEL TOOL HANDLERS
# ------------------------------------------------------------------------------


@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="get_offers",
            title="Get Home Service Offers",
            description="Retrieves available home service offers. Can optionally filter by service category, city, or state.",
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


async def _handle_call_tool(req: types.CallToolRequest) -> types.ServerResult:
    """Handle tool call requests."""
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

    arguments = req.params.arguments or {}
    filtered_offers = OFFERS.copy()

    # Apply filters
    if arguments.get("service_category"):
        category_lower = arguments["service_category"].lower()
        filtered_offers = [
            offer
            for offer in filtered_offers
            if category_lower in offer.get("serviceCategory", "").lower()
        ]

    if arguments.get("city"):
        city_lower = arguments["city"].lower()
        filtered_offers = [
            offer
            for offer in filtered_offers
            if city_lower in offer.get("city", "").lower()
        ]

    if arguments.get("state"):
        state_upper = arguments["state"].upper()
        filtered_offers = [
            offer
            for offer in filtered_offers
            if offer.get("state", "").upper() == state_upper
        ]

    # Prepare response
    count = len(filtered_offers)
    if count == 0:
        message = "No offers found matching your criteria."
    else:
        message = f"Found {count} offer{'s' if count != 1 else ''}."

    return types.ServerResult(
        types.CallToolResult(
            content=[types.TextContent(type="text", text=message)],
            structuredContent={"offers": filtered_offers},
            _meta={
                "openai/toolInvocation/invoking": "Fetching offers",
                "openai/toolInvocation/invoked": "Here are the available offers",
            },
        )
    )


# Register the tool handler
mcp._mcp_server.request_handlers[types.CallToolRequest] = _handle_call_tool

# ------------------------------------------------------------------------------
# ASGI app exposure
# ------------------------------------------------------------------------------

app = mcp.http_app

# ------------------------------------------------------------------------------
# CORS middleware
# ------------------------------------------------------------------------------

try:
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
except Exception:
    pass

# ------------------------------------------------------------------------------
# Local development entrypoint
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
