from __future__ import annotations

from pathlib import Path


def prepare_equirag_bundle(package_dir: Path, enabled: bool = False) -> dict:
    return {
        "adapter": "equirag",
        "enabled": enabled,
        "package_dir": str(package_dir),
        "status": "dry-run" if not enabled else "ready",
    }
