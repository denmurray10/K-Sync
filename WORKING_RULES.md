# K-Sync Working Rules

## Freshness

- Last reviewed: 2026-04-06
- Current truth: These are the current repo-level operating rules for humans and Codex.
- Legacy context: Older code may reflect pre-Radio.co or pre-NotebookLM habits that this file now supersedes.

## Purpose

This file is the repo-level operating contract for humans and Codex.

Use it when making project-specific changes, especially when a task touches live
radio, editorial automation, media delivery, scheduler behavior, or internal
management tooling.

## Default Working Model

- Treat `core` as the first place to look for product logic.
- Prefer server-rendered Django patterns already in the repo over inventing new frontend architecture.
- Use the `K Beats Radio` NotebookLM notebook before editing project-specific behavior.

## Current Truth Rules

- Radio.co is the current live-song source when enabled.
- Cloudinary is active in current media and voice-over workflows.
- Backblaze B2 references are usually legacy, migration, or fallback context unless the task explicitly says otherwise.

## Safety Rules

- Do not upload raw `.env` or raw `ksync_project/settings.py` into NotebookLM.
- Do not copy live tokens, API keys, or database URLs into docs, prompts, or notebook sources.
- If a file mixes useful architecture with secrets, write a sanitized summary instead of uploading the raw file.

## Before Editing

Check whether the task touches any of these:

- Radio.co live behavior
- Cloudinary media rewriting or uploads
- B2 migration or cleanup utilities
- scheduler jobs or startup behavior
- staff or admin-only APIs
- AI output contracts
- analytics, consent, or SEO shared surfaces

If yes, consult the notebook first and check the matching curated doc.

## Notebook Maintenance Rule

Whenever a meaningful change lands in:

- routes
- templates
- models
- integrations
- scheduler jobs
- deployment/runtime behavior
- operator workflows

update the matching file in `docs/notebooklm/` and re-upload that source to the notebook.

## Validation Rule

After a meaningful notebook update:

- rerun at least one matching question from `docs/notebooklm/NOTEBOOK_VALIDATION_SUITE.md`
- fix weak answers by improving curated docs, not by dumping raw files
