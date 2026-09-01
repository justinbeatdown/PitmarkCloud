# Pitmark Cloud v0.20.3 — Mail Performance + Sidebar Order

Focused repair before returning development focus to Pitmark Racing Tools.

CHANGED FILES
=============
api/control_center_v202.js
api/email_center.py

FIXES
=====
1. DESKTOP SIDEBAR ORDER
   Dashboard
   Autopilot
   Mail
   Shield
   Campaigns
   Outreach
   Blog
   PRT Analytics
   Directory
   Settings

   Settings is explicitly kept as the final workspace item. Existing buttons
   injected by older UI bundles are moved into canonical order instead of only
   ordering newly-created buttons.

2. MAIL PERFORMANCE
   Removed Gmail synchronization + full Shield rescans from:
   - GET /api/control/email/status
   - GET /api/control/email/threads
   - GET /api/control/email/threads/{thread_id}

   Those requests now read Cloud's synchronized mailbox directly instead of
   blocking the UI on Gmail API/network work and mailbox-wide Shield passes.

   Pitmark Cloud's existing Gmail background worker remains responsible for new
   inbound mail synchronization and Shield protection.

NOT CHANGED
===========
- Gmail credentials/configuration
- Mail send/reply/drafts
- Spam training
- Shield rules
- Mobile navigation
- PRT
