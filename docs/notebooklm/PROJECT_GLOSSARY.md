# K-Sync Project Glossary

## Freshness

- Last reviewed: 2026-04-06
- Current truth: These terms reflect how the current repo and notebook docs describe the system.
- Legacy context: Some names still point at older media or radio implementations even when the product behavior has moved on.

## Purpose

Use this glossary to keep NotebookLM from confusing internal names, user-facing
names, and legacy references.

## Core Product Terms

- `K-Sync`
  The Django application and repo that powers the K-Beats experience.
- `K-Beats` or `K Beats Radio`
  The user-facing radio and fan product brand.
- `core`
  The dominant Django app that owns most routes, templates, models, and logic.

## Audience Terms

- public flow
  A route or feature that does not require login for primary use.
- authenticated flow
  A user journey that requires a logged-in account.
- staff/operator flow
  An internal workflow for managers, editors, or radio operators.
- admin-only JSON
  A JSON endpoint protected by the superuser-only helper, not a public API.

## Radio Terms

- Radio.co-first
  The current interpretation for live playback when Radio.co is enabled.
- local radio models
  `RadioTrack`, playlists, schedules, and related models that still power internal programming and fallback logic.
- fallback logic
  The local path used when Radio.co is unavailable or when internal programming data is still needed.

## Media Terms

- Cloudinary fetch
  Rewriting remote asset delivery through Cloudinary for optimization.
- voice-over storage
  Current Cloudinary-backed storage path for generated DJ audio.
- B2 legacy context
  Older Backblaze B2 storage, migration, or sync behavior that still exists in code.

## Editorial Terms

- What Just Landed
  A comeback-linked editorial and reels workflow around new releases.
- link pass
  The internal linking step applied to generated articles.
- queue-based publishing
  Social publishing behavior that usually schedules or meters output rather than posting everything immediately.

## Community Terms

- fan club tier
  Membership level used to gate perks, progression, and some event behavior.
- badge drop
  Reward-bearing event mechanism tied to activity and tier.
- digest
  Scheduled notification or email summary driven by user preferences and timezone-aware delivery.
