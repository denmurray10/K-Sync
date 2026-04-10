# K-Beats SEO Week Action Plan

This file turns the one-week SEO plan into a practical execution checklist for the current Django site.

## Day 1: Crawl Waste And Indexation Risk

### Mark `noindex`
- `404-preview/`
- `home-redesign-lab/`
- `comeback-design-lab/`
- `what-just-landed-reel-lab/`
- `test-landing-wow/`
- `test-page/`
- `legal/placeholder/`
- `internal/reels/preview/<slug>/<uuid>/`

### Keep indexable
- `/`
- `/listen-free/`
- `/live/`
- `/news/`
- `/blog-page/`
- `/blog/<slug>/`
- `/charts/`
- `/idols/`
- `/idols/<slug>/`
- `/comebacks/`
- new landing pages for UK, mood, playlist, and discovery intent

### Leave out of sitemap unless promoted later
- lab routes
- test routes
- internal preview routes
- placeholder pages
- promo duplicates that do not serve a distinct search intent

## Day 2: Core Page Keyword Map

| Page | Primary keyword cluster | Intent | Primary CTA |
| --- | --- | --- | --- |
| `/` | `kpop radio`, `kpop radio online`, `live kpop stream` | commercial discovery | Listen live |
| `/listen-free/` | `free kpop radio`, `kpop music free online no download`, `where to listen to kpop online free` | transactional | Start listening free |
| `/live/` | `live kpop stream`, `kpop live radio station` | live listening | Play current stream |
| `/news/` + `/blog-page/` | `discover new kpop music`, freshness/editorial terms | informational discovery | Read article |
| `/idols/` | artist and group discovery | informational | Explore artist page |
| `/comebacks/` | `kpop comebacks`, new release discovery | informational/current-awareness | Track releases |

## Day 3: Internal Linking Checklist

### Homepage
- Link to UK radio page
- Link to one mood page
- Link to one playlist/discovery page
- Keep direct routes to `live`, `charts`, `news`, and `idols`

### Listen-Free
- Link to UK radio page
- Link to one mood page
- Link to one discovery or playlist page
- Keep direct route to `live`

### Blog Hub / News
- Link to discovery page
- Link to playlist page
- Link to one mood page

### Comebacks
- Link to discovery page
- Link to live stream
- Link to charts

### New Editorial Articles
- Run the internal-link pass after publishing
- Add at least one natural link to `live`, one to `charts`, and one to a related landing page when relevant

## Day 4: First New Pages To Publish

### Publish first
- `/kpop-radio-station-uk/`
- `/rainy-day-kpop/`

### Keep both pages narrow
- one H1
- one primary keyword
- one lead paragraph that clearly answers intent
- links to `live`, `charts`, and `blog`

## Day 5: First Editorial Loop

### First weekly article target
- `best kpop songs right now`

### Workflow
1. Generate article
2. Review title, H1, and first 150 words for keyword clarity
3. Publish to blog
4. Run internal-link pass
5. Add homepage or news-surface placement if the article is strong enough

## Day 6: Authority Support Page

### Preferred next page
- `/best-kpop-playlist-2026/`

### If artist support is chosen instead
- upgrade one existing high-interest artist page already in the system
- add links to charts, comebacks, live stream, and one fresh editorial piece

## Day 7: Review

### Check
- Search Console impressions
- CTR by page cluster
- sitemap coverage
- whether noindex routes remain out of SEO workflows
- which new landing page gains impressions first

### Decide next repeat
- keep one successful pattern
- adjust one underperforming page
- queue the next three pages in order
