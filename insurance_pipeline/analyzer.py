"""Build insurance-company metrics from the IRDAI annual handbook.

The pipeline downloads the latest public "Handbook on Indian Insurance
Statistics" ZIP from IRDAI, parses the required workbook tables, and returns a
single DataFrame used by the public /insurance/ website.
"""

from __future__ import annotations

import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests


HANDBOOK_PAGE_URL = "https://irdai.gov.in/handbook-of-indian-insurance"

T39_HEADER_ROWS = 3
T39_COL_YEAR_OF_OPERATION = 5

T53_HEADER_ROWS = 4
T53_LATEST_4_YEAR_OFFSETS = (14, 26, 38, 50)
T53_COL_PAID = 2
T53_COL_REPUDIATED = 3

T56_HEADER_ROWS = 3
T56_PREVIOUS_REPORTED_COLS = (35, 40)
T56_LATEST_INSURER_COL = 45
T56_LATEST_REPORTED_COL = 47

T62_HEADER_ROWS = 5
T62_LATEST_3_TOTAL_ICR_COLS = (121, 136, 151)


@dataclass(frozen=True)
class HandbookSource:
    fiscal_year: str
    url: str


def _clean_name(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"[~^$%*#@]+$", "", s).strip()
    s = re.sub(r"(Ltd\.?)\s*[~^$%*#@]+", r"\1", s)
    return re.sub(r"\s+", " ", s)


_ALIASES: dict[str, str] = {
    "agriculture insurance of india": "agriculture insurance company of india",
    "future generali india insurance c": "future generali india insurance",
    "star health & allied insurance": "star health and allied insurance",
    "magma hdi general insurance": "magma general insurance",
    "kotak mahindra general insurance": "zurich kotak general insurance",
    "galaxy health insurance": "galaxy health and allied insurance",
    "kshemageneral insurance": "kshema general insurance",
    "narayana health insurance": "narayana health insurance",
}


def _normalize(name: str) -> str:
    s = _clean_name(name).lower()
    s = re.sub(r"[#$@*~^%]", "", s)
    s = s.replace(".", "").replace(",", "")
    s = s.replace("limited", "ltd").replace("& ", "and ")
    s = re.sub(r"\bcompany\b", "co", s)
    s = re.sub(r"\(india\)", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(\s+(co|ltd))+\s*$", "", s).strip()
    for alias, canonical in _ALIASES.items():
        if s == alias or s.startswith(alias):
            return canonical
    return s


def _is_data_row(sno) -> bool:
    if pd.isna(sno):
        return False
    return str(sno).strip().replace(".", "").isdigit()


def _is_section_header(name: str) -> bool:
    keywords = (
        "sector",
        "total",
        "specialized",
        "stand-alone",
        "grand total",
        "industry",
        "reinsur",
    )
    return any(keyword in name.lower() for keyword in keywords)


def _numeric(value):
    return pd.to_numeric(value, errors="coerce")


def _find(name: str, data: dict):
    if name in data:
        return data[name]
    normalized = _normalize(name)
    for key, value in data.items():
        if _normalize(key) == normalized:
            return value
    return None


def _fiscal_year_end(fiscal_year: str) -> int:
    start = int(fiscal_year.split("-")[0])
    return start + 1


def latest_years(fiscal_year: str, count: int) -> tuple[str, ...]:
    end_year = _fiscal_year_end(fiscal_year)
    years = []
    for end in range(end_year - count + 1, end_year + 1):
        years.append(f"{end - 1}-{str(end)[-2:]}")
    return tuple(years)


def request_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": HANDBOOK_PAGE_URL,
    }


def discover_latest_handbook() -> HandbookSource:
    response = requests.get(HANDBOOK_PAGE_URL, headers=request_headers(), timeout=120)
    response.raise_for_status()
    html = response.text

    candidates: list[HandbookSource] = []
    href_pattern = re.compile(r"""href=["']([^"']+?\.zip[^"']*)["']""", re.IGNORECASE)
    year_pattern = re.compile(r"Handbook(?:\+|%20| )on(?:\+|%20| )Indian(?:\+|%20| )Insurance(?:\+|%20| )Statistics(?:\+|%20| )(\d{4}-\d{2})", re.IGNORECASE)

    for href in href_pattern.findall(html):
        match = year_pattern.search(href)
        if not match:
            continue
        fiscal_year = match.group(1)
        candidates.append(HandbookSource(fiscal_year, urljoin(HANDBOOK_PAGE_URL, href)))

    if not candidates:
        text_pattern = re.compile(r"Handbook on Indian Insurance Statistics (\d{4}-\d{2})", re.IGNORECASE)
        years = sorted(set(text_pattern.findall(html)), key=_fiscal_year_end, reverse=True)
        found = ", ".join(years[:3]) or "none"
        raise RuntimeError(
            "Could not find a handbook ZIP link on the IRDAI handbook page. "
            f"Visible handbook years: {found}."
        )

    return max(candidates, key=lambda source: _fiscal_year_end(source.fiscal_year))


