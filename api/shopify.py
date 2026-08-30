from fastapi import APIRouter, Request, Response, status
from models.schemas import ShopifyStatusResponse
from services.shopify_service import status as shopify_status, connection_test

router = APIRouter()


@router.get("/status", response_model=ShopifyStatusResponse)
async def status_endpoint() -> ShopifyStatusResponse:
    return ShopifyStatusResponse(**shopify_status())


@router.get("/connection")
async def connection_endpoint():
    try:
        return connection_test()
    except Exception as exc:
        return {"configured": shopify_status().get("configured", False), "authenticated": False, "error": str(exc)}


@router.post("/webhooks")
async def webhook_placeholder(request: Request) -> Response:
    # Intentionally does NOT trust or process Shopify payloads yet.
    # Production implementation must verify the Shopify webhook HMAC first.
    await request.body()
    return Response(
        content="Shopify webhook endpoint scaffolded; HMAC verification not configured yet.",
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        media_type="text/plain",
    )
