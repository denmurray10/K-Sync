# K-Sync Notebook Change Log

## 2026-07-16

### My Station flyout → "For You" pulse drawer

- Repurposed the global flyout tab (Den's pick from three options) as a return-visit engine. Tab reads **FOR YOU**; its badge now counts unread alerts **plus** pulse items that changed since the user last opened the drawer (seen-state in `localStorage` key `kbeats_foryou_seen_v1`, marked seen ~1.5s after opening).
- Drawer rows (logged-in): bias next-comeback D-day + title → calendar; bias chart position/movement on today's Top 20 → charts; Daily Drop day number with played/solved/streak state read client-side from the game's own localStorage → play page. No bias set → "Pick your bias" row → personalisation settings. Logged-out drawer unchanged (signup variant). New `data-track-category="for_you_flyout"` events: `pulse_comeback_open`, `pulse_chart_open`, `pulse_drop_open`, `pulse_pick_bias`.
- New `core.context_processors.for_you_pulse` (registered in settings after `gamification`): auth-only, one profile + one ranking query, with the comeback/chart scan cached per `(bias, chart-day)` for 30 min (`foryou_pulse:<bias_pk>:<date>`).

### My Station flyout fix: Alpine deduplication

- The My Station flyout tab (global, in `header.html`) opened blank/behaved erratically. Root cause: Alpine.js was loaded twice on ~25 pages — `header.html` has shipped its own Alpine tag since March (26e0f35) while pages kept their pre-existing ones. Double `Alpine.start()` re-initializes every component (Alpine's docs warn against it) — duplicate listeners/scopes break toggles like the flyout's.
- Removed the page-level Alpine core tag from all 25 templates that include `core/header.html` (both the `3.x.x` and pinned `3.14.9` forms); `header.html` is now the single Alpine source on those pages. Standalone pages (game play pages, etc.) keep their own tags. The `@alpinejs/collapse` plugin tag was retained where present.
- Also fixed the flyout's invisible title (`text-black` on the black panel → `text-primary`) and added a global `[x-cloak] { display: none !important; }` rule to `core/shared_head.html` (previously no page defined it, so `x-cloak` elements could flash before Alpine initialized).
- Rebuilt both compiled Tailwind bundles (`home-tailwind.css`, `idols-tailwind.css`).
- **Second root cause (confirmed from a live screenshot):** the flyout panel carried a static `translate-x-full` class while Alpine's string-ternary `:class` *added* `translate-x-0` on open without removing the static class. With both classes present, stylesheet order decides — `.translate-x-full` sits later in the compiled CSS and wins, so the tab moved and the overlay dimmed but the panel never slid in. Converted the panel and tab-button bindings to Alpine object syntax (`:class="{ 'translate-x-0': open, 'translate-x-full': !open }"`), which actively toggles the conflicting class off; pre-JS closed defaults retained.

## Freshness

- Last reviewed: 2026-04-06
- Current truth: This changelog tracks curated-source changes for the `K Beats Radio` notebook.
- Legacy context: Earlier notebook states were smaller bootstrap packs and should not be treated as complete project-brain coverage.

## 2026-07-14

### Homepage "For Your Bias" rail + views.py repair

- Added a full "For Your Bias" section to `core/templates/core/index.html`, directly under the live player bar: `#bias-rail`, black-stage, mirroring the Today's Programming anatomy (stacked headline + mono subtitle + sharp-shadow header CTA, then full-width hover-invert rows). Three states — personalised (chart row with rank/movement/track, next-comeback row with D-day and date, hub row with group image), picker (logged in, no bias — explainer rows + Choose Your Bias CTA), and signup teaser (logged out — explainer rows + Start Free CTA). Context is built in `_build_homepage_context` (`bias_rail` key) reusing the existing station-matching helpers, `Ranking` daily data, `ComebackData`, and the stream-image helpers for the bias image.
- New click events under `data-track-category="homepage_bias_rail"`: `bias_rail_group_home`, `bias_rail_chart_home`, `bias_rail_comeback_home`, `bias_rail_play_home`, `bias_rail_pick_home`, `bias_rail_signup_home`.
- Rebuilt `core/static/core/css/home-tailwind.css` for the new markup.
- Repaired a truncation in `core/views.py` left by the 14 Jul cleanup pass: restored `get_artist_stats`'s tail and the `placeholder`, `privacy_policy`, `cookie_policy`, and `terms_of_service` views from git history (the app could not boot without them).
- Fixed double-encoded ▲/▼ chart-movement glyphs in `core/views.py` (they rendered as mojibake in Trending and would have in the new rail).
- Current truth unchanged elsewhere; no legacy reinterpretation.

### Daily-format games: Daily Drop + Chart Oracle (15 Jul)

- **Daily Drop** (`/game/daily-drop/` promo, `/game/daily-drop/play/`): Heardle-format shared daily puzzle. One mystery track per chart day, deterministically seeded from the daily `Ranking` date over its top 40, enriched with an iTunes 30s preview (cached per chart day, key `daily_drop_puzzle:<date>`). Six tries on a 1/2/4/7/11/16s snippet ladder. Guesses are validated server-side (`/api/daily-drop/guess/`) so the answer never ships in page source; `/api/daily-drop/clip/` returns only the clip URL. Client keeps per-day state and streak in localStorage, posts finished games to `save_game_score` as `daily_drop`, and offers a Wordle-style share grid.
- **Chart Oracle** (`/game/chart-oracle/` promo, `/game/chart-oracle/play/`): prediction game against tomorrow's chart. Three deterministic matchups (seeded RNG over today's Top 20) plus a #1 call from the top five. Login required to lock in (`/api/chart-oracle/predict/`; one `ChartPrediction` per user per chart day, 409 on duplicates). Predictions auto-resolve on the next visit once a newer daily ranking exists (+10 per matchup, +20 for the #1 call; a track that falls off the chart loses its matchup, both off = void) and write a `chart_oracle` `GameScore`.
- New model `ChartPrediction`; `GameScore.GAME_CHOICES` gains `daily_drop` and `chart_oracle` — migration `0052_alter_gamescore_game_chartprediction` (a `0051` was also generated for pre-existing `writer_slug` drift). Both games are in the Games page All-Games list and the Today's Challenge rotation (now 9 entries). Neither is in the sitemap, consistent with all other game routes.

## 2026-04-06

### Bootstrap and core project-brain setup

- Added the initial internal brief, architecture, operations, conventions, media, AI/editorial, data-model, and flow docs.
- Added supporting root docs such as brand guidance and deployment environment notes.
- Established Radio.co as the current live-source truth and B2 as legacy or secondary context.

### Long-term system expansion

- Added route ownership and permission mapping.
- Added settings and environment cataloging.
- Added management command classification.
- Added template, API, analytics, SEO, lifecycle, glossary, and testing-risk docs.
- Added a root `WORKING_RULES.md` and a sanitized `RELEASE_CHECKLIST.md`.
- Added notebook maintenance workflow support, including validation and update-process guidance.
- Added design-system, component-pattern, page-pattern, UX-rule, and copy-style docs so the notebook can guide future page and feature design.
- Added a visual reference set plus captured page screenshots for the homepage, live experience, signup, and staff login surfaces so future design work can be grounded in the current UI.

## How To Use This File

- Append a dated section whenever the notebook pack changes materially.
- Record:
  - what was added or refreshed
  - why it changed
  - whether current truth or legacy interpretation changed
