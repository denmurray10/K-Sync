# K-Sync Top User Flows

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This guide reflects the current public, authenticated, mixed, and staff/operator journeys in K-Sync.
- Legacy context: Some routes in the same views module are lab or prototype surfaces and should not automatically be treated as primary user journeys.

This file explains the most important public, authenticated, and staff/operator
journeys in K-Sync so NotebookLM can reason about features in terms of product
flows rather than only code structure.

## Purpose

Use this guide when a task is about how a feature behaves end to end.

Typical questions it should help answer:

- what the user is trying to do
- which pages and APIs belong to that journey
- which models and integrations are involved
- whether the flow is public, authenticated, staff-only, or admin-oriented

## Flow Classification At A Glance

NotebookLM should classify the main K-Sync flows like this before answering:

- public flows: live listening, stream selection, public blog reading, contests,
  fan-club browsing, signup capture
- authenticated user flows: onboarding, dashboard use, profile preferences,
  digest preferences, notification viewing, contest entry, fan-club membership
- staff and operator flows: blog generation, link pass, playlist management,
  schedule management, voiceover generation, AI playlist building, AI schedule
  filling
- mixed flows: some systems have a public front end but a staff-managed back
  end, especially contests, fan clubs, radio scheduling, and editorial

If a question asks "who uses this?", answer with one of these categories first.

## 1. Live Listening Flow

### User goal

Listen to K-Beats live, understand what is playing now, explore stream options,
and interact with the live experience.

### Main entry points

- `live/`
- `live/player-popout/`
- `stream/`
- `stream/<slug>/`

### Supporting APIs and helpers

- live status
- live rotate
- live chat
- save-this-moment
- live AI like, commentary, and theme endpoints
- `_build_live_page_context`
- `_resolve_live_page_context`
- `_stream_presets`

### Main dependencies

- Radio.co for current live playback when enabled
- local radio models for fallback and internal curation
- Cloudinary for some media delivery behavior

### Important interpretation

- public live playback is Radio.co-first
- internal radio models still influence surrounding behavior and fallback logic
- this is a public flow with some authenticated engagement features layered on top

## 2. Stream Selection Flow

### User goal

Choose the right stream preset and understand whether a stream is available for
their membership level.

### Main entry points

- `stream/`
- `stream/<slug>/`

### Main concepts

- stream presets
- required tier
- locked versus unlocked stream access
- related stream suggestions

### Important interpretation

- this is not just audio playback; it also expresses product tiering and access rules
- this is a mixed public and authenticated flow because available presets can depend on membership level

## 3. Onboarding, Signup, And Dashboard Flow

### User goal

Create an account, complete onboarding, personalize preferences, and use the
dashboard as the home for a logged-in experience.

### Main entry points

- `signup/`
- `my-station/onboarding/`
- `dashboard/`
- `profile/`

### Supporting concepts

- `UserProfile`
- bias selection
- favorite groups and songs
- digest preferences
- notification and personalization state

### Important interpretation

- `UserProfile` is the core workflow hub for personalization
- dashboard behavior depends on more than auth; it also depends on profile state
- this is an authenticated-user flow

## 4. Blog And Editorial Flow

### User goal

Read K-pop news and editorial content, while internal operators can generate,
link, enrich, and distribute new content.

### Public entry points

- `news/`
- `blog/<slug>/`

### Internal editorial entry points

- `blog/generate/`
- `blog/link-pass/`

### Main workflow

1. fetch news candidates
2. generate long-form article content
3. enrich with images
4. save `BlogArticle`
5. run internal linking
6. queue or publish to social destinations

### Main dependencies

- DeepSeek and DeepSeek Reasoner
- Getimg and image enrichment helpers
- Facebook, X, Pinterest, and optionally Instagram

### Important interpretation

- `BlogArticle` is a workflow hub, not just content storage
- editorial behavior spans generation, SEO, and distribution
- public reading is public-facing, but generation and linking are staff/operator flows

## 5. Playlist And Schedule Management Flow

