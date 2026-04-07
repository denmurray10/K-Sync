# K-Sync Runbook

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This runbook reflects the current operational interpretation of deploy, runtime, and incident behavior.
- Legacy context: Some operational notes still account for older B2-era or migration-support workflows.

This runbook is the practical operator guide for common project work in K-Sync.
It is written for NotebookLM and Codex so they can reason about likely safe
actions before touching the repo.

## Purpose

Use this runbook when the task is operational rather than purely structural.

Typical use cases:

- understanding what to check before deployment
- reasoning about scheduler behavior
- deciding whether a bug is local-only or runtime-specific
- identifying the safest area to inspect first during incidents

## Local Development

### App startup

- The web entrypoint is Django running through the project config in `ksync_project/`.
- The scheduler can start during local `runserver`, but only in the active
  reload process because `RUN_MAIN` is checked.
- Local development may use SQLite if `DJANGO_USE_SQLITE` is enabled.

### What to verify first

For local breakages, check:

- whether the issue is route or template level inside `core`
- whether an environment toggle changes the code path
- whether the scheduler is running when you expect it to
- whether the feature depends on Radio.co, Cloudinary, or an AI provider

## Deployment Runtime

### Process model

- The repo uses `web: gunicorn ksync_project.wsgi` in `Procfile`.
- Scheduler startup is tied to the web process through `CoreConfig.ready()`.
- A Heroku-style `DYNO` environment is explicitly checked for web dynos.

### What this means operationally

- Background jobs are coupled to the web runtime.
- Startup problems can affect both request handling and scheduled behavior.
- Runtime bugs may differ between local `runserver` and deployed Gunicorn.

## Safe Deployment Checks

Before or after deployment, confirm:

- required env vars are present
- Radio.co values are correct if live playback should use Radio.co
- Cloudinary credentials are present if voiceover synthesis or media rewriting is expected
- third-party tracking toggles match the intended environment
- social posting toggles match the intended environment
- the site URL and domain assumptions are correct

Use `DEPLOYMENT_ENV_CHECKLIST.md` for the baseline checklist and this runbook
for behavioral interpretation.

## Common Incident Paths

### Live radio looks wrong

Check in this order:

1. Is Radio.co enabled in the active environment?
2. Are station ID and listen URL configured?
3. Is the issue in Radio.co mode or local fallback mode?
4. Is media URL rewriting through Cloudinary changing the delivered URL?
5. Is the problem only in internal manager tools, or also in public live pages?

### Playlist or schedule tools look wrong

Check:

1. `RadioTrack`, `RadioPlaylist`, and `RadioSchedule` assumptions
2. whether the issue is in manager APIs or in public rendering
3. whether AI-generated outputs are malformed or the local save path is wrong
4. whether the problem belongs to fallback radio logic rather than Radio.co mode

### Blog or editorial automation looks wrong

Check:

1. whether `_do_blog_generate()` is being invoked manually or by scheduler
2. whether AI generation succeeded but post-processing failed
3. whether image enrichment or social posting is the failing phase
4. whether the queue behavior is expected or immediate posting toggles were changed

### Voiceover generation looks wrong

Check:

1. Inworld configuration and voice availability
2. Cloudinary upload behavior
3. output shape returned to the playlist manager
4. whether the failure is script generation or audio synthesis

## Scheduler Awareness

The scheduler is responsible for multiple product behaviors, including:

- rankings
- calendar sync
- blog generation
- digest dispatch
- social publishing jobs

When debugging time-based behavior, always ask:

- is the scheduler actually running?
- is this a startup issue or a job-logic issue?
- is the current environment supposed to run this job?

## When To Use NotebookLM First

Codex should consult the notebook before acting when the task involves:

- current-vs-legacy confusion
- runtime toggles
- deployment assumptions
- radio/media ownership
- AI/editorial workflows
- staff/admin manager behavior

## Escalation Rule

If production truth is unclear, prefer:

1. the curated notebook docs
2. the live code path in the repo
3. operator confirmation

Do not trust legacy utility scripts over current curated docs when they conflict.
