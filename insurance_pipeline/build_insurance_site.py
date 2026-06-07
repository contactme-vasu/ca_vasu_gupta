"""Refresh the public /insurance/ website data."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from insurance_pipeline.analyzer import build_analysis, save_excel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "insurance"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the latest IRDAI handbook and rebuild /insurance/ data."
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help="Static website folder to update.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the downloaded/extracted handbook in .tmp_insurance_handbook.",
    )
    parser.add_argument(
        "--require-current-cycle",
        action="store_true",
        help="Fail if IRDAI has not published the expected handbook for this annual cycle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    work_dir = PROJECT_ROOT / ".tmp_insurance_handbook"

    if args.keep_work_dir:
        work_dir.mkdir(parents=True, exist_ok=True)
        df, source = build_analysis(work_dir)
    else:
        with tempfile.TemporaryDirectory(prefix="insurance-handbook-") as tmp:
            df, source = build_analysis(Path(tmp))

    if args.require_current_cycle:
        expected = expected_fiscal_year_for_annual_cycle()
        if source.fiscal_year != expected:
            raise RuntimeError(
                f"Latest IRDAI handbook is {source.fiscal_year}, but this annual "
                f"cycle expects {expected}. No public website files were updated."
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = output_dir / "Insurance_Analysis.xlsx"
    data_path = output_dir / "data.json"

    save_excel(df, workbook_path)
    write_site_json(df, source.fiscal_year, data_path)

    if not args.keep_work_dir and work_dir.exists():
        shutil.rmtree(work_dir)

    print(f"Updated insurance workbook: {workbook_path}")
    print(f"Updated insurance JSON: {data_path}")
    print("Publish URL path: /insurance/")
    return 0


def write_site_json(df: pd.DataFrame, fiscal_year: str, output_path: Path) -> None:
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataUpdatedThrough": fiscal_year,
        "sourceWorkbook": "Insurance_Analysis.xlsx",
        "source": f"IRDAI Handbook on Indian Insurance Statistics {fiscal_year}",
        "rows": _clean_for_json(df.to_dict(orient="records")),
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def expected_fiscal_year_for_annual_cycle(today: date | None = None) -> str:
    today = today or date.today()
    end_year = today.year - 1
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _clean_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_for_json(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())
