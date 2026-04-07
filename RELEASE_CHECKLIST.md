# K-Sync Release Checklist

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This is the current sanitized release checklist for K-Sync.
- Legacy context: Older deployment habits may not have included notebook updates, validation prompts, or route-risk reviews.

## Purpose

Use this checklist for production-minded changes. It is intentionally sanitized
and should be safe to upload to NotebookLM.

## Before Release

- confirm which user flows are changing
- confirm whether the change touches:
  - live radio
  - scheduler jobs
  - social publishing
  - fan-club or event logic
  - analytics or consent behavior
  - SEO-critical templates or metadata
- review environment dependencies for the affected feature
- make sure any required static assets or Tailwind builds are up to date

## Environment Review

- verify the required provider settings exist in the hosting environment
- confirm tracking flags and live-service toggles are correct for production
- double-check any new env variables have sanitized documentation

## Runtime Review

- consider scheduler startup side effects
- consider whether the feature behaves differently in debug versus production
- consider whether external providers are required for the changed path

## Content And Media Review

- if the change affects media delivery, verify current Cloudinary and Radio.co assumptions
- if the change affects legacy media utilities, confirm whether B2 support is still required
- if the change affects editorial or social automation, confirm queue and publish timing assumptions

## Notebook Review

- update the matching doc in `docs/notebooklm/` if project truth changed
- re-upload changed notebook docs
- rerun the relevant validation prompts from `docs/notebooklm/NOTEBOOK_VALIDATION_SUITE.md`

## After Release

- smoke-test the affected route or API
- verify no unexpected scheduler or provider errors appear
- verify analytics and SEO-critical pages still render correctly if applicable
- record any notebook updates in `docs/notebooklm/NOTEBOOK_CHANGELOG.md`
