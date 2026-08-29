# Pitmark Cloud v0.10.0 — Control Center Login + Real Views

After deployment, open `/control`.

On the first visit only, Pitmark will show **Initialize Control Center**:
1. Enter the existing `PITMARK_ADMIN_KEY` once.
2. Keep username `admin` or choose another username.
3. Create a password of at least 12 characters.
4. The password is stored only as a salted scrypt hash in the persistent database.

After setup, `/control` shows a private login screen and the old Admin Key field is gone. The browser receives a signed, Secure/HttpOnly/SameSite=Strict session cookie. The existing Admin Key remains available for service-to-service/emergency API access but is no longer part of normal dashboard use.

Autopilot > Posts & Queue is now a real view with filters and approve/reject/schedule/archive actions. Publish remains intentionally disabled until platform OAuth/publishing connectors are connected.
