# All In One News

A Bengali-first, bilingual news dashboard that brings Bangladesh and international headlines together in one place.

**Live website:** https://all-in-one-news.github.io/all-in-one-news/

## What the site includes

- Country and language filters (Bangla and English). Visitors can change and retain their own preferences.
- News desks for incidents and public-safety reports, politics, economy, sports, technology, entertainment, and the share market.
- Search, date range, newest/oldest sorting, and paginated results.
- Light/dark theme, responsive layout, and accessible labels/live announcements.
- Article thumbnails and supported YouTube/Facebook embeds when the source provides them.
- A latest-news ticker that follows the selected country, language, and news desk.

## How news is collected

The scheduled GitHub Actions collector searches Google News RSS feeds for country and topic coverage, enriches some article links and images from publisher pages, classifies stories, groups near-duplicate reports, and writes the generated data to `news.json`. A last-known-good `news-backup.json` is retained for frontend fallback.

- Collection schedule: every 10 minutes (GitHub Actions cron).
- Browser refresh: every 60 seconds while the page is visible.
- Retention window: 30 days.
- The site uses public RSS/search discovery for Facebook and YouTube links where available; it is not a direct Facebook or YouTube API ingestion service.
- Country is assigned from explicit incident-location evidence. Unlocated international stories remain under the global `WORLD` label.

## Repository map

| Path | Purpose |
| --- | --- |
| `index.html` | News dashboard, filters, theme, and rendering |
| `news.json` | Current generated news snapshot |
| `news-backup.json` | Last known-good news snapshot |
| `sitemap.xml` | Search-engine sitemap |
| `articles/` | Generated article landing pages |
| `.github/scripts/update_news.py` | RSS collection, enrichment, classification, and deduplication |
| `.github/scripts/test_country_detection.py` | Country and homepage regression checks |
| `.github/workflows/update-news.yml` | Scheduled collection and publishing workflow |
| `.github/workflows/test-country-detection.yml` | Automated regression-test workflow |

## Development and checks

Run the regression checks locally from the repository root:

```bash
python -m py_compile .github/scripts/update_news.py
python .github/scripts/test_country_detection.py
```

The regression workflow runs these checks on relevant pushes and pull requests. The news workflow validates the generated feed and sitemap before publishing data. GitHub Pages deploys the static website from the repository's configured Pages source.

## Notes and limitations

- News availability, category accuracy, summaries, and thumbnails depend on third-party feeds and publisher pages; coverage is not exhaustive.
- The dashboard is a news discovery and linking service, not an official emergency-alert authority. For urgent cases, follow the linked official source.
- A visitor's chosen language controls the displayed language; IP location is informational and does not override that preference.
