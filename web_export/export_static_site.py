from __future__ import annotations

import json
import shutil
from pathlib import Path


STATIC_FILES = ("index.html", "app.js", "styles.css")


def build_site(data: dict, output_dir: Path, project_root: Path | None = None) -> None:
    """Write the static /index/ website from precomputed public analysis data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    for filename in STATIC_FILES:
        source = Path(__file__).resolve().parent / "static" / filename
        shutil.copyfile(source, output_dir / filename)

    with (output_dir / "data.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    stale_workbook = output_dir / "Output.xlsx"
    if stale_workbook.exists():
        stale_workbook.unlink()

    root = project_root or Path.cwd()
    logo_path = root / "Logo" / "CA India Logo.png"
    if logo_path.exists():
        shutil.copyfile(logo_path, assets_dir / "ca-india-logo.png")


def load_site_data(data_path: Path) -> dict:
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)