def download_and_extract(source: HandbookSource, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    zip_path = work_dir / f"Handbook_{source.fiscal_year}.zip"
    extract_dir = work_dir / source.fiscal_year

    print(f"Downloading {source.fiscal_year} handbook from IRDAI...")
    response = requests.get(source.url, headers=request_headers(), timeout=180)
    response.raise_for_status()
    if response.content[:4] != b"PK\x03\x04":
        raise RuntimeError(
            "IRDAI did not return a ZIP file. The page may have changed or "
            "temporarily blocked automated downloads."
        )

    zip_path.write_bytes(response.content)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)

    for candidate in extract_dir.rglob("Part II.xlsx"):
        return candidate.parent
    raise FileNotFoundError(f"Part II.xlsx was not found after extracting {zip_path}.")


def parse_table_39(wb_path: Path, fiscal_year: str) -> dict[str, int | None]:
    df = pd.read_excel(wb_path, sheet_name="39", header=None)
    reference_year = _fiscal_year_end(fiscal_year)
    result: dict[str, int | None] = {}

    for index in range(T39_HEADER_ROWS, len(df)):
        if not _is_data_row(df.iloc[index, 0]):
            continue
        name = str(df.iloc[index, 1]).strip()
        year_op = df.iloc[index, T39_COL_YEAR_OF_OPERATION]
        age = None
        if pd.notna(year_op):
            try:
                start = int(str(year_op).strip().split("-")[0])
                age = reference_year - start
            except ValueError:
                pass
        result[name] = age
    return result


def parse_table_53(wb_path: Path, fiscal_year: str) -> dict:
    df = pd.read_excel(wb_path, sheet_name="53", header=None)
    years = latest_years(fiscal_year, 4)
    result = {}

    for index in range(T53_HEADER_ROWS, len(df)):
        if not _is_data_row(df.iloc[index, 0]):
            continue
        name = str(df.iloc[index, 1]).strip()
        yearly: dict[str, float] = {}
        for year, offset in zip(years, T53_LATEST_4_YEAR_OFFSETS):
            paid = _numeric(df.iloc[index, offset + T53_COL_PAID])
            repudiated = _numeric(df.iloc[index, offset + T53_COL_REPUDIATED])
            if pd.notna(paid) and pd.notna(repudiated) and (paid + repudiated) > 0:
                yearly[year] = paid / (paid + repudiated)
        if yearly:
            result[name] = {
                "yearly_csr": yearly,
                "avg_csr": float(np.mean(list(yearly.values()))),
            }
    return result


def parse_table_56(wb_path: Path, fiscal_year: str) -> dict:
    df = pd.read_excel(wb_path, sheet_name=" 56", header=None)
    years = latest_years(fiscal_year, 3)
    previous_years = years[:2]
    latest_year = years[-1]
    companies: dict[str, dict[str, float]] = {}

    for index in range(T56_HEADER_ROWS, len(df)):
        if not _is_data_row(df.iloc[index, 0]):
            continue
        name = str(df.iloc[index, 1]).strip()
        yearly: dict[str, float] = {}
        for year, col in zip(previous_years, T56_PREVIOUS_REPORTED_COLS):
            value = _numeric(df.iloc[index, col])
            if pd.notna(value):
                yearly[year] = value
        companies[name] = yearly

    for index in range(T56_HEADER_ROWS, len(df)):
        insurer_raw = df.iloc[index, T56_LATEST_INSURER_COL]
        if pd.isna(insurer_raw):
            continue
        name_latest = str(insurer_raw).strip()
        if not name_latest or name_latest == "nan" or _is_section_header(name_latest):
            continue

        value = _numeric(df.iloc[index, T56_LATEST_REPORTED_COL])
        if pd.isna(value):
            continue

        normalized_latest = _normalize(name_latest)
        for existing in companies:
            if _normalize(existing) == normalized_latest:
                companies[existing][latest_year] = value
                break
        else:
            companies[name_latest] = {latest_year: value}

    result = {}
    for name, yearly in companies.items():
        values = [value for value in yearly.values() if pd.notna(value)]
        if values:
            result[name] = {
                "yearly_complaints": yearly,
                "avg_complaints": float(np.mean(values)),
            }
    return result


