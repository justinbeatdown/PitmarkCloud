# Pitmark Cloud v0.20.0 — Google Workspace / Gmail Migration

## Outcome

Pitmark Mail and Shield now use Google Workspace/Gmail as the production mailbox
infrastructure. The Control Center mail experience remains Pitmark-owned, while
Gmail becomes the delivery, inbox, alias, read-state, spam, trash and attachment
source of truth.

## Included

- Gmail API OAuth refresh-token authentication stored only in Render.
- Background inbox synchronization every 60 seconds by default.
- Business-only delivery filtering keeps personal Gmail traffic out of Pitmark Cloud.
- Google Workspace send-as identities in the Pitmark Mail composer.
- Root-domain Pitmark department addresses on desktop, mobile and PRT Support.
- Shield classification for newly synchronized Gmail messages.
- Gmail-aware read, spam and trash behavior.
- Authenticated inbound attachment downloads.
- Removal of the obsolete Resend inbound webhook and provider UI copy.

## Preserved

- v0.19.10 Race Card upload/startup repair.
- Existing Pitmark Mail database history and Shield audit history.
- Rich compose, local drafts, signatures, reply, reply-all and forward.
- Discord, Autopilot, Campaigns, Outreach, Shopify and PRT behavior.
- Desktop and mobile Control Center parity.
