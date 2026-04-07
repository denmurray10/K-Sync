# K-Sync Decision Log

## Freshness

- Last reviewed: 2026-04-06
- Current truth: These entries summarize the current architectural and product decisions visible in the repo.
- Legacy context: Some decisions were made to preserve older systems during migration rather than to represent the ideal end state.

## Purpose

Use this file when NotebookLM needs to explain why the codebase looks the way it
does instead of only describing what it does.

## Current Decisions

### 1. Keep the product centered in one `core` app

Decision:
Most product logic, routes, models, templates, APIs, and operator surfaces live
inside the `core` Django app.

Why it matters:

- feature ownership is easier to find in one place
- NotebookLM should check `core` first for almost every product question
- implementers should avoid inventing new app boundaries unless there is a real architectural reason

### 2. Stay server-rendered instead of moving to a SPA

Decision:
K-Sync is primarily a server-rendered Django application with templates, small
JS enhancements, and Tailwind build outputs.

Why it matters:

- template ownership still matters
- route, template, and context behavior are tightly coupled
- UI changes often require server-side context understanding, not just frontend work

### 3. Run the scheduler inside the web process

Decision:
APScheduler is started from `core.apps.CoreConfig.ready()` for local `runserver`
and Heroku-style web dynos.

Why it matters:

- scheduler behavior is coupled to app boot
- startup side effects matter
- deploy, reload, or debug changes can affect background behavior

### 4. Make Radio.co the primary live source

Decision:
Radio.co is the current source of truth for live playback when enabled.

Why it matters:

- live metadata should be interpreted as Radio.co-first
- NotebookLM should not default to B2-backed track streaming as the live path
- live page changes should consider Radio.co payloads, station info, and request widget behavior

### 5. Keep local radio models even after Radio.co adoption

Decision:
Local radio models remain important for internal curation, playlists, schedules,
voiceovers, and fallback logic.

Why it matters:

- the repo has both current and legacy-seeming radio systems because they still serve different jobs
- implementers should not delete local radio logic just because Radio.co is live

### 6. Use Cloudinary as the active media optimization layer

Decision:
Cloudinary is active for current image/audio delivery rewriting and voice-over
storage, even though B2 utilities still exist.

Why it matters:

- Cloudinary-related behavior is current production logic
- B2 references are often migration, support, or fallback context

### 7. Keep curated notebook docs as the safe project brain

Decision:
NotebookLM should learn from curated summaries, not raw secret-bearing repo
files.

Why it matters:

- raw `settings.py` and `.env` are unsafe upload material
- when NotebookLM gives a weak answer, the fix is usually a better curated doc

### 8. Keep one canonical notebook for now

Decision:
`K Beats Radio` remains the single project brain notebook until a domain becomes
too noisy.

Why it matters:

- context stays centralized
- maintenance stays lighter
- any future split should be deliberate, not a reaction to ordinary growth

## Future Split Candidates

If the notebook eventually becomes noisy, the most likely first split domains
are:

- editorial and AI workflows
- operations and deployment
- integrations and vendor docs
