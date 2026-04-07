# K-Sync Visual Reference Set

## Freshness

- Last reviewed: 2026-04-07
- Current truth: This file summarizes the current visual reference captures for the main K-Beats public and operator-adjacent surfaces.
- Legacy context: If public pages or operator entry points are redesigned, this file and the screenshots it references should be refreshed together.

## Purpose

This file turns a small screenshot pack into a reusable NotebookLM-friendly design
reference. It should help future design and feature work stay aligned with the
actual current UI, not just the written design rules.

The current screenshot set lives in:

- `output/playwright/design-refs/home.png`
- `output/playwright/design-refs/live.png`
- `output/playwright/design-refs/signup.png`
- `output/playwright/design-refs/staff-login.png`

These should be uploaded to NotebookLM alongside this markdown file whenever the
major public or operator-facing surfaces change materially.

## Visual System Snapshot

Across the current public experience, K-Beats presents itself as a premium,
broadcast-inspired K-pop platform with:

- predominantly black or near-black backgrounds
- hot pink as the primary action/accent color
- cyan as the secondary accent and system contrast color
- high-contrast white headline moments
- sharp-edged cards, buttons, and layout framing
- oversized editorial hero typography for public storytelling surfaces
- denser, flatter, more task-focused styling for operator entry points

## Reference Screens

### Home page

Reference file:

- `output/playwright/design-refs/home.png`

Key characteristics:

- A cinematic homepage with a giant headline lockup and neon-outlined editorial
  typography.
- Navigation stays slim and uppercase so the hero remains dominant.
- The right rail reinforces the broadcast identity with live-now, on-deck, and
  upcoming content modules.
- Primary actions use hot pink fills, while the rest of the page relies on
  restrained borders, glow, and contrast instead of heavy color blocking.

Design takeaway:

- Public landing surfaces should feel like a broadcast poster or launch screen,
  not a generic app dashboard.

### Live experience

Reference file:

- `output/playwright/design-refs/live.png`

Key characteristics:

- The live page softens the hard-black base with a deep magenta atmospheric
  gradient.
- The page foregrounds the now-playing object, its social/share state, and
  immediate listening/request actions.
- Broadcast utility information is still visible, but it is composed into a
  stylized entertainment surface rather than a plain utility dashboard.

Design takeaway:

- Live-related pages should feel reactive, event-like, and emotionally close to
  the current track or room energy.

### Signup page

Reference file:

- `output/playwright/design-refs/signup.png`

Key characteristics:

- The signup page keeps the public brand language, but narrows it into a
  conversion-focused split layout.
- Large editorial typography sells the emotional promise of the account, while
  the form itself is framed in cyan and pink accents.
- Supporting benefits are short, scannable, and icon-led rather than verbose.

Design takeaway:

- Onboarding pages should preserve the public brand drama while making the next
  action simple, direct, and confidence-building.

### Staff login

Reference file:

- `output/playwright/design-refs/staff-login.png`

Key characteristics:

- The staff login page strips the experience back to a sparse, centered sign-in
  surface.
- The same brand tokens remain, but they are used more sparingly.
- The page communicates restricted access and seriousness rather than discovery
  or entertainment.

Design takeaway:

- Operator and admin-adjacent entry points should feel branded but quieter, with
  clarity taking priority over spectacle.

## Public Versus Operator Visual Split

Use the screenshot set to preserve this distinction:

- Public pages: more cinematic, more editorial typography, more atmosphere, and
  more entertainment framing.
- Conversion pages: still branded and dramatic, but more disciplined around the
  action path.
- Operator entry points: stripped back, centered, and task-first, with less
  motion and fewer competing visual layers.

## When To Refresh This Set

Refresh the screenshots and this file when any of the following changes:

- the homepage hero or navigation language changes materially
- the live page layout or interaction model changes
- signup/login styling or form framing changes
- operator entry points gain a new design language
- the brand palette, typography pairing, or accent hierarchy changes

## Recommended NotebookLM Use

Ask questions like:

- Which current K-Beats reference screen is closest to this new page?
- Should this feature inherit the cinematic public style or the quieter operator style?
- Does this proposed layout preserve the current balance between hot pink actions, cyan system accents, and black-stage composition?
- Is this new page closer to the homepage, live page, signup page, or staff login visual model?
