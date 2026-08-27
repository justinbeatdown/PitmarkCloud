from utils.config import settings


def status() -> dict:
    configured = bool(
        settings.shopify_shop_domain
        and settings.shopify_client_id
        and settings.shopify_client_secret
    )
    return {
        "configured": configured,
        "message": (
            "Shopify credentials are configured; webhook/customer entitlement wiring is the next step."
            if configured
            else "Shopify integration scaffold is ready. Credentials have not been configured yet."
        ),
    }
