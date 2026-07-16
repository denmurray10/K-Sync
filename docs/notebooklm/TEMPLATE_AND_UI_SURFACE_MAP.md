# K-Sync Template And UI Surface Map

## Freshness

- Last reviewed: 2026-07-16
- Current truth: This map is based on current template files in `core/templates/core` and render calls in `core/views.py`.
- Legacy context: Prototype, lab, and exported design pages share the same template directory as production pages.

## Purpose

Use this guide when a task asks which templates or rendered pages belong to a
feature, journey, or management surface.

## Shared layout surfaces

- `header.html`
- `footer.html`
- `seo_meta.html`
- `404.html`

These are shared across broad parts of the site and should be treated as
high-impact UI surfaces.

`core/static/core/js/live_status.js` is the shared client-side live-status channel. The header, mobile player, My Station widget, and homepage subscribe to it so live metadata is refreshed through one deduplicated request loop.

## Main public product templates

### Brand and discovery

- `index.html` (homepage SEO metadata hooks, live-listening hero, mobile discovery links, and deferred hero media)
- `charts.html`
- `idols.html`
- `schedule.html`
- `news.html`
- `about_us.html`
- `pricing.html`
- `shop.html`
- `presenters.html`
- `promo.html`
- `listen_free_landing.html`
- `seo_destination.html`
- `seo_kpop_radio_uk.html` (dedicated content partial for `/kpop-radio-station-uk/`)
- `seo_best_kpop_playlist_2026.html` (dedicated chart-edit partial for `/best-kpop-playlist-2026/`)

### Live and stream

- `live_experience.html`
- `live_popout_player.html`
- `stream_hub.html`
- `stream_player.html`
- `request_track.html`

### Editorial and release intelligence

- `blog_page.html`
- `blog_article.html`
- `comebacks.html`
- `comeback_release_article.html`
- `calendar.html`

### Community and fandom

- `fan_clubs.html`
- `contest_entry.html`
- `contests.html`
- `results.html`

### Authenticated member experience

- `login.html`
- `signup.html`
- `dashboard.html`
- `my_station_onboarding.html`
- `start_club.html`

## Staff and operator templates

- `signups_login.html`
- `signups_dashboard.html`
- `playlist_manager.html`
- `track_manager.html`
- `song_upload_manager.html`

These templates are the main operator surfaces and should be treated as high
impact for internal workflow changes.

## Game and engagement templates

- `game_intro.html`
- `song_game.html`
- `song_game_promo.html`
- `idol_scramble.html`
- `lyric_drop.html`
- `lyric_drop_promo.html`
- `chart_clash.html`
- `chart_clash_promo.html`
- `bias_selector.html`
- `bias_selector_promo.html`
- `fandom_trivia.html`
- `mv_matcher.html`
- `draft_day.html`
- `beat_streak.html`

## Prototype, exported, and design-lab templates

These exist in the same app and route file but should be treated as lower
confidence product truth unless the task explicitly targets them:

- `home_redesign_lab.html`
- `upcoming_comebacks_design_lab.html`
- `what_just_landed_reel_lab.html`
- `what_just_landed_reel_preview.html`
- `test_landing_wow_hero.html`
- exported reward, store, modal, or neon variants

## UI Surface Rules For NotebookLM

- If a task changes page behavior, NotebookLM should identify both the route family and the template surface.
- If a route renders a prototype or lab template, NotebookLM should say so explicitly.
- If a task touches shared layout or SEO partials, NotebookLM should warn that the blast radius is broad.
