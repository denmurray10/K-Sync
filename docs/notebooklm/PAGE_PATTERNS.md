# K-Sync Page Patterns

## Freshness

- Last reviewed: 2026-04-07
- Current truth: These patterns reflect the main public, member, and operator page types currently visible in the repo.
- Legacy context: Prototype and lab pages may intentionally exaggerate or test variants outside these defaults.

## Purpose

Use this guide when designing new pages or reshaping existing ones so layouts
follow recognizable K-Sync patterns.

## Public Marketing And Discovery Pages

Examples:

- homepage
- charts
- idols
- news
- presenters
- pricing

Pattern:

- bold hero or section opener
- high-contrast editorial composition
- a few strong modules instead of equal-weight grids
- strong CTA path toward live radio, signup, or deeper content

## Live Experience Pages

Examples:

- `live/`
- `stream/`
- `stream/<slug>/`

Pattern:

- now-playing or primary listening block first
- real-time feeling through motion, chips, queue state, or live metadata
- interaction areas grouped around playback, not scattered across the page
- optional AI or community modules should support the live core, not distract from it

## Onboarding And Signup Pages

Examples:

- `signup/`
- `my-station/onboarding/`

Pattern:

- one strong onboarding promise
- a focused form or choice task
- visible benefit framing
- minimal distractions
- clear sense of progress or next step

## Member Dashboard Pages

Examples:

- `dashboard/`
- profile and personalization surfaces

Pattern:

- personalized hero or welcome header
- compact stats bar
- modular but still branded content blocks
- quick actions visible early

## Editorial And Article Pages

Examples:

- `news/`
- `blog/<slug>/`
- comeback-linked editorial pages

Pattern:

- headline-first presentation
- clear metadata and article hierarchy
- supporting image or media without making the page feel like a blog template clone
- space for internal links and related discovery

## Operator Tool Pages

Examples:

- playlist manager
- track manager
- song upload manager

Pattern:

- dense control surface
- strong tab or workspace structure
- metrics and status visible near the top
- large working pane plus secondary control areas
- low-friction editing over decorative design

## Community And Participation Pages

Examples:

- fan clubs
- contests
- events

Pattern:

- clear group identity
- prominent reward, status, or participation state
- balance between browsing and action
- tier or membership cues should feel meaningful, not hidden

## NotebookLM Rules

- When asked to design a new page, classify it into one of these page families first.
- Reuse the matching page pattern before inventing a new layout structure.
- If a page mixes two families, identify the dominant one and keep the secondary pattern subordinate.
