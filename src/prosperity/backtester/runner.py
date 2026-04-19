from __future__ import annotations

import subprocess
from uuid import uuid4

from pydantic import BaseModel

from prosperity.backtester.artifacts import collect_run_dirs
from prosperity.backtester.discovery import discover_backtester_path
from prosperity.backtester.parser import BacktestSummary, parse_backtester_output, summary_to_dict
from prosperity.paths import RepoPaths
from prosperity.settings import AppSettings
from prosperity.utils import ensure_dir, json_dumps, utcnow_iso


class BacktestRequest(BaseModel):
    trader_path: str
    dataset: str
    day: int | None = None
    persist: bool = False
    products_mode: str = "summary"
    trade_match_mode: str | None = None
    queue_penetration: float | None = None
    price_slippage_bps: float | None = None


class BacktestResult(BaseModel):
    run_id: str
    request: BacktestRequest
    summary: BacktestSummary
    stdout: str
    stderr: str
    run_dirs: list[str]
    created_at: str


class BacktesterRunner:
    def __init__(self, paths: RepoPaths, settings: AppSettings):
        self.paths = paths
        self.settings = settings
        self.backtester_root = discover_backtester_path(paths, settings.backtester.path)

    def run(self, request: BacktestRequest) -> BacktestResult:
        cargo_wrapper = self.backtester_root / "scripts" / "cargo_local.sh"
        cargo_command = ["./scripts/cargo_local.sh"] if cargo_wrapper.exists() else ["cargo"]
        command = [
            *cargo_command,
            "run",
            "--",
            "--trader",
            request.trader_path,
            "--dataset",
            request.dataset,
            "--products",
            request.products_mode,
        ]
        if request.day is not None:
            command.append(f"--day={request.day}")
        if request.persist:
            command.append("--persist")
        if request.trade_match_mode:
            command.extend(["--trade-match-mode", request.trade_match_mode])
        if request.queue_penetration is not None:
            command.extend(["--queue-penetration", str(request.queue_penetration)])
        if request.price_slippage_bps is not None:
            command.extend(["--price-slippage-bps", str(request.price_slippage_bps)])

        process = subprocess.run(
            command,
            cwd=self.backtester_root,
            capture_output=True,
            text=True,
            check=False,
        )
        summary = parse_backtester_output(process.stdout)
        run_id = uuid4().hex
        result = BacktestResult(
            run_id=run_id,
            request=request,
            summary=summary,
            stdout=process.stdout,
            stderr=process.stderr,
            run_dirs=[str(path) for path in collect_run_dirs(summary, self.backtester_root)],
            created_at=utcnow_iso(),
        )
        self._persist_logs(result)
        if process.returncode != 0:
            raise RuntimeError(
                f"Backtester failed with exit code {process.returncode}\n{process.stdout}\n{process.stderr}"
            )
        return result

    def _persist_logs(self, result: BacktestResult) -> None:
        run_dir = ensure_dir(self.paths.runs / result.run_id)
        (run_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        (run_dir / "summary.json").write_text(
            json_dumps(summary_to_dict(result.summary)),
            encoding="utf-8",
        )
