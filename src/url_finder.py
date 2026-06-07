"""
Generates and caches niftyindices.com URLs for each index.

URLs follow the pattern:
  https://www.niftyindices.com/indices/equity/{category-slug}/{index-slug}

Category mapping (from config.py category names):
  "Broad Market Indices" -> broad-based-indices
  "Strategy Indices"     -> strategy-indices
  "Thematic Indices"     -> thematic-indices

Cached to url_cache.json.
"""

import json
import os
import re


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(_PROJECT_ROOT, "cache", "url_cache.json")

CATEGORY_SLUGS = {
    "Broad Market Indices": "broad-based-indices",
    "Strategy Indices": "strategy-indices",
    "Thematic Indices": "thematic-indices",
}


def slugify(name):
    """Convert index name to URL slug."""
    s = name.lower()
    s = s.replace(":", "-")
    s = re.sub(r"[^a-z0-9\s-]", "", s)  # drop other punctuation
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


def build_url(category, index_name):
    cat_slug = CATEGORY_SLUGS.get(category, "broad-based-indices")
    return f"https://www.niftyindices.com/indices/equity/{cat_slug}/{slugify(index_name)}"


def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def build_url_map(index_categories):
    """
    Return dict {index_name: url} for every index in config, persisting to cache.
    """
    cache = _load_cache()
    changed = False
    for category, indices in index_categories.items():
        for idx in indices:
            if idx not in cache:
                cache[idx] = build_url(category, idx)
                changed = True
    if changed:
        _save_cache(cache)
    return cache
