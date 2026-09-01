# Pitmark Cloud v0.21.1 — Shopify Subscription Bridge + PRT Site Brand Pass

## Shopify / PRT licensing
- Replaces the Shopify webhook placeholder with verified HMAC processing.
- Seeds the two live PRT Shopify products into the entitlement mapping layer:
  - Pro: product `16009945579601`, variant `60271858024529`
  - League / Team: product `16009947643985`, variant `60271874211921`
- Captures paid PRT orders into durable `prt_shopify_purchases` storage.
- Detects monthly vs yearly selling-plan purchases from Shopify order payload data.
- Adds secure device-authenticated Shopify license claiming by order + purchase email.
- Renewal orders refresh already-linked device entitlements automatically.
- Cancelled orders, refunded PRT line items, and subscription status events can revoke or move linked entitlements into grace/inactive states.
- Adds admin visibility for stored Shopify purchases and mappings.

## PRT website
- Adds the new Pitmark Racing Tools horizontal logo as the primary site mark.
- Keeps the circular Pitmark Racing Co. badge as the parent-company mark in the footer.
- Adds Free / Pro / League-Team pricing cards with current subscription pricing.
- Refreshes the support hub branding and licensing FAQ.
- Updates the Windows-build label to v0.16.44 and surfaces Cloud licensing as connected.
- Desktop and mobile responsive layouts included.

## Version
- Authoritative Pitmark Cloud version bumped to `0.21.1` in `utils/config.py`.

## Shopify webhook endpoint
`POST /api/shopify/webhooks`

Webhook HMAC uses `SHOPIFY_WEBHOOK_SECRET` when configured, otherwise the existing `SHOPIFY_CLIENT_SECRET`.
