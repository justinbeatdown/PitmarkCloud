# Pitmark Cloud v0.16.24 — PRT Support / Licensing Mail Identity

Adds a dedicated Pitmark Racing Tools identity to Pitmark Mail:

- Label: PRT Support / Licensing
- Sender name: Pitmark Racing Tools
- Address: prt@mail.pitmarkracing.com

The existing dynamic identity architecture automatically exposes it in both desktop and mobile From selectors. Inbound messages addressed to the identity inherit it for replies. Drafts and outbound messages preserve it like every other approved Pitmark Mail identity. Shield protection remains at the shared inbound layer, so PRT mail is protected automatically.
