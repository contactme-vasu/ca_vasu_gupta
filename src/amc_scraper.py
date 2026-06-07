"""
Scrapes the "Domestic Index Funds" (AMC/issuer) list from niftyindices.com.

Key insight: the full issuer table (tbody#indxfund) is embedded in every
index detail page's HTML — JavaScript just filters rows by CSS class on the
client side. So a single fetch of any index page gives us AMCs for ALL indices.

Cached to amc_cache.json (default 7-day TTL).
"""

import json
import os
import re
import time
import requests
from datetime import datetime, timedelta


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(_PROJECT_ROOT, "cache", "amc_cache.json")
CACHE_TTL_DAYS = 7

# Any index page works — use a stable well-known one
SOURCE_URL = "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-50"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def normalize(name):
    """Strip all non-alphanumerics and lowercase for matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data["timestamp"])
        if datetime.now() - ts > timedelta(days=CACHE_TTL_DAYS):
            return None
        return data["amc_map"]
    except Exception:
        return None


def _save_cache(amc_map):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "amc_map": amc_map,
        }, f, indent=2, ensure_ascii=False)


def _parse_amc_table(html):
    """
    Parse the <tbody> inside <table id="indxfund">. Rows look like:
      <tr class="nifty50">
        <td data-th="Index">NIFTY 50</td>
        <td data-th="Issuer">HDFC Mutual Fund</td>
      </tr>
    Returns: {normalized_index_name: [amc1, amc2, ...]}
    """
    tbl_start = html.find('id="indxfund"')
    if tbl_start == -1:
        return {}
    tb_start = html.find("<tbody", tbl_start)
    tb_end = html.find("</tbody>", tb_start)
    if tb_start == -1 or tb_end == -1:
        return {}
    tbody = html[tb_start:tb_end]

    row_pat = re.compile(
        r'<td[^>]*data-th="Index"[^>]*>(.*?)</td>\s*'
        r'<td[^>]*data-th="Issuer"[^>]*>(.*?)</td>',
        re.DOTALL | re.IGNORECASE,
    )
    tag_pat = re.compile(r"<[^>]+>")

    result = {}
    for m in row_pat.finditer(tbody):
        idx_name = tag_pat.sub("", m.group(1)).strip()
        issuer = tag_pat.sub("", m.group(2)).strip()
        if not idx_name or not issuer:
            continue
        key = normalize(idx_name)
        result.setdefault(key, [])
        if issuer not in result[key]:
            result[key].append(issuer)
    return result


def fetch_amc_map(force_refresh=False):
    """
    Return dict {normalized_index_name: [amc, ...]}, using cache when fresh.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            print(f"  Using cached AMC data ({len(cached)} indices)")
            return cached

    print(f"  Fetching AMC data from {SOURCE_URL}...")
    session = requests.Session()
    # Warm-up to get cookies
    for attempt in range(3):
        try:
            session.get(
                "https://www.niftyindices.com/reports/historical-data",
                headers=HEADERS,
                timeout=60,
            )
            break
        except Exception:
            time.sleep(2)

    for attempt in range(3):
        try:
            r = session.get(SOURCE_URL, headers=HEADERS, timeout=90)
            r.raise_for_status()
            amc_map = _parse_amc_table(r.text)
            if amc_map:
                _save_cache(amc_map)
                print(f"  Parsed AMCs for {len(amc_map)} indices")
                return amc_map
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(3)

    print("  Failed to fetch AMC data — returning empty map")
    return {}


def get_amcs(index_name, amc_map):
    """Return list of AMCs for index_name, or [] if not found."""
    return amc_map.get(normalize(index_name), [])
