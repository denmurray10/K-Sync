# K-Sync AI And Editorial Workflows

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This doc reflects the current AI, editorial, playlist, and social workflow interpretation for K-Sync.
- Legacy context: Provider names and automation details may outlive individual prompts or model choices, so treat provider wiring as more stable than exact prompt wording.

This file explains how AI-assisted generation, editorial content, voiceovers,
playlists, and social workflows fit together in K-Sync.

## AI Provider Roles

### DeepSeek

DeepSeek is the main general-purpose text generation path in the repo.

It is used for:

- ranking generation
- radio commentary and themes
- AI playlist ordering
- AI schedule fill behavior
- voice-over scripting fallback
- general K-pop assistant-style prompting

The repo uses both:

- `deepseek-chat` for normal generation
- `deepseek-reasoner` for heavier long-form generation

### Inworld

Inworld is used for radio voice and speech workflows when configured.

It powers:

- DJ voice-over script generation
- voice listing
- voice synthesis via TTS

Synthesized audio is then uploaded to Cloudinary and returned as playlist-ready
track data.

### Getimg

Getimg is used for image generation via a Flux Schnell text-to-image endpoint.

This is a narrower workflow than the DeepSeek and Inworld integrations.

## Blog And Editorial Generation

The blog pipeline combines:

- news fetching
- duplicate and near-duplicate filtering
- long-form AI article generation
- image fetch and upload enrichment
- internal linking hints
- queue-based social publishing

The core article-generation helper is `_do_blog_generate()`.

Its behavior includes:

- pulling news items
- skipping duplicates and near-duplicates
- generating original long-form K-pop journalism in HTML
- adding internal link hints to existing K-Beats content
- enriching articles with image lookup and upload
- creating `BlogArticle` records
- queueing or optionally immediately posting to social channels

NotebookLM should describe this as a structured editorial pipeline, not simply
"AI writes blog posts".

## Internal Linking Pass

There is a post-generation internal-link pass that scans stored article bodies
and injects links to sibling articles where titles are mentioned naturally.

This matters because:

- editorial SEO is part of the workflow
- content generation and content refinement are separate phases

## Social Publishing

Social workflows are tied to `BlogArticle` metadata and scheduler jobs.

Current social concerns include:

- Facebook post queueing
- homepage commenting
- reels generation and publishing state
- optional immediate posting toggles
- X posting
- Pinterest posting

NotebookLM should describe social as an attached operational and editorial
system, not as unrelated helper code.

## Ranking Generation

Ranking generation exists both as:

- scheduled ranking jobs
- on-demand AI ranking endpoints

The ranking prompts are specific to K-pop charts and expect structured JSON.
This means prompt and output stability matters more than "creative prose" when
changing ranking features.

## Live AI Features

The live radio experience has AI-enhanced features for:

- saving likes and making artist suggestions
- generating DJ commentary blurbs
- generating mood palettes
- enriching live-track payloads

These are user-facing radio experience features, not just internal tooling.

## Playlist And Schedule AI

There are AI-assisted internal tools for radio programming:

- AI playlist generation
- AI schedule fill
- DJ voice-over script generation
- multi-track voice-over script assignment

The design pattern is:

- select or prefilter candidate tracks deterministically
- use AI to improve ordering, scripting, or framing
- keep output shapes constrained so manager UIs can use the result directly

This is important for future edits:

- AI is used as an enhancer, not as the sole source of truth for all scheduling decisions
- local radio models still carry the final operational structure

## NotebookLM Interpretation Rules

When asked about AI and editorial behavior, NotebookLM should answer with these ideas:

- DeepSeek is the main general text, ranking, and editorial engine
- DeepSeek Reasoner is used for long-form article quality
- Inworld handles DJ voice and synthesis workflows
- Getimg is used for image generation
- AI outputs are usually wired into structured product workflows rather than
  being one-off experiments
