# Pitmark Cloud v0.21.12 — PRT Tester Ops + Site Cleanup

- Changes the PRT Free metric to count only recently active Free devices instead of historical device identities left behind by development/security migrations.
- Keeps total registered devices available in PRT usage analytics.
- Adds tester workflow status management to Early Access invites.
- Adds a persistent PRT tester feedback queue for bugs, general feedback and feature requests.
- Adds admin feedback logging/status controls in Control Center and a device-authenticated Early Access feedback endpoint for future in-app submission.
- Adds an Open Feedback metric to the PRT hub.
- Cleans the public PRT header spacing and gives the official PRT logo more top breathing room.
- Updates the public PRT build label to v0.16.49.
- Adds Apply for Early Access calls-to-action across the PRT site.
- Adds /prt/apply, which safely redirects to the configured public Google Form responder URL.
- Does not weaken Pitmark Shield, device credentials, Shopify licensing, or the approved Control Center shell.

## Render setting
Set `PRT_EARLY_ACCESS_FORM_URL` to the public Google Forms responder URL (forms.gle/... or docs.google.com/forms/...).
