# K-Sync Project Brain Index

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This index points at the current curated source pack for the `K Beats Radio` notebook.
- Legacy context: Older bootstrap-only notebook states are superseded by the wider project-brain pack listed here.

This file is the table of contents for the K-Sync NotebookLM knowledge pack.
It points NotebookLM and future maintainers toward the curated internal sources
that should be treated as the primary project references.

## Purpose

The goal of this pack is to make NotebookLM useful as a project-specific brain
for K-Sync without uploading large raw source dumps or exposing secrets.

These docs should answer:

- how the project is structured
- which systems are current versus legacy
- how the live radio and media flows work
- how deployment and scheduled jobs behave
- how AI, editorial, and management workflows fit together
- which project rules Codex should follow before editing code

## Canonical Internal Sources

- `docs/notebooklm/K-SYNC_NOTEBOOKLM_BRIEF.md`
- `docs/notebooklm/ARCHITECTURE_MAP.md`
- `docs/notebooklm/ENGINEERING_CONVENTIONS.md`
- `docs/notebooklm/RADIO_MEDIA_MAP.md`
- `docs/notebooklm/OPERATIONS_DEPLOYMENT_MAP.md`
- `docs/notebooklm/AI_EDITORIAL_WORKFLOWS.md`
- `docs/notebooklm/RUNBOOK.md`
- `docs/notebooklm/INTEGRATIONS_MAP.md`
- `docs/notebooklm/DATA_MODEL_GUIDE.md`
- `docs/notebooklm/TOP_USER_FLOWS.md`
- `docs/notebooklm/ROUTE_OWNERSHIP_MAP.md`
- `docs/notebooklm/ADMIN_AND_PERMISSIONS_MAP.md`
- `docs/notebooklm/ENVIRONMENT_AND_SETTINGS_CATALOG.md`
- `docs/notebooklm/MANAGEMENT_COMMANDS_GUIDE.md`
- `docs/notebooklm/TEMPLATE_AND_UI_SURFACE_MAP.md`
- `docs/notebooklm/API_AND_AJAX_SURFACE_MAP.md`
- `docs/notebooklm/ANALYTICS_AND_TRACKING_MAP.md`
- `docs/notebooklm/SEO_AND_DISCOVERY_MAP.md`
- `docs/notebooklm/DATA_LIFECYCLE_MAP.md`
- `docs/notebooklm/TESTING_AND_RISK_AREAS.md`
- `docs/notebooklm/DECISION_LOG.md`
- `docs/notebooklm/PROJECT_GLOSSARY.md`
- `docs/notebooklm/DESIGN_SYSTEM.md`
- `docs/notebooklm/COMPONENT_PATTERNS.md`
- `docs/notebooklm/PAGE_PATTERNS.md`
- `docs/notebooklm/UX_RULES.md`
- `docs/notebooklm/COPY_STYLE_GUIDE.md`
- `docs/notebooklm/VISUAL_REFERENCE_SET.md`
- `docs/notebooklm/NOTEBOOK_VALIDATION_SUITE.md`
- `docs/notebooklm/NOTEBOOK_CHANGELOG.md`
- `docs/notebooklm/MAINTENANCE_CHECKLIST.md`
- `BRAND_GUIDELINES.md`
- `DEPLOYMENT_ENV_CHECKLIST.md`
- `WORKING_RULES.md`
- `RELEASE_CHECKLIST.md`

## How To Read This Pack

- Start with `K-SYNC_NOTEBOOKLM_BRIEF.md` for the shortest project summary.
- Use `ARCHITECTURE_MAP.md` for repo boundaries, route groups, models, and major
  request flows.
- Use `ENGINEERING_CONVENTIONS.md` for repo-specific rules, editing cautions,
  admin/staff boundaries, and current-vs-legacy interpretation rules.
- Use `RADIO_MEDIA_MAP.md` for live playback, stream presets, Radio.co, media
  delivery, Cloudinary, and legacy B2 references.
