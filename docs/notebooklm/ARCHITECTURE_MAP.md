# K-Sync Architecture Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This doc reflects the current app, route, model, and workflow structure in the repo.
- Legacy context: Prototype pages, migration utilities, and older media flows still exist in code and should not automatically be treated as the primary product path.

This file explains the high-level structure of the K-Sync codebase in a way
that is safe for NotebookLM and useful for project-specific coding tasks.

## Top-Level Shape

K-Sync is primarily a Django 4.2 application with one dominant app: `core`.
The repo also includes Tailwind build scripts for frontend styles, management
commands for operational tasks, and notebook-oriented docs for Codex and
NotebookLM.

Key top-level areas:

- `ksync_project/` contains Django project config and root URL wiring
- `core/` contains most application logic, routes, models, templates, and helper functions
- `docs/notebooklm/` contains curated project-brain docs for NotebookLM
- `media/` is local media storage for development and generated assets

## Primary App Boundary

The `core` app is the product surface.

It owns:

- public pages
- user profile and fan features
- live radio and streaming pages
- content and editorial pages
- internal manager tools for tracks, playlists, and schedules
- AI endpoints
- background-job entrypoints and helper functions
- SEO defaults and tracking middleware

For most coding tasks, if the question is "where does this live?", `core` is
the first place to inspect.

## Root URL Structure

`ksync_project/urls.py` mounts:

- Django admin
- the `core` app at the site root
- sitemap and robots routes
- favicon and manifest redirects
- media serving during local development

This means nearly all user-facing routes are defined inside `core/urls.py`.

## Main Route Families In `core`

### Public product pages

- home, about, pricing, presenters, shop, schedule, charts, idols, comebacks, calendar, news, and legal pages

### Auth and user pages

- login, logout, signup, dashboard, profile, and onboarding

### Games and fan engagement

- song game, idol scramble, lyric drop, chart clash, fandom trivia, draft day, beat streak, contests, fan clubs, and notifications

### Live radio and streaming

- `live/`
- `live/player-popout/`
- `stream/`
- `stream/<slug>/`
- live chat, status, rotate, helpful-feedback, and saved-moment APIs

### Editorial and social workflow

- blog list and article routes
- manual blog generation
- internal link pass
- internal reel preview routes

### Radio management tools

- playlist manager
- track manager
- song upload manager
- schedule save, delete, and template APIs
- AI playlist generation and AI schedule fill APIs

### AI endpoints

- image generation
- ranking generation
- live commentary and theme
- DJ voice script generation
- voice synthesis
- playlist AI generation
- schedule AI fill

## Main Model Families

### Discovery and content

- `Ranking`
- `ComebackData`
- `KPopGroup`
- `KPopMember`
- `BlogArticle`

### User identity and engagement

- `UserProfile`
- `FavouriteSong`
- `LivePoll`
- `LivePollOption`
- `RadioTrackPlay`

### Live radio and programming

- `RadioTrack`
- `RadioStationState`
- `RadioPlaylist`
- `RadioPlaylistTrack`
- `RadioSchedule`
- `RadioScheduleTemplate`
- `RadioScheduleTemplateSlot`

These models are central to radio playback, schedule rendering, playlist
management, and AI-assisted radio operations.

## Rendering Model

The application is mostly server-rendered through Django templates in
`core/templates/core/`.

Important page groups include:

- live radio and stream templates
- charts, idols, and comeback timeline pages
- blog and editorial pages
- playlist, track, and song upload manager templates
- game and engagement pages

This is not a separate SPA architecture. The frontend is mostly Django templates
with Tailwind or CSS and targeted JavaScript behavior.

## Shared Infrastructure Helpers

Several important helpers sit in `core/views.py` even when they are not
directly exposed as views.

These include:

- DeepSeek and Inworld wrappers
- Radio.co integration helpers
- Cloudinary and remote media URL helpers
- live-page context builders
- blog generation and social publishing helpers
- admin and staff JSON gate helpers

When working on radio, editorial, or AI flows, expect view-layer helpers to
contain significant business logic.

## Startup And Scheduler Boundary

`core.apps.CoreConfig.ready()` starts the background scheduler only for:

- local `runserver`
- Heroku-style `web` dynos detected via the `DYNO` environment variable

This is important because background jobs are attached to the web process rather
than being isolated into a separate worker process inside this repo.

## Current Architecture Guidance

NotebookLM should summarize the architecture this way:

- K-Sync is a Django-first, `core`-centric web product
- live radio, editorial, AI, and management tooling all coexist in the same app
- route grouping matters more than package boundaries
- the live radio stack mixes current Radio.co integration with local fallback
  playlist and schedule logic
