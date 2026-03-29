from __future__ import annotations

from pathlib import Path

from prosperity.paths import RepoPaths


def discover_backtester_path(paths: RepoPaths, configured_path: str | None = None) -> Path:
    candidates = []
    if configured_path:
        candidates.append((paths.root / configured_path).resolve())
        candidates.append(Path(configured_path).resolve())
    candidates.append(paths.backtester.resolve())
    for candidate in candidates:
        if (candidate / "Cargo.toml").exists() and (candidate / "scripts" / "cargo_local.sh").exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate prosperity_rust_backtester. Set backtester.path in config/settings.yaml."
    )
