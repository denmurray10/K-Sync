# K-Sync Data Model Guide

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This guide reflects the current model groups and their product responsibilities.
- Legacy context: Some models continue to support fallback, migration, or historical workflows even when they are not the main live path.

This file summarizes the most important model groups in K-Sync and how they
relate to the product.

## Purpose

Use this guide when the task needs model-level reasoning but uploading the full
raw model file would be too noisy or too risky for NotebookLM.

## Most Important Model Groups At A Glance

NotebookLM should group the project models like this:

- content and discovery models
- user and engagement models
- radio and programming models
- request, chat, and moderation models
- contests, clubs, badges, and event models
- signup and acquisition models

It should not answer model questions by falling back to the radio integration
story unless the question is specifically about live playback.

## Content And Discovery Models

### `Ranking`

Stores generated ranking snapshots by timeframe and date.

Typical role:

- powers chart-style ranking views
- supports scheduled and on-demand ranking generation

### `ComebackData`

Stores comeback calendar data by year and month.

Typical role:

- powers comeback timeline and calendar experiences
- supports digest and event-style content

### `KPopGroup` and `KPopMember`

These define the artist and member structure used across idol discovery, fan
features, and group-linked experiences.

Typical role:

- idol pages
- fan clubs
- onboarding and preferences
- related editorial context

### `BlogArticle`

This is the main editorial content model.

Typical role:

- stores generated or curated articles
- tracks image URLs and source metadata
- carries social-posting state
- stores Facebook post and reel lifecycle fields

Important interpretation:

- `BlogArticle` is not just static content storage
- it is a workflow hub for editorial and social distribution
- it stores both article content and operational publishing state

## User And Engagement Models

### `UserProfile`

Stores the user-facing preference and personalization layer.

Typical role:

- bias and favorite-group data
- onboarding state
- digest settings
- timezone-aware digest preferences

Important interpretation:

- `UserProfile` is a personalization and notification-preference hub, not just a profile record

### `FavouriteSong`

Tracks user song saves and favorites.

### `LivePoll` and `LivePollOption`

Support fan polls and tier-aware early access behavior.

### `RadioTrackPlay`

Records play events for user listening behavior and badge logic.

### `UserNotification`

Stores alert, social, and invitation notifications.

## Radio And Programming Models

### `RadioTrack`

The foundational local radio track model.

Typical role:

- title, artist, album art, duration, audio URL
- optional AI payload for live radio enrichment
- internal playlist and scheduling workflows

Important interpretation:

- local radio models remain important even though Radio.co is the current live
  source when enabled
- `RadioTrack` is a workflow model used by managers, playlists, schedules, AI,
  and fallback radio behavior

### `RadioStationState`

Stores current, up-next, and recently played state for local fallback radio.

Important interpretation:

- this is operational state, not just archival data

### `RadioPlaylist`

Defines a playlist container and default voice configuration.

Important interpretation:

- this is a workflow hub for internal radio curation

### `RadioPlaylistTrack`

Defines ordered track membership plus voice-over settings for playlist entries.

Important interpretation:

- this is a workflow hub because it carries sequencing and voice-over behavior,
  not just a many-to-many join

### `RadioSchedule`

Stores weekly schedule slots mapped to playlists.

Important interpretation:

- this is a workflow hub for programming and public schedule behavior

### `RadioScheduleTemplate` and `RadioScheduleTemplateSlot`

Support reusable schedule layout patterns.

Important interpretation:

- these models drive internal management tools, schedule rendering, and fallback
  operational radio logic
- they should be treated as workflow models, not passive configuration only

## Request, Chat, And Moderation Models

### `SongRequest`

Stores user song requests.

Important interpretation:

- this is a lightweight workflow model tied to listener interaction

### `LiveChatMessage`

Stores live chat messages tied to authenticated users.

### `ChatBlockedTerm`

Stores blocked moderation terms for chat.

## Contest, Club, And Event Models

### `Contest` and `ContestEntry`

Support giveaway and challenge workflows.

Important interpretation:

- `Contest` is a workflow hub for active campaign state, while `ContestEntry`
  stores submissions

### `FanClubMembership`

Connects users to groups with tiered membership behavior.

Important interpretation:

- this is a workflow model because tier affects perks and product behavior

### `ClubInvitation`, `ClubLaunch`, and `UserBadge`

Support club growth, identity, and achievement mechanics.

### `LimitedTimeEvent`, `EventBadgeDrop`, and `EventParticipation`

Support timed event systems, badge drops, and participation tracking.

## Signup And Acquisition Models

### `PreLaunchSignup`

Captures prelaunch signups.

### `EmailPromotionSignup`

Captures newsletter or promotional signups.

## Model Interpretation Rules For NotebookLM

NotebookLM should use these heuristics:

- `core.models` contains both current operational models and legacy-adjacent
  structures, so model presence alone does not define the active production path
- current live playback truth should still be described as Radio.co-first
- local radio models are still active for management, scheduling, and fallback logic
- `BlogArticle` and radio models should be treated as workflow hubs, not passive tables
- `UserProfile`, `FanClubMembership`, `Contest`, and `RadioSchedule` are also
  workflow-heavy models, not just storage records
