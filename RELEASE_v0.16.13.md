# Pitmark Cloud v0.16.13 — Pitmark Mail Delete Controls

## Added
- Delete Conversation on desktop Pitmark Mail.
- Delete Conversation on mobile Pitmark Mail.
- Delete Draft on desktop and mobile.
- Confirmation prompts before permanent deletion.
- Server-side deletion endpoints protected by Control Center authentication.
- Thread cleanup/recalculation after draft deletion.

## Behavior
- Deleting a conversation removes that conversation and all of its locally stored messages from Pitmark Cloud.
- Deleting a draft removes only that draft. If the draft was the last message in its thread, the empty thread is removed too.
- This does not alter Resend DNS, webhooks, sender identities, Shopify, Shield, Blog, or source-reader behavior.

## Verification
Test on both desktop and mobile:
1. Open an inbox or sent conversation.
2. Click Delete Conversation and confirm.
3. Verify it disappears from the list after refresh.
4. Create/save a draft, reopen it, click Delete Draft, and confirm it disappears.
