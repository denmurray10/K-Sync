# K-Sync API And AJAX Surface Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This guide reflects the route-level API surface currently registered in `core/urls.py`.
- Legacy context: Some `api/` routes still serve legacy B2 or migration-adjacent workflows even though current live behavior is Radio.co-first.

## Purpose

Use this guide when a feature change touches JSON endpoints, background-fed page
APIs, or staff/operator tooling behind AJAX requests.

## Public and mostly public APIs

- `api/schedule-data/`
  Schedule data used by public timetable views.
- `api/search/`
  Search/discovery surface.
- `api/group-songs/<slug>/`
  Group song lookup for request and discovery flows.
- `api/comebacks/release/<release_id>/`
- `api/comebacks/day/<date_str>/`
  Drawer/detail endpoints for comeback timeline interactions.
- `api/live/status/`
- `api/live/rotate/`
- `api/live/chat/messages/`
  Live status and read-only live experience support.
- `api/events/monthly/`
  Public monthly events feed.
- `api/artist-stats/`
  Artist stats lookup.

## Authenticated member APIs

- `api/set-bias/`
- `api/toggle-favourite/`
- `api/remove-favourite/<pk>/`
- `api/save-game-score/`
- `api/notifications/`
- `api/notifications/<id>/read/`
- `api/fan-club/join/`
- `api/fan-club/leave/`
- `api/fan-club/perks/`
- `api/fan-club/set-tier/`
- `api/events/join/`
- `api/events/claim-badge/`
- `vote-poll/`

These operate on user state, profile personalization, fan-club participation,
or event progression.

## Live interaction and AI APIs

- `live/ai/like/`
- `live/ai/commentary/`
- `live/ai/theme/`
- `api/live/ai/helpful/`
- `api/live/save-moment/`
- `api/live/chat/send/`

These support the live experience but may combine public and authenticated
behavior depending on the action.

## Staff and operator JSON APIs

### Contest management

- `api/contests/create/`
- `api/contests/<contest_id>/edit/`
- `api/contests/<contest_id>/toggle/`
- `api/contests/<contest_id>/delete/`

### Radio management

- `api/b2-tracks/`
- `api/song-upload/`
- `api/playlist/save/`
- `api/playlist/<playlist_id>/data/`
- `api/playlist/<playlist_id>/delete/`
- `api/track/<track_id>/delete/`
- `api/schedule/save/`
- `api/schedule/<schedule_id>/delete/`
- `api/schedule/ai-fill/`
- `api/schedule/templates/`
- `api/schedule/templates/save/`
- `api/schedule/templates/<template_id>/delete/`

### Voice-over and AI programming

- `api/inworld/voices/`
- `api/voiceover/generate/`
- `api/voiceover/ai-scripts/`
- `api/voiceover/synthesize/`
- `api/playlist/ai-generate/`

## NotebookLM Rules

- Do not treat all `api/` routes as public just because they are JSON.
- Identify whether an endpoint is:
  - page-supporting and public
  - authenticated user state
  - staff dashboard support
  - superuser-only management tooling
- If a task touches a page and an API, NotebookLM should name both surfaces together.
