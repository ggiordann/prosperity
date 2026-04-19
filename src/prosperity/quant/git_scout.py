from __future__ import annotations

import subprocess
from pathlib import Path

from prosperity.quant.models import ChangedFile, GitCommitInsight, GitScoutResult

STRATEGY_HINT_DIRS = (
    "baselines/",
    "current_best_algo/",
    "artifacts/strategies/",
    "round 1/submissions/",
)


def _run_git(root: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=check,
    )


def _classify_file(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".py") and any(path.startswith(prefix) for prefix in STRATEGY_HINT_DIRS):
        return "strategy_code"
    if lower.endswith(".py"):
        return "python_code"
    if lower.endswith((".md", ".txt", ".rst")):
        return "research_note"
    if lower.endswith((".yaml", ".yml", ".toml", ".json")):
        return "config_change"
    if lower.endswith(".csv"):
        return "data_change"
    if "backtester" in lower or lower.endswith((".rs", "cargo.lock")):
        return "backtester_change"
    return "docs_or_other"


def _commit_subject(root: Path, sha: str) -> tuple[str, str]:
    result = _run_git(root, ["show", "-s", "--format=%s%x00%an", sha])
    if result.returncode != 0:
        return sha[:8], "unknown"
    subject, _, author = result.stdout.strip().partition("\x00")
    return subject or sha[:8], author or "unknown"


def _changed_files_for_commit(root: Path, sha: str, max_files: int) -> list[ChangedFile]:
    result = _run_git(root, ["diff-tree", "--no-commit-id", "--name-status", "-r", sha])
    if result.returncode != 0:
        return []
    changed: list[ChangedFile] = []
    for line in result.stdout.splitlines()[:max_files]:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        changed.append(
            ChangedFile(
                path=path,
                status=status,
                category=_classify_file(path),
                exists=(root / path).exists(),
            )
        )
    return changed


def _rev_parse(root: Path, ref: str) -> str | None:
    result = _run_git(root, ["rev-parse", "--verify", ref])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def scout_git_commits(
    root: Path,
    *,
    last_seen_sha: str | None,
    fetch_remote: bool,
    initial_scan_commits: int,
    max_files: int,
) -> GitScoutResult:
    fetched = False
    error = None
    if fetch_remote:
        fetch = _run_git(root, ["fetch", "--quiet", "origin", "main"])
        fetched = fetch.returncode == 0
        if fetch.returncode != 0:
            error = fetch.stderr.strip() or "git fetch failed"

    target_sha = _rev_parse(root, "origin/main") or _rev_parse(root, "HEAD")
    if target_sha is None:
        return GitScoutResult(
            base_sha=last_seen_sha,
            target_sha=None,
            commits=[],
            candidate_strategy_files=[],
            fetched=fetched,
            error=error or "could not resolve git target",
        )

    if last_seen_sha:
        rev_range = f"{last_seen_sha}..{target_sha}"
        commit_result = _run_git(root, ["rev-list", "--reverse", rev_range])
    else:
        commit_result = _run_git(root, ["rev-list", "--reverse", f"--max-count={initial_scan_commits}", target_sha])

    shas = [line.strip() for line in commit_result.stdout.splitlines() if line.strip()]
    commits: list[GitCommitInsight] = []
    candidate_strategy_files: list[str] = []
    for sha in shas:
        subject, author = _commit_subject(root, sha)
        changed_files = _changed_files_for_commit(root, sha, max_files)
        commits.append(
            GitCommitInsight(
                sha=sha,
                subject=subject,
                author=author,
                changed_files=changed_files,
            )
        )
        for changed in changed_files:
            if changed.category == "strategy_code" and changed.exists and changed.path not in candidate_strategy_files:
                candidate_strategy_files.append(changed.path)

    return GitScoutResult(
        base_sha=last_seen_sha,
        target_sha=target_sha,
        commits=commits,
        candidate_strategy_files=candidate_strategy_files,
        fetched=fetched,
        error=error,
    )
