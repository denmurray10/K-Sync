# K-Sync Data Lifecycle Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This guide reflects the present mix of user data, live radio metadata, editorial content, and scheduled enrichment jobs.
- Legacy context: Some media and radio records still pass through older B2-oriented utilities or migration helpers.

## Purpose

Use this guide when a task depends on where data originates, how it is enriched,
how long it lives, and which jobs or caches touch it.

## Major Data Lifecycles

### Live radio data

Origin:

- Radio.co station and current-track endpoints when enabled
- local radio models as fallback or internal curation state

Enrichment:

- artwork lookups
- recent-played reconstruction
- live page context building
- optional Cloudinary media rewriting

Consumers:

- live page
- stream pages
- player popout
- live status APIs

### Local radio programming data

Origin:

- `RadioTrack`, `RadioPlaylist`, `RadioPlaylistTrack`, `RadioSchedule`, template models
- song uploads and manager tools
- legacy B2 sync and normalization workflows

Enrichment:

- AI playlist generation
- AI schedule fill
- voice-over generation and synthesis
- weekly playlist randomization

Consumers:

- internal staff tools
- fallback live logic
- programming and schedule surfaces

### Editorial content data

Origin:

- generated article workflows
- comeback-derived article creation
- staff editorial generation and link-pass actions

Enrichment:

- image sourcing
- internal linking
- social publishing queue metadata
- reel preview generation for selected article types

Consumers:

- news page
- blog article pages
- social publishing jobs
- reel preview and publishing flows

### Idol and profile data

Origin:

- group and member records
- Kpopping sync utilities
- manual admin or data updates

Enrichment:

- DeepSeek-powered story refresh
- image integrity checks
- discovery and idol page assembly

Consumers:

- idols listing
- idol profile pages
- album detail views
- group song request flows

### User and engagement data

Origin:

- signup and onboarding
- `PreLaunchSignup` and `EmailPromotionSignup`
- `UserProfile`, favorites, scores, fan-club memberships, notifications

Enrichment:

- badge and tier progression
- digest scheduling by timezone
- contest and event participation

Consumers:

- dashboard
- onboarding
- fan clubs
- notifications
- contests and event systems

## Caches and scheduled transforms

- Radio.co payloads are cached to stabilize live reads.
- Comeback and release content is cached and reused across views.
- APScheduler drives recurring generation, posting, sync, digest, and integrity tasks.

## NotebookLM Rules

- When a task asks where data comes from, answer with origin plus enrichment path, not only the final model.
- If a flow mixes current and legacy systems, call that out explicitly.
- If a task touches scheduled or cached data, mention the background job or cache layer that may also need attention.
