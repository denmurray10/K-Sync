# K-Sync NotebookLM Brief

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This brief is the high-level summary of current K-Sync production interpretation.
- Legacy context: Detailed docs should override this brief when a system has evolved or been split into more precise notebook sources.

This document is a sanitized architecture and workflow summary for NotebookLM.
It is safe to upload because it avoids secrets, raw environment values, and
unredacted infrastructure credentials.

## Project Summary

K-Sync powers the K-Beats Radio website. The project is primarily a Django 4.2
application with one main app, `core`, plus Tailwind CSS build scripts for
frontend styling.

The site combines:

- public editorial pages such as home, charts, idols, schedule, blog, and legal pages
- interactive fan features such as profiles, favourites, polls, games, contests, and notifications
- a live radio experience with stream pages, live status, recently played, chat, and request flows
- internal content workflows for blog generation, social publishing, and reel preview/publish status
- AI-assisted features for images, live commentary, rankings, voiceovers, and playlist generation

## Current Audio Delivery Model

The current live song source is Radio.co, not Backblaze B2.

Important interpretation rules for future coding tasks:

- treat Radio.co as the primary live audio source
- treat Backblaze B2 references as legacy or secondary tooling, not the live song delivery path
- when describing current production radio playback, prefer Radio.co terminology first

The Django code currently supports both older radio track storage patterns and
the newer Radio.co integration. NotebookLM responses should describe Radio.co as
the current source of truth for live playback unless a task explicitly concerns
legacy migration utilities.

## Main Stack

- backend: Django 4.2
- database: PostgreSQL in deployed environments, optional SQLite for local work
- frontend build: Tailwind CSS scripts from `package.json`
- media and asset services: Cloudinary is relevant for delivery and transformations
- live radio integration: Radio.co public APIs and listen/request configuration
- AI integrations: OpenAI-adjacent and Inworld-style generation flows exist in the project

## Main Django Areas

### Routing shape

The root URL config mounts the `core` app and also serves admin, sitemap,
robots, favicon, and manifest endpoints.

The `core` app owns most product routes, including:

- marketing and editorial pages
- charts, idols, comebacks, calendar, presenters, pricing, and fan clubs
- auth and dashboard flows
- live radio pages and live JSON endpoints
- stream hub and stream player pages
- blog generation and article pages
- internal reel preview routes
- AI endpoints for ranking, images, commentary, themes, playlists, and voiceovers
- schedule, playlist, and track manager APIs

### Core model groups

Important model families include:

- content and discovery: `BlogArticle`, `KPopGroup`, `KPopMember`, `ComebackData`, `Ranking`
- fan identity and engagement: `UserProfile`, `FavouriteSong`, `LivePoll`, `LivePollOption`
- live radio state: `RadioTrack`, `RadioStationState`, `RadioTrackPlay`
- programming and automation: `RadioPlaylist`, `RadioPlaylistTrack`, `RadioSchedule`
- scheduling templates: `RadioScheduleTemplate`, `RadioScheduleTemplateSlot`

## Live Radio Behaviour

The live experience has two operating modes:

1. Radio.co mode
2. local or schedule-driven fallback mode

When Radio.co is enabled in settings and the station details are configured, the
live status endpoints use Radio.co station and current-track data. In that mode,
the app can return the current track plus recently played items directly from
Radio.co-backed helpers.

When Radio.co is not enabled, the app can fall back to locally managed
`RadioTrack`, playlist, schedule, and queue logic.

This means NotebookLM should answer radio questions with this priority:

1. current production playback comes from Radio.co
2. local playlist and schedule models still matter for management tools and fallback behaviour
3. older B2-oriented utilities should only be mentioned if the question is about migration or legacy media handling

## Stream And Live Pages

The public radio experience includes:

- `live/` for the live listening experience
- `stream/` for the stream hub
- `stream/<slug>/` for a specific stream preset
- live APIs for current status, rotation, helpful feedback, saved moments, and chat

These routes are important when asking NotebookLM to explain playback, queue
state, or live-user experience.

## Blog And Social Workflow

The project includes internal blog generation and publishing flows. `BlogArticle`
contains fields for:

- article content and source metadata
- Facebook posting state
- reel preview and publish lifecycle
- other social posting metadata

NotebookLM should treat blog and social tasks as part of the editorial system,
not just simple static content.

## Safe Config Summary

The project uses environment-driven settings for:

- database selection and connection
- site URL and tracking toggles
- Cloudinary delivery configuration
- Radio.co station and request widget configuration
- AI provider configuration
- social publishing toggles and schedules

Do not rely on raw `settings.py` values because the repository contains
hardcoded defaults and secrets that should not be copied into external systems.
Use this brief as the canonical upload instead of uploading raw settings files.

## Questions NotebookLM Should Answer Well

After upload, NotebookLM should be able to answer questions like:

- How does K-Sync handle radio audio delivery through Radio.co?
- Which model families power the live radio, schedule, and playlist tools?
- What route groups exist for live radio, streaming, blog, and AI features?
- Where do Cloudinary and Radio.co fit into the current architecture?
- Which features are current production flows versus legacy utilities?
