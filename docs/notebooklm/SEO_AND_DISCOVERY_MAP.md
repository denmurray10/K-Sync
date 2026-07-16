# K-Sync SEO And Discovery Map

## Freshness

- Last reviewed: 2026-07-16
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

## UK K-Pop Radio Destination

- `/kpop-radio-station-uk/` owns the focused `K-Pop Radio Station` and UK online-radio intent.
- `core.views.uk_kpop_radio` renders the shared `seo_destination.html` shell with the dedicated `seo_kpop_radio_uk.html` content partial.
- The page has one keyword-aligned H1, route-specific title and description metadata, a canonical URL, social preview artwork, and `RadioStation`, `BroadcastService`, and `BreadcrumbList` JSON-LD.
- Its primary action is live listening. Supporting internal links point to the indexable live, schedule, request, charts, comebacks, idols, and news routes using descriptive anchor text.
- Listener-facing FAQs answer free-listening, 24/7 availability, requests, music mix, UK timing, and worldwide access questions. The FAQs are visible page content and are not treated as a guaranteed Google rich-result feature.

## Best K-Pop Playlist 2026 Destination

- `/best-kpop-playlist-2026/` owns the focused `Best K-Pop Playlist 2026` intent and is designed as a useful, changing chart edit rather than a static keyword landing page.
- `core.views.best_kpop_playlist_2026` renders the shared `seo_destination.html` shell with the dedicated `seo_best_kpop_playlist_2026.html` content partial.
- The server-rendered top 10 comes from the latest daily `Ranking` record. It deliberately represents current 2026 listening momentum, so a resurgent song does not have to have been released in 2026.
- A separate fresh-release edit comes from the current month's `ComebackData` and only shows releases dated on or before the current day. This keeps genuinely new 2026 releases distinct from the live chart.
- The page has one keyword-aligned H1, a route-specific title and description, canonical and social metadata, and `MusicPlaylist`, `MusicRecording`, and `BreadcrumbList` JSON-LD based on the visible tracks.
- Supporting internal links point to the indexable live, charts, comeback timeline, idols, news, song-request, and mood/discovery routes using descriptive anchor text.
- Visible FAQs explain freshness, selection, release-year distinctions, live-radio listening, song requests, and the comeback calendar.

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
