#!/usr/bin/env python3
"""Fine-tune chennethelius Round 3 v24 until it reaches a target PnL.

This script searches parameter overrides for:

    .research_repos/p4-chennethelius/strategies/round3/v24_partial_hedge.py

It uses the local Rust backtester against round 3 data, writes a full trial
log under:

    analysis/chennethelius_v24_tuning/

and stops early once it finds a configuration whose total round-3 PnL is at
or above the target threshold.

The search is finite. It uses a coordinate-style sweep over a small parameter
grid around the current v24 baseline rather than tuning forever.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKTESTER_DIR = (REPO_ROOT / "prosperity_rust_backtester").resolve()
TRADER_PATH = (
    REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v24_partial_hedge.py"
).resolve()
OUTPUT_DIR = (REPO_ROOT / "analysis" / "chennethelius_v24_tuning").resolve()
RUN_OUTPUT_DIR = (OUTPUT_DIR / "rust_runs").resolve()
BACKTESTER_RELEASE_BIN = (BACKTESTER_DIR / "target" / "release" / "rust_backtester").resolve()
BACKTESTER_DEBUG_BIN = (BACKTESTER_DIR / "target" / "debug" / "rust_backtester").resolve()
TUNER_ENV_VAR = "ROUND3_V24_TUNER_JSON"
ROUND3_DAYS = (0, 1, 2)

SUMMARY_ROW_RE = re.compile(
    r"^(?P<dataset>\S+)\s+"
    r"(?P<day>-?\d+|all|-)\s+"
    r"(?P<ticks>\d+)\s+"
    r"(?P<own_trades>\d+)\s+"
    r"(?P<pnl>-?\d+(?:\.\d+)?)\s+",
    re.MULTILINE,
)

DEFAULT_CONFIG: dict[str, float | int] = {
    "hedge_gain": 0.3,
    "hp_fair_static": 10030,
    "hp_mr_gain": 1000,
    "hp_take_max_pay": -6,
    "hp_quote_edge": 3,
    "hp_quote_size": 30,
    "vfe_fair_static": 5275,
    "vfe_mr_gain": 2000,
    "vfe_take_max_pay": -2,
    "vfe_quote_edge": 1,
    "vfe_quote_size": 30,
    "informed_gain_s": 10,
}

SEARCH_GRID: tuple[tuple[str, tuple[float | int, ...]], ...] = (
    ("hedge_gain", (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)),
    ("hp_mr_gain", (500, 750, 1000, 1250, 1500)),
    ("vfe_mr_gain", (1500, 1750, 2000, 2250, 2500, 3000)),
    ("hp_fair_static", (9990, 10000, 10015, 10030, 10045)),
    ("vfe_fair_static", (5250, 5260, 5275, 5290, 5300)),
    ("hp_take_max_pay", (-7, -6, -5, -4)),
    ("vfe_take_max_pay", (-3, -2, -1)),
    ("informed_gain_s", (6, 8, 10, 12)),
)


@dataclass(frozen=True)
class TrialResult:
    run_id: str
    config: dict[str, float | int]
    total_pnl: float
    day_pnls: dict[int, float]
    own_trades: int
    min_day_pnl: float
    mean_day_pnl: float
    day_std_pnl: float
    pseudo_sharpe: float
    stdout_tail: str
    stderr_tail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune v24_partial_hedge to a target round-3 PnL.")
    parser.add_argument("--target-pnl", type=float, default=710000.0, help="Stop once total PnL reaches this level.")
    parser.add_argument("--passes", type=int, default=3, help="Maximum coordinate-search passes.")
    parser.add_argument(
        "--max-evals",
        type=int,
        default=0,
        help="Optional hard cap on evaluations. Zero means unlimited.",
    )
    parser.add_argument(
        "--keep-old-artifacts",
        action="store_true",
        help="Keep existing output files instead of clearing the tuning directory first.",
    )
    return parser.parse_args()


def windows_to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return str(resolved)
    posix = resolved.as_posix()
    return f"/mnt/{resolved.drive[0].lower()}{posix[2:]}"


def bash_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def ensure_output_dir(keep_old_artifacts: bool) -> None:
    if not keep_old_artifacts and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_backtester_runner() -> tuple[list[str], bool]:
    if os.name == "nt":
        wsl = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl:
            raise FileNotFoundError("WSL is required on Windows for this tuning flow, but wsl.exe was not found.")
        if BACKTESTER_RELEASE_BIN.exists():
            return [wsl, "--cd", str(BACKTESTER_DIR), "./target/release/rust_backtester"], True
        if BACKTESTER_DEBUG_BIN.exists():
            return [wsl, "--cd", str(BACKTESTER_DIR), "./target/debug/rust_backtester"], True
        return [wsl, "--cd", str(BACKTESTER_DIR), "./scripts/cargo_local.sh", "run", "--release", "--"], True

    if BACKTESTER_RELEASE_BIN.exists():
        return [str(BACKTESTER_RELEASE_BIN)], False
    if BACKTESTER_DEBUG_BIN.exists():
        return [str(BACKTESTER_DEBUG_BIN)], False

    cargo = shutil.which("cargo")
    if cargo:
        return [cargo, "run", "--release", "--quiet", "--"], False
    raise FileNotFoundError("Could not find a runnable Rust backtester.")


def parse_summary(stdout: str) -> tuple[dict[int, float], float, int]:
    day_pnls: dict[int, float] = {}
    total_pnl: float | None = None
    total_own_trades: int | None = None

    for match in SUMMARY_ROW_RE.finditer(stdout):
        dataset = match.group("dataset")
        day_label = match.group("day")
        own_trades = int(match.group("own_trades"))
        pnl = float(match.group("pnl"))
        if dataset == "TOTAL":
            total_pnl = pnl
            total_own_trades = own_trades
            continue
        if day_label in ("all", "-"):
            continue
        day_pnls[int(day_label)] = pnl

    if total_pnl is None:
        if not day_pnls:
            raise RuntimeError(f"Could not parse backtester output:\n{stdout}")
        total_pnl = sum(day_pnls.values())
    if total_own_trades is None:
        total_own_trades = 0
    return day_pnls, total_pnl, total_own_trades


def metric_bundle(day_pnls: dict[int, float]) -> tuple[float, float, float, float]:
    values = [day_pnls[day] for day in ROUND3_DAYS if day in day_pnls]
    min_day = min(values)
    mean_day = statistics.fmean(values)
    day_std = statistics.pstdev(values) if len(values) > 1 else 0.0
    pseudo_sharpe = mean_day / day_std if day_std > 0 else float("inf")
    return min_day, mean_day, day_std, pseudo_sharpe


def score_tuple(result: TrialResult) -> tuple[float, float, float, float]:
    return (result.total_pnl, result.min_day_pnl, result.pseudo_sharpe, -result.day_std_pnl)


def better_result(left: TrialResult, right: TrialResult | None) -> bool:
    if right is None:
        return True
    return score_tuple(left) > score_tuple(right)


def compact_value(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{float(value):g}".replace(".", "p")


def make_run_id(config: dict[str, float | int], attempt_index: int) -> str:
    pieces = [
        f"hg{compact_value(config['hedge_gain'])}",
        f"hpmr{compact_value(config['hp_mr_gain'])}",
        f"vfemr{compact_value(config['vfe_mr_gain'])}",
        f"hpf{compact_value(config['hp_fair_static'])}",
        f"vfef{compact_value(config['vfe_fair_static'])}",
        f"ig{compact_value(config['informed_gain_s'])}",
    ]
    return f"v24-tune-{'-'.join(pieces)}-{attempt_index}-{int(time.time() * 1000)}"


def tuner_env(config: dict[str, float | int]) -> dict[str, str]:
    env = os.environ.copy()
    env[TUNER_ENV_VAR] = json.dumps(config, separators=(",", ":"))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_backtest(
    runner_prefix: list[str],
    use_wsl_paths: bool,
    config: dict[str, float | int],
    attempt_index: int,
) -> TrialResult:
    run_id = make_run_id(config, attempt_index)
    trader_arg = windows_to_wsl_path(TRADER_PATH) if use_wsl_paths else str(TRADER_PATH)
    output_root_arg = windows_to_wsl_path(RUN_OUTPUT_DIR) if use_wsl_paths else str(RUN_OUTPUT_DIR)
    override_json = json.dumps(config, separators=(",", ":"))

    if use_wsl_paths:
        executable = runner_prefix[-1]
        backtester_dir_wsl = windows_to_wsl_path(BACKTESTER_DIR)
        bash_command = " ".join(
            [
                f"cd {bash_quote(backtester_dir_wsl)}",
                "&&",
                f"export {TUNER_ENV_VAR}={bash_quote(override_json)}",
                "&&",
                executable,
                "--trader",
                bash_quote(trader_arg),
                "--dataset",
                "round3",
                "--run-id",
                bash_quote(run_id),
                "--output-root",
                bash_quote(output_root_arg),
                "--artifact-mode",
                "none",
                "--products",
                "off",
            ]
        )
        proc = subprocess.run(
            [runner_prefix[0], "bash", "-lc", bash_command],
            cwd=BACKTESTER_DIR,
            text=True,
            capture_output=True,
            check=False,
            timeout=600,
        )
    else:
        cmd = [
            *runner_prefix,
            "--trader",
            trader_arg,
            "--dataset",
            "round3",
            "--run-id",
            run_id,
            "--output-root",
            output_root_arg,
            "--artifact-mode",
            "none",
            "--products",
            "off",
        ]
        proc = subprocess.run(
            cmd,
            cwd=BACKTESTER_DIR,
            text=True,
            capture_output=True,
            check=False,
            env=tuner_env(config),
            timeout=600,
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Backtest failed for config {config}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    day_pnls, total_pnl, own_trades = parse_summary(proc.stdout)
    min_day, mean_day, day_std, pseudo_sharpe = metric_bundle(day_pnls)
    return TrialResult(
        run_id=run_id,
        config=dict(config),
        total_pnl=total_pnl,
        day_pnls=day_pnls,
        own_trades=own_trades,
        min_day_pnl=min_day,
        mean_day_pnl=mean_day,
        day_std_pnl=day_std,
        pseudo_sharpe=pseudo_sharpe,
        stdout_tail=proc.stdout.strip()[-1200:],
        stderr_tail=proc.stderr.strip()[-1200:],
    )


def write_trial_log(trials: list[TrialResult]) -> None:
    csv_path = OUTPUT_DIR / "trial_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "run_id",
                "total_pnl",
                "day_0_pnl",
                "day_1_pnl",
                "day_2_pnl",
                "min_day_pnl",
                "mean_day_pnl",
                "day_std_pnl",
                "pseudo_sharpe",
                "own_trades",
                *DEFAULT_CONFIG.keys(),
            ]
        )
        for trial in sorted(trials, key=score_tuple, reverse=True):
            writer.writerow(
                [
                    trial.run_id,
                    f"{trial.total_pnl:.2f}",
                    f"{trial.day_pnls.get(0, 0.0):.2f}",
                    f"{trial.day_pnls.get(1, 0.0):.2f}",
                    f"{trial.day_pnls.get(2, 0.0):.2f}",
                    f"{trial.min_day_pnl:.2f}",
                    f"{trial.mean_day_pnl:.2f}",
                    f"{trial.day_std_pnl:.2f}",
                    f"{trial.pseudo_sharpe:.6f}",
                    trial.own_trades,
                    *[trial.config[key] for key in DEFAULT_CONFIG],
                ]
            )


def materialize_best_config(base_source: str, best_config: dict[str, float | int]) -> str:
    substitutions = {
        'INFORMED_GAIN_S = override_float(RUNTIME_OVERRIDES, "informed_gain_s", 10)': (
            f'INFORMED_GAIN_S = {float(best_config["informed_gain_s"]):g}'
        ),
        'HEDGE_GAIN = override_float(RUNTIME_OVERRIDES, "hedge_gain", 0.3)': (
            f'HEDGE_GAIN = {float(best_config["hedge_gain"]):g}'
        ),
        'HP_FAIR_STATIC = override_int(RUNTIME_OVERRIDES, "hp_fair_static", 10030)': (
            f'HP_FAIR_STATIC = {int(best_config["hp_fair_static"])}'
        ),
        'HP_MR_GAIN = override_int(RUNTIME_OVERRIDES, "hp_mr_gain", 1000)': (
            f'HP_MR_GAIN = {int(best_config["hp_mr_gain"])}'
        ),
        'HP_TAKE_MAX_PAY = override_int(RUNTIME_OVERRIDES, "hp_take_max_pay", -6)': (
            f'HP_TAKE_MAX_PAY = {int(best_config["hp_take_max_pay"])}'
        ),
        'HP_QUOTE_EDGE = override_int(RUNTIME_OVERRIDES, "hp_quote_edge", 3)': (
            f'HP_QUOTE_EDGE = {int(best_config["hp_quote_edge"])}'
        ),
        'HP_QUOTE_SIZE = override_int(RUNTIME_OVERRIDES, "hp_quote_size", 30)': (
            f'HP_QUOTE_SIZE = {int(best_config["hp_quote_size"])}'
        ),
        'VFE_FAIR_STATIC = override_int(RUNTIME_OVERRIDES, "vfe_fair_static", 5275)': (
            f'VFE_FAIR_STATIC = {int(best_config["vfe_fair_static"])}'
        ),
        'VFE_MR_GAIN = override_int(RUNTIME_OVERRIDES, "vfe_mr_gain", 2000)': (
            f'VFE_MR_GAIN = {int(best_config["vfe_mr_gain"])}'
        ),
        'VFE_TAKE_MAX_PAY = override_int(RUNTIME_OVERRIDES, "vfe_take_max_pay", -2)': (
            f'VFE_TAKE_MAX_PAY = {int(best_config["vfe_take_max_pay"])}'
        ),
        'VFE_QUOTE_EDGE = override_int(RUNTIME_OVERRIDES, "vfe_quote_edge", 1)': (
            f'VFE_QUOTE_EDGE = {int(best_config["vfe_quote_edge"])}'
        ),
        'VFE_QUOTE_SIZE = override_int(RUNTIME_OVERRIDES, "vfe_quote_size", 30)': (
            f'VFE_QUOTE_SIZE = {int(best_config["vfe_quote_size"])}'
        ),
    }
    tuned_source = base_source
    for old, new in substitutions.items():
        tuned_source = tuned_source.replace(old, new)
    return tuned_source


def write_best_artifacts(best_result: TrialResult) -> None:
    (OUTPUT_DIR / "best_config.json").write_text(
        json.dumps(best_result.config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "target_pnl": best_result.total_pnl,
        "day_pnls": best_result.day_pnls,
        "min_day_pnl": best_result.min_day_pnl,
        "mean_day_pnl": best_result.mean_day_pnl,
        "day_std_pnl": best_result.day_std_pnl,
        "pseudo_sharpe": best_result.pseudo_sharpe,
        "own_trades": best_result.own_trades,
        "config": best_result.config,
        "run_id": best_result.run_id,
    }
    (OUTPUT_DIR / "best_result.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    base_source = TRADER_PATH.read_text(encoding="utf-8")
    tuned_source = materialize_best_config(base_source, best_result.config)
    (OUTPUT_DIR / "best_v24_partial_hedge.py").write_text(tuned_source, encoding="utf-8")


def main() -> None:
    args = parse_args()
    ensure_output_dir(args.keep_old_artifacts)
    runner_prefix, use_wsl_paths = resolve_backtester_runner()

    trial_cache: dict[tuple[tuple[str, float | int], ...], TrialResult] = {}
    trials: list[TrialResult] = []
    eval_count = 0

    def evaluate(config: dict[str, float | int]) -> TrialResult:
        nonlocal eval_count
        normalized = {key: config.get(key, DEFAULT_CONFIG[key]) for key in DEFAULT_CONFIG}
        cache_key = tuple((key, normalized[key]) for key in DEFAULT_CONFIG)
        cached = trial_cache.get(cache_key)
        if cached is not None:
            return cached
        if args.max_evals and eval_count >= args.max_evals:
            raise RuntimeError(f"Reached max-evals={args.max_evals} before hitting the target.")
        eval_count += 1
        result = run_backtest(runner_prefix, use_wsl_paths, normalized, eval_count)
        trial_cache[cache_key] = result
        trials.append(result)
        print(
            f"[{eval_count}] pnl={result.total_pnl:,.2f} min_day={result.min_day_pnl:,.2f} "
            f"sharpe={result.pseudo_sharpe:.3f} cfg={normalized}",
            flush=True,
        )
        return result

    current_config = dict(DEFAULT_CONFIG)
    best_result = evaluate(current_config)
    if best_result.total_pnl >= args.target_pnl:
        write_trial_log(trials)
        write_best_artifacts(best_result)
        print(f"Target already met by baseline: {best_result.total_pnl:,.2f}", flush=True)
        return

    for pass_index in range(1, args.passes + 1):
        print(f"Starting pass {pass_index}...", flush=True)
        improved_this_pass = False
        for parameter, candidate_values in SEARCH_GRID:
            local_best = best_result
            local_best_config = dict(current_config)
            for candidate_value in candidate_values:
                if current_config[parameter] == candidate_value:
                    continue
                test_config = dict(current_config)
                test_config[parameter] = candidate_value
                result = evaluate(test_config)
                if better_result(result, local_best):
                    local_best = result
                    local_best_config = test_config
                if result.total_pnl >= args.target_pnl:
                    best_result = result
                    current_config = test_config
                    write_trial_log(trials)
                    write_best_artifacts(best_result)
                    print(f"Reached target with {best_result.total_pnl:,.2f}", flush=True)
                    return
            if better_result(local_best, best_result):
                best_result = local_best
                current_config = local_best_config
                improved_this_pass = True
                print(
                    f"Improved via {parameter}: pnl={best_result.total_pnl:,.2f} cfg={current_config}",
                    flush=True,
                )
        if not improved_this_pass:
            print("No further improvement in this pass; stopping early.", flush=True)
            break

    write_trial_log(trials)
    write_best_artifacts(best_result)
    if best_result.total_pnl >= args.target_pnl:
        print(f"Reached target with {best_result.total_pnl:,.2f}", flush=True)
    else:
        print(
            f"Finished search without hitting the target. Best PnL: {best_result.total_pnl:,.2f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
