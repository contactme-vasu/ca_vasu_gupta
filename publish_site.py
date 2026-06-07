"""Build and optionally push the static website files from cached site data."""

import argparse
import subprocess
from pathlib import Path

from web_export.export_static_site import build_site, load_site_data


PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build the static /index/ website from cache/site_data.json."
    )
    parser.add_argument(
        "--data",
        default=PROJECT_ROOT / "cache" / "site_data.json",
        type=Path,
        help="Path to the precomputed public site data JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default=PROJECT_ROOT / "index",
        type=Path,
        help="Folder that should contain the generated /index/ website files.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Commit and push the generated website files if output-dir is inside a Git repository.",
    )
    parser.add_argument(
        "--message",
        default="Update index analysis website",
        help="Git commit message used with --push.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    data_path = args.data.resolve()
    output_dir = args.output_dir.resolve()

    data = load_site_data(data_path)
    build_site(data, output_dir, project_root=PROJECT_ROOT)
    print(f"Static website updated: {output_dir}")
    print("Publish URL path: /index/")

    if args.push:
        commit_and_push(output_dir, args.message)


def commit_and_push(output_dir: Path, message: str) -> None:
    repo_root = _git_repo_root(output_dir)
    relative_output = output_dir.relative_to(repo_root)

    _run_git(repo_root, "add", str(relative_output))
    status = _run_git(repo_root, "status", "--porcelain", str(relative_output), capture=True)
    if not status.strip():
        print("No website changes to commit.")
        return

    _run_git(repo_root, "commit", "-m", message)
    _run_git(repo_root, "push")
    print("Website changes committed and pushed.")


def _git_repo_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _run_git(repo_root: Path, *args: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=capture,
        text=True,
    )
    return result.stdout if capture else ""


if __name__ == "__main__":
    main()

