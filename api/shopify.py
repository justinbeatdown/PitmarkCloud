from fastapi import APIRouter, Request, Response, status
from models.schemas import ShopifyStatusResponse
from services.shopify_service import status as shopify_status

router = APIRouter()


@router.get("/status", response_model=ShopifyStatusResponse)
async def status_endpoint() -> ShopifyStatusResponse:
    return ShopifyStatusResponse(**shopify_status())


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
