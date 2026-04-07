# K-Sync Environment And Settings Catalog

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This catalog is based on the current `ksync_project/settings.py` and `.env.example`.
- Legacy context: The raw settings file contains secrets and hardcoded defaults, so NotebookLM should use this sanitized summary instead of the raw file.

## Purpose

Use this guide when a task depends on environment variables, settings toggles,
hosting assumptions, or runtime flags.

## Safety Rule

Do not upload raw `settings.py` or `.env` into NotebookLM.

Reasons:

- the repo currently contains secret-bearing defaults and database URLs
- many settings are useful only after sanitizing and grouping them by purpose
- NotebookLM should learn the behavior of settings, not the credential values

## Settings Groups

### Runtime and bootstrapping

- `DJANGO_DEBUG`
  Controls debug mode and indirectly suppresses third-party tracking.
- `DJANGO_USE_SQLITE`
  Switches local development to SQLite instead of the default PostgreSQL path.
- `DATABASE_URL`
  Primary deployed database override.
- `SITE_URL`
  Canonical base URL used in social and metadata behavior.
- `ALLOWED_HOSTS`
  Currently permissive in code and should be treated as an operational caution.

### Static, media, and auth basics

- `STATIC_URL`, `STATIC_ROOT`
- `MEDIA_URL`, `MEDIA_ROOT`
- `LOGIN_URL`, `LOGIN_REDIRECT_URL`

These are stable Django platform settings rather than product toggles.

### Tracking and consent

- `GOOGLE_TAG_MANAGER_ID`
- `CLARITY_PROJECT_ID`
- `ENABLE_THIRD_PARTY_TRACKING`
- `FACEBOOK_PIXEL_ID`

These drive middleware-based injection of GTM, Meta Pixel, and Microsoft
Clarity on HTML responses when not in debug mode.

### AI and content generation

- `DEEPSEEK_API_KEY`
- `INWORLD_API_KEY`
- `INWORLD_API_ROOT`
- `INWORLD_BASE_URL`
- `INWORLD_CHAT_MODEL`
- `INWORLD_TTS_MODEL`
- `GETIMG_API_KEY`
- `PEXELS_API_KEY`
- `SERPER_API_KEY`

These power article generation, reasoning, voice-over generation, image
generation, and supporting research/enrichment flows.

### Social publishing

- Facebook
  - `FACEBOOK_PAGE_ID`
  - `FACEBOOK_PAGE_ACCESS_TOKEN`
  - `FACEBOOK_POST_ENABLED`
  - `FACEBOOK_POST_ON_CREATE_ENABLED`
  - `FACEBOOK_POST_INTERVAL_MINUTES`
  - `FACEBOOK_POST_QUEUE_START_DATE`
  - `FACEBOOK_HOMEPAGE_COMMENT_ENABLED`
  - `FACEBOOK_HOMEPAGE_COMMENT_TEXT`
- Facebook Reels
  - `FACEBOOK_REELS_ENABLED`
  - `FACEBOOK_REELS_RUN_ON_STARTUP`
  - `FACEBOOK_REELS_DAILY_HOUR`
  - `FACEBOOK_REELS_DAILY_MINUTE`
  - `FACEBOOK_REELS_API_VERSION`
  - preview and poll tuning settings
- Instagram
  - `INSTAGRAM_POST_ENABLED`
- X
  - `X_POST_ENABLED`
  - `X_POST_ON_CREATE_ENABLED`
  - `X_POST_INTERVAL_MINUTES`
  - `X_API_KEY`
  - `X_API_SECRET`
  - `X_ACCESS_TOKEN`
  - `X_ACCESS_TOKEN_SECRET`
- Pinterest
  - `PINTEREST_ACCESS_TOKEN`
  - `PINTEREST_BOARD_ID`

### Media and storage

- Cloudinary
  - `CLOUDINARY_CLOUD_NAME`
  - `CLOUDINARY_API_KEY`
  - `CLOUDINARY_API_SECRET`
- Backblaze B2
  - `B2_KEY_ID`
  - `B2_APPLICATION_KEY`
  - `B2_BUCKET_NAME`
  - `B2_DOWNLOAD_URL`
- Audio and image fetch toggles
  - `AUDIO_STREAM_USE_CLOUDINARY_FETCH`
  - `AUDIO_STREAM_CLOUDINARY_TRANSFORM`
  - `IMAGE_STREAM_USE_CLOUDINARY_FETCH`
  - `IMAGE_STREAM_CLOUDINARY_TRANSFORM`

### Radio.co integration

- `RADIOCO_ENABLED`
- `RADIOCO_STATION_ID`
- `RADIOCO_LISTEN_URL`
- `RADIOCO_API_BASE`
- `RADIOCO_TIMEOUT_SECONDS`
- `RADIOCO_REQUEST_WIDGET_ID`
- `RADIOCO_REQUEST_WIDGET_SRC`

These are the current live-radio truth settings and should be treated as the
main live playback path when enabled.

### Scheduler and maintenance toggles

- `B2_AUTO_SYNC_ENABLED`
- `B2_AUTO_SYNC_INTERVAL_MINUTES`
- `B2_AUTO_SYNC_RUN_ON_STARTUP`
- `B2_AUTO_SYNC_NEW_ONLY`
- `B2_AUTO_SYNC_PRUNE_MISSING`
- `B2_AUTO_SYNC_INCLUDE_VERSIONS`
- `PLAYLIST_WEEKLY_RANDOMIZE_ENABLED`
- `IMAGE_INTEGRITY_CHECK_ENABLED`
- `IMAGE_INTEGRITY_CHECK_DAY_OF_WEEK`
- `IMAGE_INTEGRITY_CHECK_HOUR`
- `IMAGE_INTEGRITY_CHECK_MINUTE`
- `IMAGE_INTEGRITY_CHECK_LIMIT`
- `IMAGE_INTEGRITY_CHECK_TIMEOUT_SECONDS`

## Current Truth Versus Legacy Interpretation

- Radio.co is the current live source and should be treated as primary when enabled.
- Cloudinary is active for delivery rewriting and voice-over storage.
- B2 is still real in the codebase, but it is now mostly:
  - legacy media support
  - migration tooling
  - fallback or library-sync infrastructure

## NotebookLM Rules

- When a feature behaves differently across environments, NotebookLM should say that explicitly.
- When a setting belongs to a secret-bearing category, NotebookLM should describe its purpose but never invent or repeat real values.
- If a task touches live radio, media delivery, or scheduler behavior, NotebookLM should check this catalog before answering.
