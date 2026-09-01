# Pitmark Cloud v0.18.7 — Discord Launch Polish

## Launch-ready community content
- Populate and pin branded Pitmark intro panels across public community, Racing
  Tools, partner, staff and operations channels.
- Add polished welcome, community rules, official links, FAQ, service status,
  partnership information, racing/community prompts and staff channel guidance.
- Keep all managed content idempotent: future refreshes update the same bot-owned
  panel instead of posting duplicates.
- Remove the old plain-text bootstrap seed messages when the polished replacements
  are synced.

## Support & onboarding polish
- Expand the Pitmark Support Desk with category explanations, privacy guidance
  and response expectations.
- Improve new-ticket presentation and "what happens next" guidance.
- Add emoji to the racing-interest role selector and clearer role descriptions.
- Add an owner-only **Refresh Server Content** button to `/hq status`.
- `/hq sync` also refreshes managed content automatically.

## Community presentation
- Add emoji to existing Forum tags without recreating the Forum channels or tags.
- Set a Pitmark guild description.
- Attempt to configure Discord's Community welcome screen with direct links to
  Welcome, Pitmark Chat, Support, Racing Tools and Racing Chat. If Discord's
  configuration uses newer onboarding instead, this step is skipped without
  failing the content sync.

## Safety
- No user messages are deleted. Only exact old Pitmark bootstrap seed messages
  are eligible for cleanup.
- Existing tickets, forum posts, chat history, roles and permissions are preserved.
