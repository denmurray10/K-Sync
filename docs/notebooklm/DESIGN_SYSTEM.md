# K-Sync Design System

## Freshness

- Last reviewed: 2026-04-07
- Current truth: This guide reflects the current K-Beats homepage-led brand and the strongest live product surfaces in the repo.
- Legacy context: Some internal pages use a simplified version of the brand system, especially operator tools that prioritize dense workflows over ceremonial styling.

## Purpose

Use this guide when designing or redesigning K-Sync pages so new work feels
like K-Beats rather than a generic entertainment or SaaS interface.

## Core Design Direction

K-Beats should feel like a premium late-night K-pop broadcast product:

- dark-stage
- editorial
- electric
- sharp-edged
- fan-first
- high contrast

The homepage and live-radio surfaces are the strongest current design anchors.

## Brand Tokens

### Core colors

- `Black Stage`: `#000000`
- `Primary Pink`: `#f425c0`
- `Electric Cyan`: `#00f0ff`
- `White`: `#ffffff`
- `Slate neutrals` for secondary hierarchy

### Usage rules

- black is the default page canvas
- pink is the default action and identity color
- cyan is the contrast accent, not the main CTA color
- white carries primary readability and logo contrast
- do not add random new accent colors without a clear feature reason

## Typography

### Approved pairing

- `Cinzel` for ceremonial or editorial heading moments
- `Montserrat` for body text, controls, metadata, forms, and dense product UI

### Current application

- public hero and editorial surfaces should use `Cinzel` for major headings
- live-radio and promotional surfaces can mix `Cinzel` display with `Montserrat` UI text
- dashboards and operator tools may lean more heavily on `Montserrat` for clarity

### Typography rules

- H1 and H2 should feel dramatic and intentional
- body text should stay readable and compact
- uppercase works well for labels, signals, nav, and CTA copy
- avoid playful fonts, weak hierarchy, or decorative body copy

## Shape And Surface Language

- corners should be sharp by default
- pills are reserved for badges, status chips, or live indicators
- borders matter more than soft shadows
- glass or blur is allowed when it reinforces broadcast atmosphere
- white cards should be rare and intentional

## Spacing And Composition

### Spacing rhythm

Prefer a consistent scale:

- `4`
- `8`
- `12`
- `16`
- `24`
- `32`
- `48`
- `64`
- `96`

### Composition rules

- lead with a strong visual job per section
- use poster-like hero composition at the top
- avoid stacking too many equal-weight boxes
- remove weak elements before compressing spacing

## Motion

Good motion types:

- reveal-up and reveal-left sequences
- ticker motion
- glow pulses
- signal or waveform behavior
- subtle background drift

Rules:

- motion should feel atmospheric, not busy
- loops should be restrained
- respect reduced-motion expectations

## Responsive Rules

Review at minimum:

- `1440px`
- `1024px`
- `768px`
- `390px`

Check for:

- no horizontal overflow
- stable hero composition
- readable dense UI
- usable tap targets
- mobile layouts that still feel premium

## Public Versus Operator Surface Guidance

### Public-facing pages

- stronger visual drama
- more `Cinzel`
- clearer hero hierarchy
- more theatrical use of pink and cyan

### Operator and management pages

- keep the dark-stage palette
- keep sharp edges and uppercase labels
- prioritize density and scan-ability over spectacle
- use color to separate tasks, not to decorate every control

## NotebookLM Rules

- If a proposed design is soft, rounded, pastel, or dashboard-generic, treat it as off-brand.
- If a feature is public-facing, bias toward stronger editorial branding.
- If a feature is an operator tool, keep the brand but optimize for dense clarity first.
