# Pitmark Cloud v0.16.18 — Shield Mail Protection

Connects Pitmark Mail to Pitmark Shield.

- Every new Resend `email.received` message is scanned by Shield immediately after verified webhook ingestion.
- Creates normal Shield events using the existing Shield classification/event system.
- Adds phishing-language detection and routes email URLs through the existing Shield external-URL safety gate.
- Stores each Shield verdict with the Pitmark Mail message without a database migration.
- Backfills existing inbound Pitmark Mail messages so protection is not limited to mail received after deployment.
- Pitmark Mail thread/list API responses now expose a `shield` verdict for desktop and mobile clients.
- Shield audit events record each mail scan.
- Gmail/legacy Shield behavior is untouched; Pitmark Mail becomes another protected input source.
- No DNS, Resend secret, webhook secret, Shopify, Blog, or source-reader changes.
