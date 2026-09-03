# Pitmark Cloud v0.21.4 — Remove Control Center Mail UI

- Removes Pitmark Mail / Email from the Control Center desktop workspace navigation.
- Removes the mobile Email workspace and bottom-navigation entry.
- Removes Mail launch actions and stale direct `#email` navigation.
- Removes Control Center bulk-mail controls because the mailbox is no longer exposed there.
- Keeps Google Workspace / Gmail connected on the backend for Pitmark Shield, communications scanning/review, automation, and other server-side Pitmark workflows.
- Does not change Gmail sync, Shield classification, Gmail credentials, email backend APIs, or server-side mail services.
