# K-Sync Route Ownership Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map is based on `ksync_project/urls.py` and `core/urls.py`.
- Legacy context: Some experimental, lab, and exported pages share the same route file as production features.

## Purpose

Use this guide when a task asks:

- which route family owns a feature
- whether a route is public, authenticated, staff, or internal
- which product area a view belongs to

## Root Routing

`ksync_project/urls.py` owns the project-level entry points:

- `admin/` for Django admin
- `''` including all `core.urls`
- redirects for favicon and web manifest assets
- `sitemap.xml`
- `robots.txt`

The `core` app owns almost every product-facing route.

## Main Route Families

### Public marketing and discovery

- `/`
- `charts/`
- `idols/`
- `idols/universe/`
- `schedule/`
- `news/`
- `shop/`
- `pricing/`
- `about/`
- `presenters/`
- `promo/`
- `listen-free/`
- `games/`
- `results/`
- `calendar/`
- `fan-clubs/`
- legal pages

These are public-facing discovery and brand surfaces.

### Live radio and stream experiences

- `live/`
- `live/player-popout/`
- `stream/`
- `stream/<slug>/`
- `request/`

These routes are the main playback and live-interaction surfaces.

### Authenticated member flows

- `login/`
- `logout/`
- `signup/`
- `my-station/onboarding/`
- `dashboard/`
- `profile/`

These routes shape the signed-in experience and personalization path.

### Staff signups tooling

- `staff/login/`
- `staff/logout/`
- `staff/dashboard/`
- `staff/export/`

These are separate from the main authenticated member dashboard.

### Staff and operator management surfaces

- `playlist-manager/`
- `track-manager/`
- `song-upload-manager/`
- `blog/generate/`
- `blog/link-pass/`

These are management or internal editorial workflows rather than public product pages.

### Editorial and article reading

- `blog/<slug>/`
- `blog-page/`
- `new-release-spotlight/`
- `what-just-landed-reel-lab/`
- `internal/reels/preview/<slug>/<token>/`

### Community and engagement

- `contests/`
- `contests/<slug>/enter/`
- `fan-clubs/start/`
- `fan-clubs/polish-mission/`

### Comebacks and release intelligence

- `comeback-timeline/`
- `comebacks/`
- `comeback-timeline/landed/<slug>/`
- `comeback-design-lab/`

### Prototype, exported, and lab surfaces

Routes such as these exist in the same route file but should be interpreted as
design-lab or prototype surfaces unless clearly promoted into the main product:

- `404-preview/`
- `home-redesign-lab/`
- `comeback-design-lab/`
- `what-just-landed-reel-lab/`
- `neon-*`
- `test-*`
- exported celebration, store, reward, or modal routes

## API Route Ownership

### Public or mostly public APIs

- `api/schedule-data/`
- `api/search/`
- `api/group-songs/<slug>/`
- live status and rotation endpoints
- comeback drawer endpoints
- public monthly events feed

### Authenticated member APIs

- favourites and bias APIs
- game score saving
- notifications read and fetch
- fan-club join, leave, perks, tier, event participation, badge claim

### Staff or admin JSON APIs

- contest create, edit, toggle, delete
- radio track, playlist, schedule, upload, voice-over, and AI radio endpoints

These routes often look like generic JSON APIs but are not public.

## Route Ownership Rules For NotebookLM

- If a task touches the live radio experience, check the `live/` and `stream/` families first.
- If a task touches operator workflows, check management routes and admin-only JSON APIs before assuming the feature is user-facing.
- If a task mentions labs, previews, or exported design pages, treat them as lower-confidence surfaces until confirmed as production behavior.
- If a task mentions site-wide behavior, remember that almost all ownership still lives in the `core` app.
