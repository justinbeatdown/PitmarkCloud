# Pitmark Cloud v0.18.1 — Discord HQ Rate-Limit Hotfix

- Honors Discord HTTP 429 `retry_after` responses and automatically resumes HQ REST operations.
- Retries transient Discord 5xx errors with bounded exponential backoff.
- Eliminates repeated full channel-list fetches after every bootstrap write.
- A retry of a partially completed `/hq bootstrap` now reuses existing Pitmark-managed roles/categories/channels without rewriting them; `/hq sync` remains the explicit repair/update path.
- Adds small write pacing and rate-limit handling to seeded messages, panels, logs, and the deferred interaction response.
- Preserves the HQ guild lock, owner lock, public racing commands, support desk, moderation, AutoMod, and non-destructive server behavior from v0.18.0.
