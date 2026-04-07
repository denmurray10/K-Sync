# K-Sync Operations And Deployment Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map reflects current runtime, scheduler, hosting, and deployment assumptions in the repo.
- Legacy context: Some deployment defaults and toggles remain shaped by Heroku-style assumptions and older service integrations.

This file summarizes runtime behavior, deployment assumptions, scheduler
startup, environment toggles, and the most important operational commands.

## Runtime Shape

K-Sync runs as a Django web application. The repo contains:

- `Procfile` with `web: gunicorn ksync_project.wsgi`
- startup logic in `core.apps.CoreConfig.ready()`
- background scheduling via APScheduler inside the app process

This means the application combines request handling and scheduled-job startup in
the web process rather than separating them into a dedicated worker in this repo.

## Scheduler Startup Rules

The scheduler starts only when:

- the command is `runserver`
- the `DYNO` environment variable begins with `web`

For local development:

- `RUN_MAIN` is used to avoid duplicate scheduler startup during Django reloads

Implication:

- scheduler behavior is tightly coupled to how the app is launched
- changes to runtime startup logic can affect both local dev and deployed cron-like behavior

## Database Assumptions

The project supports:

- PostgreSQL in deployed environments
- SQLite locally when `DJANGO_USE_SQLITE` is enabled

The settings file currently uses env-driven selection and Neon-oriented
PostgreSQL defaults, but those raw values should not be treated as safe
notebook material. NotebookLM should understand only the sanitized behavior:

- local development may use SQLite
- deployed behavior expects PostgreSQL

## Deployment Indicators

The repo contains multiple signals that point to deployment and hosting concerns:

- `Procfile` for Gunicorn web startup
- environment-based configuration in `.env.example`
- a deployment checklist doc
- host, tracking, and social-posting toggles in settings

The project also uses site and domain-oriented configuration such as `SITE_URL`,
tracking IDs, and stream or request widget settings.

NotebookLM should summarize deployment cautiously:

- Heroku-style deployment is supported by the repo shape
- Gunicorn is the web entrypoint
- environment variables control service integrations and runtime toggles
- exact production hosting details should come from current deployment docs and operator knowledge

## Important Operational Feature Toggles

Environment-driven toggles materially change runtime behavior for:

- Radio.co integration
- third-party tracking
- Facebook posting and reel behavior
- digest dispatch
- Cloudinary fetch rewriting for audio and images
- B2 auto-sync behavior

Any code change in these areas should be evaluated with environment assumptions
in mind rather than by looking only at local defaults.

## Background Jobs And Automation

The scheduler coordinates multiple recurring jobs, including:

- ranking generation
- calendar sync
- blog generation
- user digest dispatch
- Facebook post and comment jobs
- social and editorial queue processing
- media-related maintenance tasks

Some jobs call helper logic in `core.views`, which means "view code" can be part
of operational automation as well as request handling.

## Digest Behavior

User digests are timezone-aware and opt-in. The digest logic:

- resolves per-user timezones
- collects release, birthday, and ranking-jump content
- delivers push notifications and optionally email
- tracks the last sent date to avoid repeat sends

NotebookLM should treat digests as part of the application's scheduled product
behavior, not just a utility script.

## Management Commands

The repo includes management commands for:

- media URL exports and migration tasks
- B2 and image normalization or migration work
- syncing external profile or artwork data
- seeding events
- sending user digests

These commands are important operational tools, but not all of them reflect the
current primary production path. Commands involving B2 should be treated as
legacy, migration, or support operations unless a task specifically targets them.

## Deployment And Notebook Guidance

NotebookLM should answer deployment questions with these constraints:

- describe runtime behavior and scheduler startup accurately
- note the Gunicorn web entrypoint and Heroku-style process hints
- distinguish current operational systems from legacy utility commands
- avoid quoting or depending on secret-bearing settings values
