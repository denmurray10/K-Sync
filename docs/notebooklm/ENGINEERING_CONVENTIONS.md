# K-Sync Engineering Conventions

## Freshness

- Last reviewed: 2026-04-06
- Current truth: These conventions are the current notebook-safe operating rules for Codex and maintainers.
- Legacy context: Older code may not perfectly follow every convention here, especially around B2-era workflows or prototype surfaces.

This file captures the repo-specific rules and interpretation guidance Codex
should follow before editing code in K-Sync.

## Core Editing Principles

- Prefer project-specific behavior over generic Django best practices when the
  repo clearly already has an established pattern.
- Treat the `core` app as the default home for product logic unless there is a
  strong reason to create a new boundary.
- Preserve current production behavior even if legacy utilities still exist in
  the codebase.
- Avoid introducing secrets, tokens, or raw deployment credentials into docs,
  prompts, or NotebookLM uploads.

## Current Truth Versus Legacy Context

Codex should interpret the repo with these defaults:

- Radio.co is the current live song source.
- Backblaze B2 references are legacy or secondary unless the task is explicitly
  about migration, historical storage, or fallback tooling.
- Cloudinary is active and relevant for current media workflows.
- Curated notebook docs should override stale assumptions from older utility
  scripts when they disagree about the current production path.

## Security And Secret Handling

- Never treat `.env`, raw `settings.py`, or hardcoded defaults as safe notebook
  upload material.
- Do not propagate live credentials into NotebookLM, prompts, or generated docs.
- If a source file contains both useful architectural context and secrets, write
  a sanitized summary instead of uploading the raw file.

## Staff And Admin Boundaries

Several JSON endpoints are intended for staff or admin use and are guarded by
helper checks such as `_staff_only_json` and `_admin_only_json`.

Before changing manager or automation APIs, confirm whether the endpoint is:

- public
- authenticated-user only
- staff only
- admin only

Do not assume all JSON routes are public just because they live in `views.py`.

## Runtime And Operational Cautions

- Scheduler behavior is tied to the web process and app startup.
- Some features depend on external services and environment variables.
- Local development can differ meaningfully from deployed behavior, especially
  around Radio.co, social posting, tracking, and digest dispatch.
- Settings often include toggles that change runtime paths, so environment
  conditions matter before editing live-related logic.

## Content And Editorial Conventions

- Blog generation is designed to produce long-form, human-sounding K-pop
  editorial content.
- Internal linking and site-link hints are part of the article generation flow.
- Social publishing is queue-oriented by default, even if immediate posting
  toggles exist.

When editing editorial flows, preserve the distinction between:

- content generation
- post-processing and internal linking
- queue-based social publishing
- media and image enrichment

## AI Workflow Conventions

- DeepSeek is the default general chat and generation path in the repo.
- DeepSeek Reasoner is used for heavier long-form generation.
- Inworld is used for specific radio voice and voice-over flows when configured.
- AI outputs are often expected to be constrained JSON or tightly formatted text.

Changes to AI prompts should preserve:

- deterministic output shapes where APIs depend on them
- UK English voice where explicitly required
- concise failure handling when provider calls return bad data

## NotebookLM Maintenance Rules

- Prefer curated summaries over raw source uploads.
- Update the notebook docs whenever a system changes meaningfully.
- If NotebookLM gives a wrong answer, fix the source docs rather than working
  around the problem in prompts.
- Keep "current truth" and "legacy context" clearly separated in docs.

## What Codex Should Do Before Editing

Before project-specific edits, Codex should check whether the task touches:

- current Radio.co behavior
- Cloudinary media rewriting or upload flows
- legacy B2 utilities
- scheduler and background jobs
- staff and admin-only tooling
- AI output contracts

If yes, it should consult the notebook first so changes stay grounded in the
actual K-Sync setup.
