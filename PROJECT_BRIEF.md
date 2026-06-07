# Project Brief — Nifty TRI Downloader & Analyzer

Feed this file to an LLM at the start of a new chat; no other files need reading unless asked.

> **⚠️ Maintenance note for LLMs:** When you make any non-trivial change to this project (new module, moved file, renamed config flag, changed cache layout, new Excel column, altered run behavior, etc.), **update this file in the same turn**. This is the single source of truth for future chats — if it drifts, the next LLM will waste tokens rediscovering the project. Small edits (typo, tiny refactor) don't need an update.

## Purpose
Download Total Returns Index (TRI) data for ~53 NSE indices from `niftyindices.com` (API, no browser), compute CAGR / latest trailing returns (periods in `LATEST_RETURN_YEARS_LIST`, default 1Y/3Y/5Y/7Y/10Y) / Std Dev / max drawdown / Sharpe Ratio / Sortino Ratio / rolling returns (one block per period in `ROLLING_YEARS_LIST`, default 3Y + 5Y) / rolling-return range and consistency / quartile analysis, and publish the analysis as a static website. The workflow no longer generates `Output.xlsx`; it stores public analysis rows in JSON and keeps raw TRI data in the backend cache for calculation.

## Layout
Project root shows only what the user touches: `main.py` (run this to refresh NSE data and rebuild the website), `publish_site.py` (recopy templates from existing `cache/site_data.json` only), and `PROJECT_BRIEF.md`. Code modules live in `src/`, website export code lives in `web_export/`, generated website files live in `site/index/`, caches in `cache/`.

```
Index Funds Analysis/
├─ main.py                  # entry point — user runs this
├─ Auctions of 364-Day Government of India Treasury Bills.xlsx  # RBI 364-day T-Bill yields for risk-free return
├─ PROJECT_BRIEF.md         # this file
├─ src/
│  ├─ config.py             # user-editable settings + INDEX_CATEGORIES dict
│  ├─ downloader.py         # TRI fetcher (Backpage.aspx API) + incremental CSV cache
│  ├─ processor.py          # builds calculated raw inputs + public website analysis JSON
│  ├─ amc_scraper.py        # fetches one niftyindices page, parses indxfund tbody
│  └─ url_finder.py         # slugifies index names → niftyindices URLs
└─ cache/
   ├─ amc_cache.json        # 7-day TTL
   ├─ url_cache.json        # no TTL
   ├─ site_data.json        # generated public analysis rows for the website
   └─ data_cache/           # one CSV per index (TRI history used for calculation)
```

`main.py` inserts `src/` on `sys.path` before importing. All modules compute `_PROJECT_ROOT` from `__file__` so caches are always found relative to the project root regardless of cwd.

## Module notes
- **Latest trailing returns** — `processor.py` adds latest trailing-period start TRI values from `LATEST_RETURN_YEARS_LIST`, then computes annualized 1Y/3Y/5Y/7Y/10Y returns ending at the latest TRI date for the website JSON.
- **downloader.py** — session warm-up, 90s timeout, 4 retries with re-warm on 401/timeout. Incremental: loads cached CSV, fetches only chunks after `last_date`, merges + dedupes + saves.
- **processor.py** — For each rolling period N in `ROLLING_YEARS_LIST`, builds calculated raw inputs in memory and emits public analysis rows with CAGR, risk metrics, latest returns, rolling-return metrics, quartile counts, AMCs, and source links. Sharpe/Sortino use monthly index TRI returns minus monthly risk-free returns from the local RBI 364-day T-Bill workbook (`Date of Auction` + `Implicit Yield at Cut-off Price (percent)`, annual yield converted to monthly return).
- **amc_scraper.py** — key insight: the full `indxfund` tbody is embedded in every index page (JS filters client-side), so ONE fetch = all AMCs. Normalization for lookup: strip non-alphanumerics + lowercase.
- **url_finder.py** — category slug map: Broad Market → `broad-based-indices`, Strategy → `strategy-indices`, Thematic → `thematic-indices`.

## Key config knobs (`config.py`)
- `LATEST_RETURN_YEARS_LIST = [1, 3, 5, 7, 10]` — adds latest trailing return columns to each website analysis table. Each value is the annualized return from the matching start date through the latest TRI date.
- `START_YEAR/MONTH/DAY` = 2005/4/1.
- `ROLLING_YEARS_LIST = [3, 5]` — one website analysis section is generated per entry. Edit freely (e.g. `[3]`, `[1, 3, 5, 7]`).
- `main.py` always refreshes all TRI data from NSE on each run. There is no confirmation prompt and no refresh config toggle.

