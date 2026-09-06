# Pitmark Cloud v0.21.27 — Product Media + TikTok Queue Cleanup

Cloud-only Autopilot refinement.

## Product posts
- First-party Shopify product campaigns now treat the **actual Shopify product image as authoritative** for Instagram.
- If a product event is missing media, Pitmark Cloud resolves the storefront product image directly from Shopify and stores it on the event.
- Existing pending/approved/scheduled Instagram product drafts are automatically repaired to use the real product image.
- Publishing and asset assignment now **refuse to substitute a generic or AI-generated image** for a first-party product post. If the Shopify image cannot be resolved, the post stays blocked until the image is available.

## TikTok
- Automatic first-party TikTok caption-only drafts are paused.
- New product, PRT, Street Team, partnership, blog, and milestone campaigns no longer create TikTok queue items.
- Existing first-party TikTok drafts that are still pending/approved/scheduled are archived automatically.
- Manual TikTok copy generation remains untouched; this only removes low-value automatic first-party caption drafts.

## Notes
- Facebook, Instagram, X, Discord, external racing intelligence, and manual composer workflows remain intact.
- No PRT desktop code was changed.

Pitmark Cloud: **0.21.27**
PRT desktop: **unchanged**
