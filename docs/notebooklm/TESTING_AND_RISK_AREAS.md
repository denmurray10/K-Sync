# K-Sync Testing And Risk Areas

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This summary reflects the current `core/tests.py` suite plus the broader repo shape.
- Legacy context: The repo contains many production-like surfaces that do not yet have equally deep automated coverage.

## Purpose

Use this guide when a change needs a risk review or when NotebookLM should warn
that a feature is under-tested or operationally fragile.

## Areas With Current Automated Coverage

The current Django test suite covers:

- `BlogArticle` sanitization behavior
- site icons and manifest redirects
- fan-club tier gating and event badge logic
- comeback timeline performance and drawer payloads
- comeback-to-news sync behavior
- What Just Landed reel preview, scheduling, and publish flows
- Facebook article posting and queue behavior
- Facebook Reels scheduler registration and publish preference
- Radio.co live status and live-page context behavior

## Areas That Look Under-Tested

- login, signup, onboarding, and dashboard flows
- most staff dashboard and manager UI behavior
- many JSON endpoints outside the covered fan-club, reel, and Radio.co areas
- AI endpoint output contracts
- X, Instagram, and Pinterest publishing flows
- management commands and migration utilities
- template rendering coverage across the full surface area
- environment-toggle combinations and deploy-mode behavior

## High-Risk Change Surfaces

- scheduler startup in `AppConfig.ready()`
- current Radio.co behavior versus local radio fallback logic
- Cloudinary and B2 toggles
- admin-only JSON manager endpoints
- social publishing jobs and reel scheduling
- live page context helpers
- any change that affects tracking middleware or shared SEO partials

## Why These Areas Are Risky

- many flows depend on external providers
- some features are controlled by settings flags rather than explicit dependency injection
- prototype and production surfaces coexist in the same views module
- secret-bearing defaults in settings make naive local reasoning risky

## NotebookLM Rules

- If a task touches a weakly tested area, say so before proposing edits.
- If a task touches a scheduler-driven or provider-driven flow, mention both code and operational validation needs.
- Do not overstate confidence just because there is some adjacent coverage in the repo.