def parse_table_62(wb_path: Path, fiscal_year: str) -> dict:
    df = pd.read_excel(wb_path, sheet_name="62", header=None)
    years = latest_years(fiscal_year, 3)
    result = {}

    for index in range(T62_HEADER_ROWS, len(df)):
        if not _is_data_row(df.iloc[index, 0]):
            continue
        name = str(df.iloc[index, 1]).strip()
        yearly: dict[str, float] = {}
        for year, col in zip(years, T62_LATEST_3_TOTAL_ICR_COLS):
            value = _numeric(df.iloc[index, col])
            if pd.notna(value):
                yearly[year] = value
        if yearly:
            result[name] = {
                "yearly_icr": yearly,
                "avg_icr": float(np.mean(list(yearly.values()))),
            }
    return result


def _best_name(norm: str, *dicts) -> str:
    candidates: list[str] = []
    for data in dicts:
        for key in data:
            if _normalize(key) == norm:
                candidates.append(_clean_name(key))
    return max(candidates, key=len) if candidates else norm


def merge_all(ages, claims, complaints, icr, fiscal_year: str) -> pd.DataFrame:
    csr_years = latest_years(fiscal_year, 4)
    recent_years = latest_years(fiscal_year, 3)
    all_names: set[str] = set()
    all_names.update(ages)
    all_names.update(claims)
    all_names.update(complaints)
    all_names.update(icr)

    rows = []
    seen: set[str] = set()
    for name in sorted(all_names):
        norm = _normalize(name)
        if norm in seen:
            continue
        seen.add(norm)

        age = _find(name, ages)
        cl = _find(name, claims)
        co = _find(name, complaints)
        ic = _find(name, icr)
        row: dict = {
            "Company": _best_name(norm, ages, claims, complaints, icr),
            "Track Record (Years)": age,
            "4-yr Avg CSR (%)": round(cl["avg_csr"] * 100, 2) if cl else None,
            "3-yr Avg Complaints": round(co["avg_complaints"]) if co else None,
            "3-yr Avg ICR (%)": round(ic["avg_icr"] * 100, 2) if ic else None,
        }

        for year in csr_years:
            value = cl["yearly_csr"].get(year) if cl else None
            row[f"CSR {year} (%)"] = round(value * 100, 2) if value else None
        for year in recent_years:
            value = co["yearly_complaints"].get(year) if co else None
            row[f"Complaints {year}"] = int(value) if value and pd.notna(value) else None
        for year in recent_years:
            value = ic["yearly_icr"].get(year) if ic else None
            row[f"ICR {year} (%)"] = round(value * 100, 2) if value else None

        rows.append(row)
    return pd.DataFrame(rows)


def save_excel(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Analysis", index=False)
        ws = writer.sheets["Analysis"]
        for col_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len, 30)


def build_analysis(work_dir: Path, source: HandbookSource | None = None) -> tuple[pd.DataFrame, HandbookSource]:
    source = source or discover_latest_handbook()
    handbook_dir = download_and_extract(source, work_dir)
    part2 = handbook_dir / "Part II.xlsx"
    part3 = handbook_dir / "Part III.xlsx"
    for path in (part2, part3):
        if not path.exists():
            raise FileNotFoundError(f"{path} was not found in the extracted handbook.")

    print(f"Using handbook data from: {handbook_dir}")
    ages = parse_table_39(part2, source.fiscal_year)
    claims = parse_table_53(part2, source.fiscal_year)
    complaints = parse_table_56(part2, source.fiscal_year)
    icr = parse_table_62(part3, source.fiscal_year)
    return merge_all(ages, claims, complaints, icr, source.fiscal_year), source


def main(argv: list[str] | None = None) -> int:
    work_dir = Path(argv[0]) if argv else Path(".tmp_insurance_handbook")
    df, source = build_analysis(work_dir)
    output = Path("insurance") / "Insurance_Analysis.xlsx"
    save_excel(df, output)
    print(f"Wrote {len(df)} rows for {source.fiscal_year}: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
