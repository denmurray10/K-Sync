# NotebookLM Setup For K-Sync

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This setup file reflects the expanded project-brain source pack and current validation workflow.
- Legacy context: Older setup instructions that only covered the initial bootstrap docs are incomplete now.

This file is the operator checklist for connecting Codex to NotebookLM and
using the first K-Sync notebook safely.

## What To Upload First

Start with these sources:

- `BRAND_GUIDELINES.md`
- `DEPLOYMENT_ENV_CHECKLIST.md`
- `docs/notebooklm/K-SYNC_NOTEBOOKLM_BRIEF.md`
- `docs/notebooklm/PROJECT_BRAIN_INDEX.md`
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
- `docs/notebooklm/NOTEBOOK_VALIDATION_SUITE.md`
- `docs/notebooklm/NOTEBOOK_CHANGELOG.md`
- `docs/notebooklm/MAINTENANCE_CHECKLIST.md`
- `WORKING_RULES.md`
- `RELEASE_CHECKLIST.md`

Add vendor docs that are actively relevant to current work:

- Radio.co docs
- Cloudinary docs
- Django 4.2 docs
- AI provider docs you are actively using

Do not upload these files directly:

- `.env`
- raw `ksync_project/settings.py`
- any file containing live tokens, credentials, or database URLs

## Recommended Notebook Name

Use: `K-Sync Core Architecture`

## Recommended Prompts

Use these prompts to validate the setup:

- Show our notebooks.
- Use the K-Sync notebook.
- Research this in NotebookLM before coding: how does K-Sync handle radio audio delivery through Radio.co?
- Based on the K-Sync notebook, summarize the main Django models and route groups.
- Before editing, explain whether this task touches Radio.co, Cloudinary, local fallback radio logic, or legacy B2 utilities.

## Expected Behaviour

Good answers should:

- describe Radio.co as the current song source
- mention Cloudinary where delivery or transformation is relevant
- treat B2 references as legacy unless the task is specifically about migration or older tooling
- summarize the `core` app as the main application surface
- distinguish live playback routes from editorial and management routes
- explain scheduler/runtime behavior without leaking raw secret-bearing settings
- understand AI/editorial workflows as structured product systems, not isolated experiments
- classify routes, templates, APIs, permissions, and risk surfaces correctly

## Authentication And Profile

After the MCP server is available in Codex:

- run the one-time login flow from chat by asking Codex to log in to NotebookLM
- set the NotebookLM MCP profile to `standard`
- restart Codex if the new MCP server does not appear immediately

## Notes

If a NotebookLM answer contradicts live production behaviour, prefer the current
repo implementation and update this brief so future answers stay aligned.
