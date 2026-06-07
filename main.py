"""
=======================================================================
  Nifty Total Returns Index (TRI) Downloader & Analyzer
=======================================================================
  Downloads TRI data from niftyindices.com via API (no browser needed),
  calculates CAGR, Std Dev, rolling returns (per ROLLING_YEARS_LIST),
  quartile analysis, and outputs a static website backed by analysis JSON.

  Usage: python main.py
=======================================================================
"""

import os
import sys
import time
import json
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from config import (INDEX_CATEGORIES, START_YEAR, START_MONTH, START_DAY,
                    ROLLING_YEARS_LIST, LATEST_RETURN_YEARS_LIST)
from downloader import download_all_indices, get_end_date
from processor import build_analysis, build_public_site_data
from amc_scraper import fetch_amc_map, get_amcs
from url_finder import build_url_map
from web_export.export_static_site import build_site


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DATA_PATH = PROJECT_ROOT / "cache" / "site_data.json"
SITE_OUTPUT_DIR = PROJECT_ROOT / "index"


def main():
    print("=" * 65)
    print("  Nifty Total Returns Index (TRI) Downloader & Analyzer")
    print("=" * 65)

    # Count total indices
    total_indices = sum(len(v) for v in INDEX_CATEGORIES.values())
    total_categories = len(INDEX_CATEGORIES)
    print(f"\nIndices to process: {total_indices} across {total_categories} categories")

    # Date range
    start_date = date(START_YEAR, START_MONTH, START_DAY)
    end_date = get_end_date()
    total_years = (end_date - start_date).days / 365.25

    print(f"Date range: {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')} ({total_years:.1f} years)")
    print(f"Rolling periods: {', '.join(f'{y}Y' for y in ROLLING_YEARS_LIST)}")
    print(f"Latest return periods: {', '.join(f'{y}Y' for y in LATEST_RETURN_YEARS_LIST)}")
    print(f"Yearly chunks to download per index: {int(total_years) + 1}")
    print(f"Total API calls: ~{total_indices * (int(total_years) + 1)}")

    print(f"\nThis will take approximately {total_indices * (int(total_years) + 1) * 1.5 / 60:.0f} minutes.")
    print("Proceeding automatically and refreshing all TRI data from NSE.")

    # ========================== DOWNLOAD ==========================
    print("\n" + "=" * 65)
    print("  PHASE 1: DOWNLOADING DATA")
    print("=" * 65)

    start_time = time.time()
    all_data = download_all_indices(INDEX_CATEGORIES, start_date, end_date,
                                    force_refresh=True)
    download_time = time.time() - start_time

    print(f"\nDownload complete: {len(all_data)}/{total_indices} indices retrieved")
    print(f"Download time: {download_time/60:.1f} minutes")

    if not all_data:
        print("No data downloaded. Exiting.")
        return

    # ========================== PROCESS ==========================
    print("\n" + "=" * 65)
    print("  PHASE 2: ANALYZING DATA")
    print("=" * 65)

    process_start = time.time()
    periods_data = []  # list of (rolling_years, raw_data_df, num_periods)
    for ry in ROLLING_YEARS_LIST:
        print(f"\n-- Building {ry}-year rolling analysis --")
        df, n = build_analysis(all_data, ry, latest_return_years=LATEST_RETURN_YEARS_LIST)
        if df is None:
            print(f"Analysis failed for {ry}Y. Exiting.")
            return
        periods_data.append((ry, df, n))
    process_time = time.time() - process_start

    print(f"\nAnalysis complete in {process_time:.1f} seconds")
    print(f"Indices analyzed: {len(periods_data[0][1])}")
    for ry, _, n in periods_data:
        print(f"  {ry}Y rolling periods: {n}")

    # ========================== SCRAPE AMCs ==========================
    print("\n" + "=" * 65)
    print("  PHASE 3: FETCHING AMC / INDEX FUND DATA")
    print("=" * 65)

    source_url_map = build_url_map(INDEX_CATEGORIES)  # cache per-index URLs to url_cache.json
    amc_map = fetch_amc_map()
    amc_lookup = lambda name: get_amcs(name, amc_map)
    source_lookup = lambda name: source_url_map.get(name, "")

    # ========================== PUBLISH DATA ==========================
    print("\n" + "=" * 65)
    print("  PHASE 4: BUILDING WEBSITE DATA")
    print("=" * 65)

    data_updated_through = _latest_data_date(all_data)
    site_data = build_public_site_data(
        periods_data,
        amc_lookup=amc_lookup, source_lookup=source_lookup,
        latest_return_years=LATEST_RETURN_YEARS_LIST,
        data_updated_through=data_updated_through,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )
    BACKEND_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BACKEND_DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(site_data, f, ensure_ascii=False, indent=2)
    build_site(site_data, SITE_OUTPUT_DIR, project_root=PROJECT_ROOT)

    total_time = time.time() - start_time
    print(f"\n{'=' * 65}")
    print(f"  DONE!")
    print(f"{'=' * 65}")
    print(f"  Backend data: {BACKEND_DATA_PATH}")
    print(f"  Website    : {SITE_OUTPUT_DIR}")
    print(f"  Total time  : {total_time/60:.1f} minutes")
    print(f"  Indices     : {len(periods_data[0][1])}")
    print(f"  Sheet pairs : {', '.join(f'{ry}Y' for ry, _, _ in periods_data)}")
    print(f"{'=' * 65}")


def _latest_data_date(all_data):
    latest = None
    for df in all_data.values():
        value = df["Date"].max()
        if latest is None or value > latest:
            latest = value
    if latest is None:
        return None
    return latest.date().isoformat() if hasattr(latest, "date") else str(latest)


if __name__ == "__main__":
    main()

