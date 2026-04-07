# K-Sync Integrations Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map reflects the integrations currently visible in settings, scheduler code, and product workflows.
- Legacy context: Some integrations still exist mostly for migration, optional publishing, or inactive toggles rather than constant production use.

This file explains the major external integrations used by K-Sync and what each
one is responsible for.

## Purpose

Use this map when a task touches a third-party service and you need to know:

- whether the integration is current or legacy
- what part of the app depends on it
- whether it affects public behavior, internal tools, or both

## Radio.co

### Role

Radio.co is the current primary live song source for K-Sync.

### Where it matters

- public live playback status
- current track resolution
- recently played track data
- station status
- stream listen URL
- request widget behavior

### Important interpretation

- Radio.co is current production truth for live playback when enabled.
- Local radio models still matter for internal tools and fallback logic.
- Do not describe B2 as the current live song source when Radio.co is active.

## Cloudinary

### Role

Cloudinary is an active media delivery and storage integration.

### Where it matters

- optional remote fetch rewriting for audio URLs
- optional remote fetch rewriting for image URLs
- upload destination for synthesized voice-over audio
- selected image optimization and delivery flows

### Important interpretation

- Cloudinary is current and active.
- It is not only a future or optional concept in the repo.
- It often works alongside Radio.co and local models rather than replacing them.

## Backblaze B2

### Role

Backblaze B2 is legacy or secondary context in the current project state.

### Where it still appears

- migration and normalization commands
- older URL rewriting helpers
- environment examples
- historical media handling logic

### Important interpretation

- Treat B2 as migration, fallback, or historical storage context unless a task
  is explicitly about it.
- Do not lead with B2 when explaining current live playback.

## DeepSeek

### Role

DeepSeek is the primary general AI generation provider in the repo.

### Where it matters

- ranking generation
- blog and article generation
- playlist sequencing
- schedule fill
- radio commentary and theme generation
- fallback voice-over scripting

### Important interpretation

- `deepseek-chat` handles normal generation.
- `deepseek-reasoner` is used for long-form editorial work.
- Many features rely on stable structured outputs, not open-ended prose.

## Inworld

### Role

Inworld handles DJ voice and speech-related workflows.

### Where it matters

- voice listing
- voice-over script generation
- text-to-speech synthesis

### Important interpretation

- Inworld is part of the current radio tooling story.
- Synthesized audio is stored via Cloudinary afterward.

## Getimg

### Role

Getimg powers image generation.

### Where it matters

- AI image generation endpoint
- editorial/media support workflows

### Important interpretation

- It is narrower in scope than DeepSeek or Inworld.
- It should not be treated as the core content-generation engine.

## Social Platforms

### Facebook

Used for:

- queued article posting
- homepage comments
- reels generation and publishing states

### X

Used for:

- queued or optionally immediate article posting

### Pinterest

Used for:

- article pin creation when images are available

### Instagram

Used for:

- post publishing when configured

### Important interpretation

- Social publishing is attached to the editorial pipeline and scheduler behavior.
- These are not isolated scripts; they are part of the content operations layer.

## Kpopping And iTunes

### Kpopping

Used for:

- comeback and calendar-related data sync

### iTunes

Used for:

- artwork lookup and enrichment for some ranking or media flows

## Integration Priority Guidance

NotebookLM should use this priority when describing the current stack:

1. Radio.co for current live playback
2. Cloudinary for active media and synthesized audio handling
3. DeepSeek and Inworld for AI/editorial and voice workflows
4. Social platforms as editorial distribution channels
5. B2 only as legacy or migration context unless explicitly requested