## Website analysis structure
For each N in `ROLLING_YEARS_LIST`, `cache/site_data.json` and `site/index/data.json` get one period section. Public row fields are: Index Name, CAGR (%), Std Dev (%), Max Drawdown (%), Sharpe Ratio, Sortino Ratio, Years of Data, Latest 1/3/5/7/10 Year Return (%), Average N Year Rolling Return (%), Worst Rolling Return (%), Best Rolling Return (%), Rolling Return Std Dev (%), Top Quartile Count, Bottom Quartile Count, Top/Bottom, AMCs, and Source. Raw TRI values and per-window rolling-return arrays are not included in the public JSON.

## Important design quirks
- **Latest trailing return formulas** use the latest available TRI as the end point and the closest TRI within 30 days of `latest_date - N years` as the start point. Example: with latest date 01-Apr-2020, Latest 1 Year Return uses the start TRI nearest 01-Apr-2019 and end TRI at 01-Apr-2020.
- **Header is "Index Name" not "Fund Name"** (entities are indices).
- Website analysis values are Python-computed. Changing periods or metric logic requires rerunning `main.py`.
- **Sharpe Ratio and Sortino Ratio** are Python-computed from monthly TRI returns. The risk-free rate is the local RBI 364-day T-Bill yield file; annual yields are converted to monthly returns as `(1 + annual_yield/100)^(1/12) - 1`, then aligned to month-end index returns using the latest auction date on or before each month end.
- **RBI T-Bill workbook**: `Auctions of 364-Day Government of India Treasury Bills.xlsx` is a backend input, not a public website artifact. GitHub Actions needs this file committed or otherwise downloaded before `main.py` runs. It should be refreshed when RBI publishes newer 364-day auction data; the cleaner future path is to replace the checked-in workbook with an automated RBI download/CSV cache step.
- **End date** = most recent March 31 on or before today (see `downloader.get_end_date()`).
- **AMC match is by normalized name** (`re.sub(r"[^a-z0-9]", "", name.lower())`) — site uses varied capitalization/spacing.
- **One fetch = all AMCs**: niftyindices embeds the entire issuer table on every index page. Do NOT scrape per-index; it's wasteful.
- **Cache layout**: `data_cache/<sanitized>.csv` (one per index) · `amc_cache.json` (7-day TTL) · `url_cache.json` (no TTL).
- **Running environment**: Windows, Python 3.13 (NOT 3.14 — pandas not installed there). User runs `python main.py` interactively; prompts for output path and confirmation.

## Typical ask patterns
- "Add a new index" → append to `INDEX_CATEGORIES` in `config.py`; next run builds its cache.
- "Change rolling periods" → edit `ROLLING_YEARS_LIST` in `config.py`; requires re-run (formulas + sheet names depend on it).
- "Add column X to Analysis" → modify `processor.build_public_site_data` / `_build_public_period_rows`, then update `web_export/static/index.html` and `web_export/static/app.js`.

## Known tradeoffs / NOT bugs
- The cache layer remains useful for partial-failure recovery, but normal runs deliberately request a full fresh NSE refresh.
- AMC scraper uses regex on HTML (no BeautifulSoup) — fine for the stable table structure.
- URL finder does NOT verify every URL over HTTP — slugs are built from the category pattern and now feed the website `Source` column.

## Website publishing
- User-facing root scripts: `main.py` refreshes NSE data, writes `cache/site_data.json`, and rebuilds `site/index/`; `publish_site.py` recopies browser website files from existing `cache/site_data.json`; `view_site.bat` starts a local preview server and opens `/index/`.
- Website export code lives in `web_export/`; generated public files live in `site/index/`.
- The generated folder is intended to be published at `/index/` on GitHub Pages, e.g. `www.caabcd.com/index/`.
- `main.py` computes public analysis values directly; there is no workbook bridge and no Excel formula cache dependency.
- `.github/workflows/publish-index-site.yml` can be triggered manually or scheduled on April 5 and October 5. It installs `requirements.txt`, runs `python main.py`, then commits `cache/site_data.json` and `site/index/`.
