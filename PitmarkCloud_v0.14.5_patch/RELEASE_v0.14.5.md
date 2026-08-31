# Pitmark Cloud v0.14.5

## Instagram + Social Asset Pool + Mobile Autopilot

- Adds live Instagram image publishing through the existing Meta Graph integration.
- Adds automatic Pitmark social image selection with reuse-aware rotation.
- Adds automatic Shopify product-image ingestion from the public Pitmark storefront.
- Adds manual asset assignment endpoint and “Pick Image” workflow.
- Extends scheduled publishing worker to Instagram.
- Fixes Connected Accounts display for Facebook and Instagram using real publishing status.
- Expands Mobile Control Center: generate, edit, save, approve, schedule, assign image and publish.
- Replaces the old per-field autofill workaround with a global authenticated-Control-Center guard.
- Sanitizes accidental `justin` / `admin` browser-autofill values before Autopilot generation.
- Version bumped to 0.14.5.
