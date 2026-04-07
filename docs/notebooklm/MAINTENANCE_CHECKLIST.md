# K-Sync NotebookLM Maintenance Checklist

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This checklist defines the current semi-automated maintenance process for the `K Beats Radio` notebook.
- Legacy context: Earlier maintenance was ad hoc and lighter-weight than the workflow defined here.

This file defines how to keep the `K Beats Radio` notebook accurate over time.

## Goal

The notebook should stay useful as a project brain without becoming a noisy dump
of stale raw files.

The rule is simple:

- update curated docs when project truth changes
- keep raw sensitive files out
- prefer better summaries over more files

## Source Scoring Rule

Prefer sources in this order:

1. curated docs in `docs/notebooklm/`
2. sanitized root docs such as `WORKING_RULES.md` and `RELEASE_CHECKLIST.md`
3. official vendor docs that match active live workflows
4. low-risk raw repo files only when they are uniquely useful

## Authoritative Sources

For NotebookLM purposes, the authoritative internal sources are:

- the curated docs in `docs/notebooklm/`
- `BRAND_GUIDELINES.md`
- `DEPLOYMENT_ENV_CHECKLIST.md`
- `WORKING_RULES.md`
- `RELEASE_CHECKLIST.md`
- selected low-risk repo docs that do not contain secrets

Raw code is still the execution truth, but the notebook should rely on curated
docs to explain that truth in a stable, safe way.

## When To Update The Notebook

Update the notebook docs whenever any of these change meaningfully:

- architecture boundaries or route families
- current live audio source or playback path
- Cloudinary and media handling
- deployment and runtime assumptions
- scheduler or background-job behavior
- AI providers, prompts, or output contracts
- staff or admin manager workflows
- editorial or social publishing pipelines
- repo-wide conventions Codex should follow
- permissions, route ownership, template ownership, or API ownership
- settings behavior, validation prompts, or release workflow
- design system, component patterns, page patterns, UX rules, or copy tone

## Update Process

1. Identify which knowledge area changed.
2. Update the matching curated doc in `docs/notebooklm/`.
3. Check the doc for secrets, stale assumptions, or ambiguous "current vs legacy" wording.
4. Update the freshness marker:
   - `Last reviewed`
   - `Current truth`
   - `Legacy context`
5. Re-upload the changed doc into the `K Beats Radio` notebook.
6. Add a short note to `docs/notebooklm/NOTEBOOK_CHANGELOG.md` if the change is meaningful.
7. Re-run at least one NotebookLM validation question for the affected area.

## Monthly Validation Pass

At least monthly:

1. run the prompts in `docs/notebooklm/NOTEBOOK_VALIDATION_SUITE.md`
2. collect any weak or incorrect answers
3. improve the matching curated docs
4. re-upload only the changed sources

## Validation Standard

After a meaningful update, NotebookLM should still answer these kinds of
questions correctly:

- what is current production behavior?
- what is legacy or migration-only context?
- which app, model, or route group owns the feature?
- which external service is actually involved?
- what rules should Codex follow before editing that area?
- which route, template, API, or permission boundary owns the feature?
- whether the feature design still fits K-Beats brand, UX, and copy patterns

## Anti-Patterns To Avoid

- uploading `.env`
- uploading raw `settings.py`
- uploading broad source dumps "just in case"
- leaving legacy behavior undocumented so NotebookLM confuses it with current production truth
- fixing notebook problems only with prompt wording instead of improving source docs
- skipping the freshness marker when a doc changes

## Workflow Support

Use `.github/PULL_REQUEST_TEMPLATE.md` as the lightweight "notebook update required?"
gate for future changes.

## Long-Term Strategy

The current default is one main notebook.

Only split the notebook later if one domain becomes too noisy, for example:

- a very large vendor-doc corpus
- a separate operations runbook set
- a dedicated AI or analytics subsystem

Until then, keep one primary project brain and maintain it with curated docs.
