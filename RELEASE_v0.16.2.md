# Pitmark Cloud v0.16.2 — Source Reader Reliability

- Fixes Create Article from Source for public publishers that reject automation-identifying user agents.
- Uses browser-compatible request headers and validates every redirect through Pitmark Shield.
- Adds a same-origin WordPress REST fallback for public article permalinks when the front-end is challenged/blocked.
- Separates Shield-block diagnostics from ordinary public-page fetch/read failures.
- Preserves the existing Research Agent `fetch_page_excerpt()` interface.
- Adds page-read diagnostics to research enrichment without changing desktop/mobile UI contracts.
- Adds `.gitignore` rules so `__pycache__` and `*.pyc` do not enter future builds.
- Release version: 0.16.2.

Repo cleanup included with this coordinated patch:
- delete `services/__pycache__/research_agent.cpython-311.pyc`
- delete `utils/__pycache__/config.cpython-311.pyc`
