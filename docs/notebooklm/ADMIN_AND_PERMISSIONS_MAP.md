# K-Sync Admin And Permissions Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map reflects decorators and guard helpers currently present in `core/views.py`.
- Legacy context: Some older staff tooling and modern member flows live side by side, so route location alone is not enough to infer permissions.

## Purpose

Use this guide when a change depends on who is allowed to access a route, API,
or workflow.

## Main Permission Buckets

### Public

Public pages include most discovery, content, and listening surfaces:

- home, charts, idols, schedule, news
- live page and stream hub
- presenters, pricing, about, legal pages
- many games and promo pages

Public does not mean static. Many public pages still depend on API data,
tracking middleware, or cached external services.

### Authenticated user

These are standard signed-in member flows protected with `@login_required`:

- onboarding
- dashboard
- notifications
- fan-club membership actions
- event join and badge claim flows
- contest management endpoints that require a logged-in operator

NotebookLM should treat these as user-account or member-state dependent flows.

### Staff signups surfaces

These use `login_required(login_url='/staff/login/')` and represent a separate
staff-facing auth path:

- `playlist_manager`
- `track_manager`
- `song_upload_manager`
- signups dashboard and export workflows

These are staff or internal operations surfaces, not regular member pages.

### Staff-only JSON

`_staff_only_json(request)` returns a 403 JSON response unless the user is both:

- authenticated
- `is_staff`

Current staff-only JSON usage includes:

- `blog/link-pass/`

### Admin-only JSON

`_admin_only_json(request)` returns a 403 JSON response unless the user is both:

- authenticated
- `is_superuser`

Admin-only JSON guards are currently used for the highest-risk manager APIs,
including:

- B2 track listing
- song upload
- playlist save, load, and delete
- track delete
- schedule save, delete, AI fill, and templates
- Inworld voice listing
- voice-over generation and synthesis
- AI playlist generation

## Mixed-Access Features

Some features blend audiences:

- `contests/` is public, but contest administration APIs require login
- `fan-clubs/` can be browsed publicly, but joining, leaving, and tier changes require login
- live radio is public, but some engagement or personalization layers depend on auth

## Internal and token-gated surfaces

Some routes are not staff-authenticated but are still non-public in practice:

- internal reel previews use a tokenized preview URL

Treat these as internal operational surfaces even if they do not use the same
staff decorator pattern.

## Permission Rules For NotebookLM

- Never assume a JSON route is public just because it lives under `api/`.
- Distinguish between:
  - public read surfaces
  - authenticated member actions
  - staff dashboards
  - superuser-only management endpoints
  - internal tokenized previews
- If a task changes an operator API, NotebookLM should warn about access control and not frame the change as a public UX-only task.
