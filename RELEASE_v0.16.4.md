# Pitmark Cloud v0.16.4

- Preserve the HTTP 202 recovery path.
- Surface the actual WordPress fallback failure instead of hiding it behind the original HTTP 202.
- This is a diagnostic/root-cause hotfix: the next live test will identify whether the publisher's REST endpoint is returning 202/403/non-JSON/no matching slug.
- Shield URL and redirect validation remains unchanged.
- Shared desktop/mobile backend.
