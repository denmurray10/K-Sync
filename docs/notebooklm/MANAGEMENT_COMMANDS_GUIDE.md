# K-Sync Management Commands Guide

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This guide reflects the commands currently present in `core/management/commands`.
- Legacy context: Several commands still target Backblaze B2 migration and cleanup work even though Radio.co is now the primary live source.

## Purpose

Use this guide when a task touches a Django management command, scheduler job,
migration utility, or media maintenance workflow.

NotebookLM should answer these questions well:

- which command is safe to run repeatedly
- which command is diagnostic versus mutating
- which command is migration-only or legacy
- which command is scheduler-connected or production-relevant

## Command Categories

### Active diagnostics and maintenance

- `check_image_integrity`
  Verifies idol and blog image URLs over HTTP and writes a CSV report. Safe diagnostic command.
- `canary_cloudinary_images`
  Runs Cloudinary fetch checks against image URLs and can optionally flip an env file flag. Diagnostic by default, mutating only with `--auto-enable`.
- `send_user_digests`
  Sends due user digests through the same digest system used by the scheduler. Active operational command.
- `refresh_idol_stories`
  Regenerates idol profile copy through DeepSeek-based helpers. Mutating content command.
- `sync_kpopping_group_profiles`
  Pulls group and member profile information from Kpopping. Active sync utility with external side effects on local data.
- `sync_radio_track_artwork`
  Refreshes `RadioTrack` artwork using iTunes and Deezer matching. Active enrichment utility.
- `seed_monthly_events`
  Seeds sample monthly events and badge drops for testing or demo data. Safe in development, potentially noisy in shared data environments.

### Export and dry-run friendly utilities

- `export_media_urls_map`
  Exports current idol and blog media URLs into a CSV mapping template.
- `migrate_media_urls`
  Safely remaps media URLs from a CSV map. Dry-run by default; mutating only with `--apply`.
- `normalize_radio_bucket_tracks`
  Normalizes legacy radio audio URLs into supported bucket paths and can clear unsupported values. Review carefully before `--apply`.

### Migration and historical storage utilities

- `migrate_images_to_b2`
  Migrates idol and blog images into Backblaze B2, produces mappings, and can update DB records.
- `migrate_comeback_images_to_b2`
  Similar to `migrate_images_to_b2`, but scoped to `ComebackData` JSON payloads.
- `migrate_voiceovers_to_cloudinary`
  Moves legacy local or older voice-over assets into Cloudinary-backed storage.
- `optimize_large_b2_images`
  Re-encodes oversized B2-hosted images, uploads optimized variants, and can update database references.
- `upload_local_assets_to_b2`
  Uploads local assets to B2 and prints Cloudinary fetch URLs.

### Legacy radio and media support

- `api_b2_tracks` is not a management command, but several commands still exist to support B2-backed track libraries and migration cleanup.
- Treat B2-centric commands as legacy or migration support unless the task explicitly mentions B2 cleanup, fallback, or media normalization.

## Risk Levels

### Low-risk commands

- `check_image_integrity`
- `export_media_urls_map`
- `send_user_digests` in controlled environments

These are either diagnostic or operational without broad data rewrites.

### Medium-risk commands

- `canary_cloudinary_images`
- `refresh_idol_stories`
- `sync_kpopping_group_profiles`
- `sync_radio_track_artwork`
- `seed_monthly_events`

These can change live data or content, but are usually scoped and recoverable.

### High-risk commands

- `migrate_images_to_b2`
- `migrate_comeback_images_to_b2`
- `migrate_media_urls --apply`
- `migrate_voiceovers_to_cloudinary`
- `normalize_radio_bucket_tracks --apply`
- `optimize_large_b2_images --apply`
- `upload_local_assets_to_b2`

These touch production-like media references, storage paths, or large batches of records.

## Scheduler Relationship

The scheduler currently relies on code-level jobs in `core/scheduler.py`, not
on a large command-driven cron setup. The main scheduler-connected command is:

- `send_user_digests` by behavior, even though the scheduler calls the digest function directly

Other recurring background work is handled by internal Python functions rather
than `call_command`, except for the weekly image integrity check which calls:

- `check_image_integrity`

## NotebookLM Interpretation Rules

- Do not assume every command is part of the active production workflow.
- Distinguish between:
  - active maintenance
  - developer seeding or fixture support
  - migration-only utilities
  - legacy B2 cleanup tooling
- If a task mentions running a command, NotebookLM should identify whether it is:
  - safe by default
  - dry-run capable
  - mutating only with flags like `--apply`
  - risky because it rewrites URLs, uploads media, or calls external services
