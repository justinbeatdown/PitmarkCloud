# Pitmark Cloud v0.16.12

## Pitmark Mail — Partnerships identity

- Adds approved sender identities to Pitmark Mail.
- Keeps `mail@mail.pitmarkracing.com` as the safe default.
- Adds `partnerships@mail.pitmarkracing.com` as the first departmental identity.
- Desktop and mobile Compose now show a From selector.
- Drafts persist the selected identity using the existing message `from_address`.
- Replies with no explicit identity automatically inherit the Pitmark address that received the inbound message.
- Outbound Reply-To defaults to the selected departmental address.
- Existing Resend keys, inbound webhook verification, DNS, Shield, Shopify, Blog, and source-reader behavior are unchanged.