### User goal

Operators manage local radio tracks, playlists, templates, voiceovers, and
schedule slots for programming and fallback behavior.

### Main entry points

- `playlist-manager/`
- `track-manager/`
- `song-upload-manager/`

### Main APIs

- playlist save, delete, and data APIs
- track delete
- song upload
- schedule save and delete
- schedule template list, save, and delete
- AI playlist generation
- AI schedule fill

### Main models

- `RadioTrack`
- `RadioPlaylist`
- `RadioPlaylistTrack`
- `RadioSchedule`
- `RadioScheduleTemplate`
- `RadioScheduleTemplateSlot`

### Important interpretation

- this is an internal operator flow, not a public consumer flow
- local radio models stay important even when public live playback comes from Radio.co
- this is the main staff/operator flow behind programming and fallback behavior

## 6. Voiceover And DJ Assist Flow

### User goal

Operators create or refine DJ-style playlist moments using AI-generated scripts
and synthesized voice audio.

### Main APIs

- voice listing
- voiceover script generation
- voiceover synthesis
- AI multi-track script assignment

### Main dependencies

- Inworld for voice and synthesis
- DeepSeek as fallback script generator
- Cloudinary for storing synthesized output

### Important interpretation

- this is a production workflow attached to playlist programming, not an isolated experiment
- this is a staff/operator flow

## 7. Contest And Fan Club Flow

### User goal

Join contests, submit entries, participate in fandom mechanics, and engage with
fan-club systems.

### Main entry points

- `contests/`
- `contests/<slug>/enter/`
- `fan-clubs/`
- `fan-clubs/start/`

### Main models

- `Contest`
- `ContestEntry`
- `FanClubMembership`
- `ClubInvitation`
- `ClubLaunch`
- `UserBadge`
- limited-time event models

### Important interpretation

- these are engagement and progression systems, not just static pages
- tier and participation state can affect behavior
- browsing can be public, but participation usually becomes an authenticated-user flow

## 8. Notification And Digest Flow

### User goal

Receive alerts, engagement updates, and optional digest content.

### Main entry points

- notifications APIs
- dashboard-linked notification surfaces

### Main models and systems

- `UserNotification`
- `UserProfile` digest fields
- digest scheduler logic
- periodic email or summary generation paths tied to preference fields

### Important interpretation

- this flow is partly user-facing and partly scheduler-driven
- timezone-aware digest behavior is part of the product experience
- this is mainly an authenticated-user flow supported by background operator/runtime systems

## 9. Signup Capture And Acquisition Flow

### User goal

Join K-Beats before or beyond full account creation through signup or email
capture mechanisms.

### Main entry points

- prelaunch signup API
- email promotion signup API
- regular signup flow

### Main models

- `PreLaunchSignup`
- `EmailPromotionSignup`
- auth user creation plus `UserProfile`

### Important interpretation

- this is acquisition infrastructure, not only marketing decoration
- this starts as a public flow and may later hand off into the authenticated onboarding flow

## Fast Answer Template For NotebookLM

When asked about a K-Sync product feature, prefer this answer order:

1. classify the feature as public, authenticated, staff/operator, or mixed
2. explain the user or operator goal
3. list the main routes, APIs, or management surfaces involved
4. name the key models and external integrations
5. explain any important current-versus-legacy distinction

Important standing interpretations:

- live listening is public and Radio.co-first
- onboarding and dashboard behavior are authenticated and centered on `UserProfile`
- blog reading is public, but editorial generation and distribution are staff/operator workflows
- playlist, schedule, and voiceover tools are staff/operator workflows
- contests and fan clubs are mixed engagement systems
- notifications and digests are authenticated-user experiences backed by scheduler-driven delivery

## How NotebookLM Should Use This Guide

When asked about a feature, NotebookLM should try to answer in flow terms:

- what the user or operator is doing
- which pages and APIs support that journey
- which models and integrations are involved
- whether the flow is public or internal

This helps Codex reason about behavior changes without needing a large code dump
for every product question.
