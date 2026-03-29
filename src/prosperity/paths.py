from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from prosperity.utils import ensure_dir


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return current


@dataclass(frozen=True)
class RepoPaths:
    root: Path
    src: Path
    config: Path
    docs: Path
    data: Path
    corpora: Path
    caches: Path
    db_dir: Path
    artifacts: Path
    strategies: Path
    runs: Path
    reports: Path
    submissions: Path
    research_repos: Path
    backtester: Path
    baselines: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> "RepoPaths":
        root = find_repo_root(start)
        data = ensure_dir(root / "data")
        artifacts = ensure_dir(root / "artifacts")
        return cls(
            root=root,
            src=root / "src",
            config=root / "config",
            docs=root / "docs",
            data=data,
            corpora=ensure_dir(data / "corpora"),
            caches=ensure_dir(data / "caches"),
            db_dir=ensure_dir(data / "db"),
            artifacts=artifacts,
            strategies=ensure_dir(artifacts / "strategies"),
            runs=ensure_dir(artifacts / "runs"),
            reports=ensure_dir(artifacts / "reports"),
            submissions=ensure_dir(artifacts / "submissions"),
            research_repos=root / ".research_repos",
            backtester=root / "prosperity_rust_backtester",
            baselines=root / "baselines",
        )
