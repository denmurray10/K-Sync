# K-Sync Analytics And Tracking Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map is based on `GoogleTagManagerMiddleware`, tracking-related settings, and current template metadata behavior.
- Legacy context: The repo does not currently expose a large explicit front-end event taxonomy; most tracking is middleware-injected page-level instrumentation.

## Purpose

Use this guide when a task might affect observability, marketing attribution,
consent, or route-level analytics context.

## Current Tracking Stack

### Google Tag Manager

- Injected by `GoogleTagManagerMiddleware`
- Runs only when:
  - `DEBUG` is false
  - `ENABLE_THIRD_PARTY_TRACKING` is true
  - the response is HTML and not streaming

### Meta Pixel

- Also injected by `GoogleTagManagerMiddleware`
- Controlled primarily by `FACEBOOK_PIXEL_ID`
- Includes standard `PageView` handling

### Microsoft Clarity

- Injected conditionally by middleware
- Controlled by `CLARITY_PROJECT_ID`
- Respecting analytics consent stored in local storage

## Consent System

The middleware injects:

- consent mode script
- consent banner styling and behavior
- Clarity consent synchronization logic

Important behavior:

- analytics and ads are denied by default until consent is granted
- consent is stored client-side in local storage
- Clarity loading is gated by consent state

## Page Context Instrumentation

The middleware derives and records page-level context from the request:

- route name
- first path segment as page section
- auth state

This means route names and path structure matter for analytics context, not just
template content.

## Risk Areas

- renaming routes can silently change page analytics context
- disabling tracking in debug can hide production-only behavior
- streaming HTML responses bypass the injection layer
- changing shared layout structure can interfere with where scripts or consent UI appear

## NotebookLM Rules

- If a task touches layout, route names, or page sections, NotebookLM should mention analytics context risk.
- If a task is about a page not loading a tracker, check:
  - `DEBUG`
  - `ENABLE_THIRD_PARTY_TRACKING`
  - HTML versus streaming response
  - whether IDs are configured
- Treat middleware injection as current truth unless a newer explicit tracking system is added.
