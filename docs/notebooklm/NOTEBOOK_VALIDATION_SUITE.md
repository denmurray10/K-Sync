# K-Sync Notebook Validation Suite

## Freshness

- Last reviewed: 2026-04-06
- Current truth: These are the current recommended validation prompts for the `K Beats Radio` notebook.
- Legacy context: If the notebook later splits into specialist notebooks, this suite should be split too.

## Purpose

Use this file for monthly validation or after any meaningful notebook update.

## Core Validation Prompts

- Summarize the K-Sync architecture and the role of the `core` app.
- Explain the current live radio path, including Radio.co and local fallback logic.
- Describe where Cloudinary fits into media delivery and how it differs from legacy B2 references.
- Which routes and templates own the live listening, stream selection, and onboarding journeys?
- What permissions or staff boundaries apply to this feature?
- Which management commands are safe, active, migration-only, or potentially risky?
- Which env settings control this behavior, and is the system current or legacy?
- Which API endpoints and templates are touched by this workflow?
- What analytics, SEO, or tracking behavior could break if we change this page?
- What tests are weak here, and what parts of this feature are brittle?
- What current-versus-legacy distinction matters before editing this code?

## Validation Standard

Good answers should:

- be project-specific, not generic Django advice
- identify the correct audience boundary for the feature
- mention the relevant routes, templates, models, integrations, and commands
- separate current production truth from migration or legacy context

## Correction Rule

If an answer is weak:

- improve the matching curated doc
- re-upload the improved doc
- rerun the same question

Do not try to solve repeated weak answers by dumping raw files into NotebookLM.
