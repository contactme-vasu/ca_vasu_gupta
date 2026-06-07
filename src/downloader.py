"""
Downloads Total Returns Index data from NSE Indices website via API.
No browser/Selenium needed - uses direct HTTP POST requests.
"""

import os
import re
import requests
import json
import pandas as pd
import time
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


API_URL = "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(_PROJECT_ROOT, "cache", "data_cache")


def _cache_path(index_name):
    """Sanitized CSV path for an index."""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", index_name).strip("_")
    return os.path.join(CACHE_DIR, f"{safe}.csv")


def _load_cached(index_name):
    """Load cached TRI data for an index, or None if missing/unreadable."""
    path = _cache_path(index_name)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, parse_dates=["Date"])
        if df.empty or "Total Returns Index" not in df.columns:
            return None
        return df.sort_values("Date").reset_index(drop=True)
    except Exception as e:
        print(f"    Cache read error ({path}): {e}")
        return None


def _save_cached(index_name, df):
    """Persist cached TRI data for an index."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(index_name)
    df = df.sort_values("Date").drop_duplicates(subset=["Date"], keep="first")
    df.to_csv(path, index=False, date_format="%Y-%m-%d")

HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.niftyindices.com",
    "Referer": "https://www.niftyindices.com/reports/historical-data",
    "X-Requested-With": "XMLHttpRequest",
}


def format_date_for_api(dt):
    """Format a date object as 'dd-MMM-yyyy' for the API (e.g., '01-Apr-2025')."""
    return dt.strftime("%d-%b-%Y")


def get_end_date():
    """
    Calculate the end date: latest 31st March before or on today.
    If today is 1-Apr-2026, end date = 31-Mar-2026.
    If today is 15-Feb-2026, end date = 31-Mar-2025.
    """
    today = date.today()
    # If we are in April or later, use March 31 of this year
    # If we are in Jan-March, use March 31 of previous year
    if today.month >= 4:
        end = date(today.year, 3, 31)
    else:
        end = date(today.year - 1, 3, 31)

    # But if today is exactly March 31 or later in March, use this year's March 31
    if today.month == 3 and today.day == 31:
        end = date(today.year, 3, 31)

    return end


def generate_yearly_ranges(start_date, end_date):
    """
    Generate 1-year date ranges from start_date to end_date.
    E.g., (01-Apr-2005, 31-Mar-2006), (01-Apr-2006, 31-Mar-2007), ...
    """
    ranges = []
    current_start = start_date
    while current_start < end_date:
        current_end = current_start + relativedelta(years=1) - relativedelta(days=1)
        if current_end > end_date:
            current_end = end_date
        ranges.append((current_start, current_end))
        current_start = current_end + relativedelta(days=1)
    return ranges


def warm_session(session):
    """Visit the landing page to (re)acquire cookies."""
    try:
        session.get(
            "https://www.niftyindices.com/reports/historical-data",
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=30,
        )
    except Exception:
        pass


def fetch_tri_data(index_name, start_date, end_date, session=None, max_retries=4):
    """
    Fetch TRI data for one index and one date range from the API.
    Retries with session re-warm on timeout / 401 / transient errors.
    Returns a list of dicts or None on failure.
    """
    if session is None:
        session = requests.Session()
        warm_session(session)

    start_str = format_date_for_api(start_date)
    end_str = format_date_for_api(end_date)

    cinfo = (
        "{{'name':'{name}','startDate':'{start}',"
        "'endDate':'{end}','indexName':'{name}'}}"
    ).format(name=index_name, start=start_str, end=end_str)

    payload = json.dumps({"cinfo": cinfo})

    for attempt in range(1, max_retries + 1):
        try:
            response = session.post(API_URL, headers=HEADERS, data=payload, timeout=90)
            if response.status_code == 401:
                raise requests.exceptions.HTTPError("401 Unauthorized", response=response)
            response.raise_for_status()
            result = response.json()
            data = json.loads(result["d"])
            return data
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if attempt == max_retries:
                print(f"    Network error (final): {e}")
                return None
            print(f"    Retry {attempt}/{max_retries-1} after: {e}")
            # Re-warm session on 401 (cookies expired) or any error after the first
            if status == 401 or attempt >= 1:
                warm_session(session)
            time.sleep(2 * attempt)  # backoff: 2s, 4s, 6s...
        except (json.JSONDecodeError, KeyError) as e:
            print(f"    Parse error: {e}")
            return None
    return None


def download_index_data(index_name, start_date, end_date, session=None, force_refresh=False):
    """
    Download TRI data for one index, combining with any locally cached CSV.
    Only fetches yearly chunks newer than the cache's last date.
    Returns a DataFrame with columns: IndexName, Date, Total Returns Index
    """
    if session is None:
        session = requests.Session()

    cached = None if force_refresh else _load_cached(index_name)
    if cached is not None and not cached.empty:
        last_cached = cached["Date"].max().date()
        print(f"    Cache: {len(cached)} rows, up to {last_cached}")
        fetch_from = last_cached + relativedelta(days=1)
    else:
        fetch_from = start_date

    if fetch_from > end_date:
        print(f"    Cache is up to date (latest {last_cached} >= {end_date})")
        return cached

    yearly_ranges = generate_yearly_ranges(fetch_from, end_date)
    all_records = []

    for i, (yr_start, yr_end) in enumerate(yearly_ranges):
        start_str = format_date_for_api(yr_start)
        end_str = format_date_for_api(yr_end)
        print(f"    Chunk {i+1}/{len(yearly_ranges)}: {start_str} to {end_str}", end="")

        data = fetch_tri_data(index_name, yr_start, yr_end, session)

        if data is None or len(data) == 0:
            print(" - No data")
            continue

        print(f" - {len(data)} records")
        all_records.extend(data)

        time.sleep(0.5)

    # Build DataFrame of newly fetched rows
    if all_records:
        new_df = pd.DataFrame(all_records)
        new_df = new_df.rename(columns={
            "Index Name": "IndexName",
            "TotalReturnsIndex": "Total Returns Index",
        })
        new_df = new_df[["IndexName", "Date", "Total Returns Index"]]
        new_df["Date"] = pd.to_datetime(new_df["Date"], format="%d %b %Y")
        new_df["Total Returns Index"] = pd.to_numeric(new_df["Total Returns Index"], errors="coerce")
    else:
        new_df = None

    # Merge with cache
    if cached is not None and new_df is not None:
        df = pd.concat([cached, new_df], ignore_index=True)
    elif cached is not None:
        df = cached
    elif new_df is not None:
        df = new_df
    else:
        return None

    df = df.sort_values("Date").drop_duplicates(subset=["Date"], keep="first").reset_index(drop=True)

    # Persist to cache
    _save_cached(index_name, df)

    return df


def download_all_indices(index_categories, start_date, end_date, force_refresh=False):
    """
    Download TRI data for all indices across all categories.
    Returns a dict: {index_name: DataFrame}
    """
    session = requests.Session()
    # First visit the page to get cookies
    try:
        session.get(
            "https://www.niftyindices.com/reports/historical-data",
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=15,
        )
    except Exception:
        pass  # Continue even if this fails

    all_data = {}
    total_indices = sum(len(v) for v in index_categories.values())
    current = 0

    for category, indices in index_categories.items():
        print(f"\n{'='*60}")
        print(f"Category: {category}")
        print(f"{'='*60}")

        for index_name in indices:
            current += 1
            print(f"\n[{current}/{total_indices}] {index_name}")

            df = download_index_data(index_name, start_date, end_date, session,
                                     force_refresh=force_refresh)

            if df is not None and len(df) > 0:
                all_data[index_name] = df
                print(f"  -> Total: {len(df)} records, "
                      f"{df['Date'].min().strftime('%d-%b-%Y')} to "
                      f"{df['Date'].max().strftime('%d-%b-%Y')}")
            else:
                print(f"  -> SKIPPED (no data returned)")

            # Small delay between indices
            time.sleep(1)

    return all_data
