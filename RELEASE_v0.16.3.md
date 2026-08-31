# Pitmark Cloud v0.16.3

## Source reader hotfix
- Handle HTTP 202 publisher/intermediary challenge responses as fallback-worthy.
- Inside Track News returned HTTP 202 rather than normal article HTML.
- The reader now attempts the existing Shield-safe same-origin WordPress REST fallback for HTTP 202.
- Shield redirect and private-network protections remain unchanged.
- Shared backend behavior applies to desktop and mobile Control Center.
- Version bumped to 0.16.3.