- Use `OPERATIONS_DEPLOYMENT_MAP.md` for runtime behavior, scheduler startup,
  deployment assumptions, env configuration, and management commands.
- Use `AI_EDITORIAL_WORKFLOWS.md` for AI, content generation, voiceovers,
  rankings, playlists, and social publishing workflows.
- Use `RUNBOOK.md` for practical deployment, incident, and operator reasoning.
- Use `INTEGRATIONS_MAP.md` for third-party service ownership and current-vs-legacy interpretation.
- Use `DATA_MODEL_GUIDE.md` for the most important model groups and product responsibilities.
- Use `TOP_USER_FLOWS.md` for end-to-end product journeys such as live listening,
  editorial publishing, onboarding, playlist management, and fan engagement.
- Use `ROUTE_OWNERSHIP_MAP.md` and `TEMPLATE_AND_UI_SURFACE_MAP.md` together when a task touches page ownership.
- Use `ADMIN_AND_PERMISSIONS_MAP.md` when a change touches auth, staff tools, or admin-only APIs.
- Use `ENVIRONMENT_AND_SETTINGS_CATALOG.md` for sanitized runtime and provider settings behavior.
- Use `MANAGEMENT_COMMANDS_GUIDE.md` when a task mentions a command, job, or migration utility.
- Use `API_AND_AJAX_SURFACE_MAP.md` for JSON endpoint ownership and API grouping.
- Use `ANALYTICS_AND_TRACKING_MAP.md` and `SEO_AND_DISCOVERY_MAP.md` for page-wide behavioral risks.
- Use `DATA_LIFECYCLE_MAP.md` when a task depends on where data originates or how jobs and caches touch it.
- Use `TESTING_AND_RISK_AREAS.md` before risky edits or when coverage is unclear.
- Use `DECISION_LOG.md` for "why is it shaped like this?" questions.
- Use `PROJECT_GLOSSARY.md` to normalize terminology.
- Use `DESIGN_SYSTEM.md` for brand, typography, spacing, motion, and public-versus-operator design rules.
- Use `COMPONENT_PATTERNS.md` when designing or refining buttons, forms, cards, chips, lists, or overlays.
- Use `PAGE_PATTERNS.md` to classify a page into a known K-Sync layout family before designing it.
- Use `UX_RULES.md` for CTA hierarchy, form behavior, loading/error states, and public-versus-operator UX decisions.
- Use `COPY_STYLE_GUIDE.md` for headlines, CTA labels, helper text, and tone.
- Use `VISUAL_REFERENCE_SET.md` with the screenshot pack when a design task needs grounding in the current live UI rather than abstract rules alone.
- Use `NOTEBOOK_VALIDATION_SUITE.md` for monthly or post-update validation.
- Use `NOTEBOOK_CHANGELOG.md` to track notebook evolution.
- Use `MAINTENANCE_CHECKLIST.md` to keep the notebook aligned with the live codebase.

## Current Truth Markers

NotebookLM should prioritize these interpretations:

- Radio.co is the current live song source for the radio experience.
- Cloudinary is an active delivery/storage concern for media and voice-over
  audio workflows.
- Backblaze B2 references still exist in code and utilities, but should be
  treated as legacy or secondary unless a task is explicitly about migrations or
  historical media handling.
- The `core` Django app owns almost all product logic, routes, models, and
  rendering.

## What Not To Upload

- `.env`
- raw `ksync_project/settings.py`
- direct secrets, tokens, database URLs, or auth headers
- broad raw source dumps when a curated summary is enough

## Suggested Validation Questions

- Summarize the K-Sync architecture and the role of the `core` app.
- Explain the current live radio path and Radio.co versus local fallback logic.
- Describe where Cloudinary fits into media delivery and voice-over workflows.
- Summarize scheduler behavior, deployment assumptions, and management commands.
- Explain the AI-assisted editorial and playlist tooling.
- What project-specific rules should Codex follow before editing code in this repo?
