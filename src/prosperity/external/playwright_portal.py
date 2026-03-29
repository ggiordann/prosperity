from __future__ import annotations

from pathlib import Path


def dry_run_upload(package_dir: Path) -> dict:
    return {
        "mode": "dry-run",
        "adapter": "playwright",
        "package_dir": str(package_dir),
        "status": "not-executed",
    }


def upload_with_playwright(package_dir: Path, enabled: bool) -> dict:
    if not enabled:
        return dry_run_upload(package_dir)
    try:
        import playwright  # noqa: F401
    except Exception as exc:
        raise RuntimeError("Playwright portal adapter requested but playwright is not installed.") from exc
    return {"mode": "live", "adapter": "playwright", "package_dir": str(package_dir), "status": "ready"}
