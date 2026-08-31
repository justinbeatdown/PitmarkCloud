# Pitmark Cloud v0.16.21 — Shield Classification Refinement

Refines Pitmark Mail security semantics so neutral uncertainty no longer looks like a threat.

- Adds `Unverified` for messages with no concrete risk signals and insufficient trust evidence.
- Keeps `Review` for actual concern signals such as protected topics, suspicious patterns, phishing language, or unsafe URLs.
- Preserves `Legit`, `System`, and `Spam`.
- Existing Pitmark Mail messages are rescanned so prior 40% `Review / insufficient-evidence` records become `Unverified`.
- Email UI treats Unverified as neutral gray instead of warning yellow.
- Mail status now reports Review and Unverified counts separately.
- Desktop and mobile share the same classification display.
