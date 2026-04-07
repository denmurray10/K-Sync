# K-Sync SEO And Discovery Map

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This map is based on `core/context_processors.py`, `core/sitemaps.py`, route metadata, and the editorial pipeline.
- Legacy context: Some prototype or lab routes should not be treated as important discovery surfaces unless explicitly promoted.

## Purpose

Use this guide when a change could affect search discoverability, metadata,
internal linking, or the structure of content entry points.

## Main Discovery Surfaces

- `news/` and `blog/<slug>/`
- `charts/`
- `idols/` and dynamic idol pages
- `comeback-timeline/` and landed article pages
- `fan-clubs/`
- `presenters/`
- `about/` and pricing pages

## Current SEO Plumbing

### Context-based metadata defaults

`core.context_processors.seo_defaults` provides route-based titles and
descriptions for major surfaces including:

- home
- live
- charts
- news
- idols
- schedule
- games
- comeback timeline
- blog page
- contests
- fan clubs
- presenters
- pricing
- about

### Sitemaps

`core.sitemaps` currently exposes:

- static page sitemap entries
- `BlogArticle` sitemap entries

### Robots

`robots.txt` allows crawling and points crawlers to the generated sitemap.

## Editorial SEO Behavior

The editorial system matters for discovery because it does more than publish
articles:

- generates long-form content
- creates article metadata
- runs internal link enrichment
- creates social-ready article variants and queue entries

The internal link pass is especially important because it strengthens site
connectivity and should not be treated as optional decoration.

## Discovery Risks

- route renames can break route-based titles and descriptions
- slug changes can break article or idol discoverability
- removing `seo_meta.html` or equivalent shared metadata inclusion can strip page metadata broadly
- lab or preview pages should not be treated as core SEO targets unless intentionally published

## NotebookLM Rules

- When a task touches news, blog, idols, charts, or comeback pages, NotebookLM should mention SEO impact.
- If a content or template change could affect metadata, internal linking, or sitemap coverage, say so explicitly.
- Use the editorial and link-pass flow as current truth for how content supports discovery.
