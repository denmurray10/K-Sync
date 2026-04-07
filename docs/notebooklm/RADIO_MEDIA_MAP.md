# K-Sync Radio And Media Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map reflects Radio.co as the current live source and Cloudinary as the active media optimization layer.
- Legacy context: B2-backed media utilities and local radio systems still exist and matter for fallback, migration, and internal programming.

This file describes the current live radio path, stream logic, media delivery,
and the relationship between Radio.co, Cloudinary, and legacy B2 references.

## Current Live Song Source

The current primary live song source is Radio.co.

NotebookLM should treat this as the default answer for questions about current
production playback unless the task is explicitly about fallback logic or older
storage tooling.

## Two Live Modes

The radio experience has two operating modes:

1. Radio.co mode
2. local schedule-driven fallback mode

### Radio.co mode

When `RADIOCO_ENABLED` is true and the station ID plus listen URL are
configured, the app uses Radio.co-backed helpers to fetch:

- station info
- current track info
- public status
- recently played tracks
- request widget source

In this mode:

- Radio.co acts as the source of truth for what is currently playing
- the live status endpoint returns current-track data from Radio.co helpers
- the app can synthesize local display payloads from Radio.co responses

### Local fallback mode

When Radio.co is not enabled, the app falls back to local radio models and
scheduler logic built around:

- `RadioTrack`
- `RadioStationState`
- `RadioPlaylist`
- `RadioPlaylistTrack`
- `RadioSchedule`
- schedule-context and queue-rotation helpers

This fallback path is still important for management tools, testing, and
internal scheduling behavior.

## Stream Experience

The user-facing radio and streaming surface includes:

- `live/` for the main live page
- `stream/` for the stream hub
- `stream/<slug>/` for stream presets
- live chat and status APIs
- helpful feedback and "save this moment" APIs

`_build_live_page_context`, `_resolve_live_page_context`, and `_stream_presets`
are important helper boundaries when understanding how playback UI is composed.

## Media Delivery Layers

### Cloudinary

Cloudinary is active in the project and relevant in multiple ways:

- optional fetch-based rewriting of Backblaze-style audio URLs
- optional fetch-based rewriting of image URLs
- upload target for synthesized voice-over audio
- optimization and delivery for selected image flows

This means Cloudinary is not just a future or experimental integration. It is
already part of current media handling.

### Radio.co media interaction

In the Radio.co path, the app uses Radio.co metadata as the canonical live-track
signal and then builds display payloads for the frontend.

NotebookLM should describe this as:

- Radio.co decides the live track identity
- the Django app enriches, caches, and renders the live experience
- Cloudinary and local helpers may still shape delivery URLs or related media

## Legacy Backblaze B2 Context

Backblaze B2 still appears in the codebase in:

- URL rewriting helpers
- older media and migration commands
- `.env.example`
- management commands for image and media migration

However, it should not be described as the current live song source.

The right interpretation is:

- B2 is legacy or secondary context
- some code still knows how to work with B2-hosted media
- some commands exist for migration, normalization, or export tasks
- current production live song delivery should still be described as Radio.co-first

## Song Upload And Playlist Management

Internal management tools support:

- track ingestion and deletion
- playlist save, delete, and data operations
- voice-over generation and synthesis
- AI playlist generation
- AI schedule fill

These management tools rely on local radio models even though Radio.co is the
current live song source. That distinction matters:

- Radio.co powers current live playback truth
- local radio models still power internal curation, fallback, and scheduling workflows

## Voice-Over And Audio Generation

Voice-over flows use Inworld for:

- script generation
- text-to-speech synthesis

Synthesized voice-over audio is then uploaded to Cloudinary and returned as
playlist-ready track data. This is a current active workflow and should be
treated as part of the radio and media system, not as an isolated experiment.

## Recommended NotebookLM Interpretation

When asked about radio and media, NotebookLM should answer in this order:

1. Radio.co is the primary current live audio source
2. local playlist, schedule, and radio models still matter for tooling and fallback behavior
3. Cloudinary is active in delivery and synthesized-audio workflows
4. B2 is legacy or migration context unless the task explicitly targets it
