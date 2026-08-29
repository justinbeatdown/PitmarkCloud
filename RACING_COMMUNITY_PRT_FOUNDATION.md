# Pitmark Racing Community / PRT Foundation — v0.12.2

This build establishes the shared Pitmark Cloud identity layer intended for Autopilot, Outreach, Campaign Manager, the website, PRT desktop, and future PRT Mobile.

## Permanent product rules
- PRT is open to everyone. Public/community participation is optional.
- Racing Community covers real-world racing, sim racing, and crossover participants/organizations.
- Pitmark Racing Community belongs to Pitmark Cloud; PRT participates through scoped APIs.
- Never merge identities by name alone.
- Public/community/internal/private data boundaries remain distinct.
- Outreach remains approval-first.

## New durable models
- `racing_community_entities`
- `racing_community_relationships`
- `racing_community_claims`
- `autopilot_research_jobs`

## New Control API foundation
- `GET /api/control/community/entities`
- `GET /api/control/community/entities/{id}`
- `POST /api/control/community/entities`
- `POST /api/control/community/relationships`
- `POST /api/control/community/research/prepare`
- `GET /api/control/community/research/{job_id}`

These endpoints are Control Center/admin protected. They are NOT the future public PRT API. A separate scoped PRT-facing API/auth layer should expose only permitted community/profile data.

## Community lanes
- `real`
- `sim`
- `crossover`

## PRT V1 target screens
1. My Racing Profile
2. iRacing identity connection
3. My Leagues
4. League Profile
5. Pitmark Features
6. Race Cards
7. Claim/Profile privacy foundation

## Autopilot Research Agent contract
`RESEARCH & PREPARE` creates a durable job containing the required output contract: verified facts, sources, strengths, weaknesses, PRT fit, Pitmark fit, recommended action, personalized outreach. This build queues/persists that job; it does not yet perform live web research or send outreach.

## Next integration layer
- Research worker + public/authorized source adapters
- claim verification flow
- canonical identity resolution/match review
- iRacing-supported data adapter
- scoped PRT Community API
- Control Center Racing Community UI
- Opportunity card `RESEARCH & PREPARE` button wired to the durable job
