from __future__ import annotations

import subprocess

from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.paths import RepoPaths
from prosperity.settings import AppSettings


def test_backtester_runner_persists_logs(tmp_path, monkeypatch, sample_backtester_stdout):
    backtester_root = tmp_path / "backtester"
    (backtester_root / "scripts").mkdir(parents=True)
    (backtester_root / "Cargo.toml").write_text("[package]\nname='demo'\n", encoding="utf-8")
    run_dir = backtester_root / "runs" / "example-run"
    run_dir.mkdir(parents=True)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=sample_backtester_stdout, stderr="")

    monkeypatch.setattr("prosperity.backtester.runner.discover_backtester_path", lambda paths, configured_path=None: backtester_root)
    monkeypatch.setattr("subprocess.run", fake_run)

    root = tmp_path / "repo"
    root.mkdir()
    paths = RepoPaths.discover(root)
    settings = AppSettings()
    runner = BacktesterRunner(paths, settings)
    result = runner.run(BacktestRequest(trader_path="/tmp/trader.py", dataset="tutorial"))

    summary_path = paths.runs / result.run_id / "summary.json"
    assert summary_path.exists()
    assert result.summary.total_final_pnl == 2770.5
