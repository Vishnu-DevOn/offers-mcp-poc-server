"""
Home Service Offers MCP server implemented with FastMCP 2.x.

This server exposes tools for fetching home service offers and renders
them using a React widget hosted on S3, compatible with OpenAI App SDK.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# ------------------------------------------------------------------------------
# Initialize FastMCP server
# ------------------------------------------------------------------------------

mcp = FastMCP(
    "Home Service Offers",
    stateless_http=True,  # Required for ChatGPT / OpenAI App SDK
)

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

S3_BASE_URL = os.getenv(
    "S3_BASE_URL",
    "https://open-ai-app-widget-poc.s3.us-east-1.amazonaws.com",
)

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
# Input schema for tool
# ------------------------------------------------------------------------------


class GetOffersInput(BaseModel):
    service_category: Optional[str] = Field(
        None, description="Filter by service category (e.g., HVAC, Plumbing)"
    )
    city: Optional[str] = Field(None, description="Filter by city name")
    state: Optional[str] = Field(None, description="Filter by state code (e.g., TX)")


# ------------------------------------------------------------------------------
# Widget resource (FastMCP 2.x correct pattern)
# ------------------------------------------------------------------------------


@mcp.resource(
    "ui://widget/offers.html",
    mime_type="text/html+skybridge",
    meta={
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "resource_domains": [S3_BASE_URL],
            "connect_domains": [],
        },
    },
)
def offers_widget_resource():
    return f"""<!doctype html>
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


# ------------------------------------------------------------------------------
# Tool: get_offers
# 
# ------------------------------------------------------------------------------


@mcp.tool(
    description="Retrieves available home service offers. "
    "Can optionally filter by service category, city, or state."
)
def get_offers(
    service_category: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    filtered = OFFERS.copy()

    if service_category:
        sc = service_category.lower()
        filtered = [o for o in filtered if sc in o.get("serviceCategory", "").lower()]

    if city:
        c = city.lower()
        filtered = [o for o in filtered if c in o.get("city", "").lower()]

    if state:
        s = state.upper()
        filtered = [o for o in filtered if o.get("state", "").upper() == s]

    message = (
        f"Found {len(filtered)} offer{'s' if len(filtered) != 1 else ''}."
        if filtered
        else "No offers found matching your criteria."
    )

    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": {"offers": filtered},
        "_meta": {
            "openai/outputTemplate": "ui://widget/offers.html",
            "openai/toolInvocation/invoking": "Fetching offers",
            "openai/toolInvocation/invoked": "Here are the available offers",
        },
    }



@mcp.tool(
    description="Retrieves available home service offers. "
    "Can optionally filter by service category, city, or state."
)
def get_offers_new(
    service_category: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    filtered = OFFERS.copy()

    if service_category:
        sc = service_category.lower()
        filtered = [o for o in filtered if sc in o.get("serviceCategory", "").lower()]

    if city:
        c = city.lower()
        filtered = [o for o in filtered if c in o.get("city", "").lower()]

    if state:
        s = state.upper()
        filtered = [o for o in filtered if o.get("state", "").upper() == s]

    message = (
        f"Found {len(filtered)} offer{'s' if len(filtered) != 1 else ''}."
        if filtered
        else "No offers found matching your criteria."
    )

    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": {"offers": filtered},
        "_meta": {
            "openai/outputTemplate": "ui://widget/offers.html",
            "openai/toolInvocation/invoking": "Fetching offers",
            "openai/toolInvocation/invoked": "Here are the available offers",
        },
    }

# ------------------------------------------------------------------------------
# ASGI app exposure (FastMCP 2.x)
# ------------------------------------------------------------------------------

app = mcp.http_app

# ------------------------------------------------------------------------------
# CORS (required for ChatGPT widget fetches)
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
