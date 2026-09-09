# Pitmark Cloud v0.21.41

## PRT paid subscription activation

- Paid PRT Shopify orders now mint one-time activation codes automatically:
  - `PRT-PRO-XXXX-XXXX-XXXX`
  - `PRT-TEAM-XXXX-XXXX-XXXX`
- Activation codes are delivered to the purchaser through Pitmark's Google Workspace mail integration.
- Successful delivery clears the temporary plaintext code; normal verification uses a SHA-256 hash plus a masked admin hint.
- Shopify webhook retries are idempotent and reuse the same pending code if delivery needs to be retried.
- Redeeming a paid code binds the purchased Pro or League / Team plan to the first PRT device.
- Cancellation/refund/subscription status changes revoke pending codes and continue to update active device entitlements.
- PRT v0.16.80 compatibility is preserved: its existing Early Access activation box accepts paid code prefixes through the legacy route, and Cloud translates active Shopify entitlements to the legacy Early Access source marker only for clients through v0.16.80.
- Added a dedicated `/api/entitlements/claim-paid-code` path for the v0.16.81+ activation UI.
- Existing order-number + purchase-email activation remains available as a fallback.
