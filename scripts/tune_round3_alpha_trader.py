#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import functools
import json
import os
import re
import statistics
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKTESTER_DIR = (REPO_ROOT / "prosperity_rust_backtester").resolve()
ROUND3_DATASET = (BACKTESTER_DIR / "datasets" / "round3").resolve()
TRADER_PATH = (REPO_ROOT / "round3_alpha_trader.py").resolve()
OUTPUT_DIR = (REPO_ROOT / "analysis" / "round3_alpha_tuning").resolve()
BACKTESTER_RELEASE_BIN = (BACKTESTER_DIR / "target" / "release" / "rust_backtester").resolve()
BACKTESTER_DEBUG_BIN = (BACKTESTER_DIR / "target" / "debug" / "rust_backtester").resolve()

ROUND3_DAYS = (0, 1, 2)
BACKTEST_PRODUCTS_MODE = "off"
BACKTEST_ARTIFACT_MODE = "none"

SUMMARY_ROW_RE = re.compile(
    r"^(?P<dataset>\S+)\s+"
    r"(?P<day>-?\d+|all|-)\s+"
    r"(?P<ticks>\d+)\s+"
    r"(?P<own_trades>\d+)\s+"
    r"(?P<pnl>-?\d+(?:\.\d+)?)\s+",
    re.MULTILINE,
)

DEFAULT_CONFIG: dict[str, float] = {
    "residual_prior_weight": 0.20,
    "underlying_micro_scale": 1.0,
    "underlying_structure_scale": 1.0,
    "underlying_reversion_scale": 1.0,
    "option_micro_scale": 1.0,
    "option_structure_scale": 1.0,
    "option_reversion_scale": 1.0,
}

STAGES: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("residual_prior_weight", (0.0, 0.10, 0.20, 0.30)),
    ("underlying_micro_scale", (0.85, 1.00, 1.15)),
    ("underlying_structure_scale", (0.85, 1.00, 1.15)),
    ("underlying_reversion_scale", (0.75, 1.00, 1.25)),
    ("option_micro_scale", (0.90, 1.00, 1.10, 1.20)),
    ("option_structure_scale", (0.85, 1.00, 1.15)),
    ("option_reversion_scale", (0.75, 1.00, 1.25, 1.50)),
)


@dataclass(frozen=True)
class CandidateResult:
    run_id: str
    stage: str
    parameter: str
    value: float
    config: dict[str, float]
    return_code: int
    total_pnl: float | None
    day_pnls: dict[int, float]
    score: tuple[float, float, float, float]
    status: str
    stdout_tail: str
    stderr_tail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune round 3 alpha trader with the Rust backtester.")
    parser.add_argument("--trader", type=Path, default=TRADER_PATH, help="Trader file to evaluate.")
    parser.add_argument("--dataset", type=Path, default=ROUND3_DATASET, help="Backtester dataset directory.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Directory for sweep outputs.")
    parser.add_argument("--passes", type=int, default=1, help="Coordinate-search passes over the stage list.")
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=0,
        help="Stop after this many evaluated candidates. Zero means unlimited.",
    )
    parser.add_argument(
        "--day",
        type=int,
        default=None,
        help="Optional single day to backtest instead of the full round.",
    )
    return parser.parse_args()


def log_message(message: str, log_file) -> None:
    print(message, flush=True)
    log_file.write(message + "\n")
    log_file.flush()


def make_run_id(stage: str, parameter: str, value: float, index: int) -> str:
    safe_value = format_value(value)
    timestamp = int(time.time() * 1000)
    return f"round3-alpha-{stage}-{parameter}-{safe_value}-{index}-{timestamp}"


def format_value(value: float) -> str:
    sign = "m" if value < 0 else ""
    return sign + f"{abs(value):g}".replace(".", "p")


def normalize_config(config: dict[str, float]) -> dict[str, float]:
    merged = dict(DEFAULT_CONFIG)
    for key, value in config.items():
        try:
            merged[key] = float(value)
        except (TypeError, ValueError):
            continue
    return merged


def compare_score(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> int:
    for lval, rval in zip(left, right):
        if lval > rval:
            return 1
        if lval < rval:
            return -1
    return 0


def candidate_score(total_pnl: float | None, day_pnls: dict[int, float]) -> tuple[float, float, float, float]:
    if total_pnl is None:
        return (float("-inf"), float("-inf"), float("-inf"), float("-inf"))
    day_values = [day_pnls[day] for day in ROUND3_DAYS if day in day_pnls]
    if not day_values:
        return (total_pnl, float("-inf"), float("-inf"), float("-inf"))
    min_day = min(day_values)
    mean_day = statistics.fmean(day_values)
    std_day = statistics.pstdev(day_values) if len(day_values) > 1 else 0.0
    return (total_pnl, min_day, mean_day, -std_day)


def parse_backtester_summary(stdout: str) -> tuple[dict[int, float], float | None]:
    day_pnls: dict[int, float] = {}
    total_pnl: float | None = None
    for match in SUMMARY_ROW_RE.finditer(stdout):
        dataset = match.group("dataset")
        day_label = match.group("day")
        pnl = float(match.group("pnl"))
        if dataset == "TOTAL":
            total_pnl = pnl
            continue
        if day_label in ("all", "-"):
            continue
        day_pnls[int(day_label)] = pnl
    if total_pnl is None and day_pnls:
        total_pnl = sum(day_pnls.values())
    return day_pnls, total_pnl


def rust_env(config: dict[str, float]) -> dict[str, str]:
    env = os.environ.copy()
    env["ROUND3_ALPHA_TUNER_JSON"] = json.dumps(config, separators=(",", ":"))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@functools.lru_cache(maxsize=256)
def windows_to_wsl_path(path_text: str) -> str:
    path = Path(path_text).resolve()
    if os.name != "nt":
        return str(path)

    posix = path.as_posix()
    if len(path.drive) == 2 and path.drive[1] == ":":
        return f"/mnt/{path.drive[0].lower()}{posix[2:]}"
    return posix


def resolve_backtester_runner() -> tuple[list[str], bool, str]:
    if os.name == "nt":
        wsl = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl:
            raise FileNotFoundError(
                "WSL is required on Windows for this backtester, but wsl.exe was not found."
            )

        for candidate, label in (
            (BACKTESTER_RELEASE_BIN, "./target/release/rust_backtester"),
            (BACKTESTER_DEBUG_BIN, "./target/debug/rust_backtester"),
        ):
            if candidate.exists():
                return [wsl, "--cd", str(BACKTESTER_DIR), label], True, f"wsl:{candidate}"

        return [wsl, "--cd", str(BACKTESTER_DIR), "./scripts/cargo_local.sh", "run", "--release", "--"], True, (
            "wsl:./scripts/cargo_local.sh"
        )

    cargo = shutil.which("cargo")
    if cargo:
        return [cargo, "run", "--release", "--quiet", "--"], False, f"cargo:{cargo}"

    for candidate in (BACKTESTER_RELEASE_BIN, BACKTESTER_DEBUG_BIN):
        if candidate.exists():
            return [str(candidate)], False, f"binary:{candidate}"

    raise FileNotFoundError(
        "Could not find a runnable backtester. Expected WSL on Windows, or cargo/a built binary on Linux."
    )


def run_backtester(
    runner_prefix: list[str],
    use_wsl_paths: bool,
    trader_path: Path,
    dataset_path: Path,
    output_root: Path,
    run_id: str,
    config: dict[str, float],
    day: int | None,
) -> subprocess.CompletedProcess[str]:
    if use_wsl_paths:
        trader_arg = windows_to_wsl_path(str(trader_path))
        dataset_arg = windows_to_wsl_path(str(dataset_path))
        output_root_arg = windows_to_wsl_path(str(output_root))
    else:
        trader_arg = str(trader_path)
        dataset_arg = str(dataset_path)
        output_root_arg = str(output_root)

    cmd = [
        *runner_prefix,
        "--trader",
        trader_arg,
        "--dataset",
        dataset_arg,
        "--run-id",
        run_id,
        "--output-root",
        output_root_arg,
        "--artifact-mode",
        BACKTEST_ARTIFACT_MODE,
        "--products",
        BACKTEST_PRODUCTS_MODE,
    ]
    if day is not None:
        cmd.extend(["--day", str(day)])
    return subprocess.run(
        cmd,
        cwd=BACKTESTER_DIR,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=rust_env(config),
    )


def evaluate_candidate(
    *,
    stage: str,
    parameter: str,
    value: float,
    config: dict[str, float],
    candidate_index: int,
    args: argparse.Namespace,
    runner_prefix: list[str],
    use_wsl_paths: bool,
) -> CandidateResult:
    run_id = make_run_id(stage, parameter, value, candidate_index)
    result = run_backtester(
        runner_prefix,
        use_wsl_paths,
        args.trader,
        args.dataset,
        args.output_dir / "runs",
        run_id,
        config,
        args.day,
    )
    day_pnls, total_pnl = parse_backtester_summary(result.stdout)
    score = candidate_score(total_pnl, day_pnls)
    status = "ok" if result.returncode == 0 and total_pnl is not None else "failed"
    return CandidateResult(
        run_id=run_id,
        stage=stage,
        parameter=parameter,
        value=value,
        config=dict(config),
        return_code=result.returncode,
        total_pnl=total_pnl,
        day_pnls=day_pnls,
        score=score,
        status=status,
        stdout_tail=result.stdout[-3000:],
        stderr_tail=result.stderr[-3000:],
    )


def append_jsonl(path: Path, record: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "run_id",
        "stage",
        "parameter",
        "value",
        "status",
        "return_code",
        "total_pnl",
        "day_0_pnl",
        "day_1_pnl",
        "day_2_pnl",
        "min_day_pnl",
        "mean_day_pnl",
        "std_day_pnl",
        "score_total",
        "score_min_day",
        "score_mean_day",
        "score_neg_std",
        "config_json",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def candidate_row(result: CandidateResult) -> dict[str, object]:
    day_values = [result.day_pnls.get(day) for day in ROUND3_DAYS]
    valid = [value for value in day_values if value is not None]
    min_day = min(valid) if valid else None
    mean_day = statistics.fmean(valid) if valid else None
    std_day = statistics.pstdev(valid) if len(valid) > 1 else 0.0 if valid else None
    return {
        "run_id": result.run_id,
        "stage": result.stage,
        "parameter": result.parameter,
        "value": result.value,
        "status": result.status,
        "return_code": result.return_code,
        "total_pnl": result.total_pnl,
        "day_0_pnl": result.day_pnls.get(0),
        "day_1_pnl": result.day_pnls.get(1),
        "day_2_pnl": result.day_pnls.get(2),
        "min_day_pnl": min_day,
        "mean_day_pnl": mean_day,
        "std_day_pnl": std_day,
        "score_total": result.score[0],
        "score_min_day": result.score[1],
        "score_mean_day": result.score[2],
        "score_neg_std": result.score[3],
        "config_json": json.dumps(result.config, sort_keys=True),
    }


def champion_record(result: CandidateResult, reason: str) -> dict[str, object]:
    row = candidate_row(result)
    row["reason"] = reason
    row["stdout_tail"] = result.stdout_tail
    row["stderr_tail"] = result.stderr_tail
    return row


def main() -> int:
    args = parse_args()
    args.trader = args.trader.resolve()
    args.dataset = args.dataset.resolve()
    args.output_dir = args.output_dir.resolve()
    if not args.trader.exists():
        raise FileNotFoundError(f"Trader file not found: {args.trader}")
    if not args.dataset.exists():
        raise FileNotFoundError(f"Dataset path not found: {args.dataset}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = args.output_dir / "runs"
    log_path = args.output_dir / "tuning.log"
    champion_log_path = args.output_dir / "champions.jsonl"
    results_csv_path = args.output_dir / "candidate_results.csv"
    best_config_path = args.output_dir / "best_config.json"
    runs_dir.mkdir(parents=True, exist_ok=True)
    runner_prefix, use_wsl_paths, runner_label = resolve_backtester_runner()

    with log_path.open("a", encoding="utf-8") as log_file:
        log_message(f"[setup] trader={args.trader}", log_file)
        log_message(f"[setup] dataset={args.dataset}", log_file)
        log_message(f"[setup] output_dir={args.output_dir}", log_file)
        log_message(f"[setup] backtester={runner_label}", log_file)

        all_rows: list[dict[str, object]] = []
        champion_events: list[dict[str, object]] = []
        best_result: CandidateResult | None = None
        current_config = normalize_config(DEFAULT_CONFIG)
        evaluated = 0

        baseline = evaluate_candidate(
            stage="baseline",
            parameter="baseline",
            value=current_config["residual_prior_weight"],
            config=current_config,
            candidate_index=0,
            args=args,
            runner_prefix=runner_prefix,
            use_wsl_paths=use_wsl_paths,
        )
        all_rows.append(candidate_row(baseline))
        evaluated += 1
        if baseline.status == "ok":
            best_result = baseline
            current_result = baseline
            champion_events.append(champion_record(baseline, "initial baseline"))
            append_jsonl(champion_log_path, champion_record(baseline, "initial baseline"))
            log_message(
                f"[champion] baseline total_pnl={baseline.total_pnl:.2f} "
                f"days={baseline.day_pnls} config={json.dumps(baseline.config, sort_keys=True)}",
                log_file,
            )
        else:
            log_message(
                f"[warning] baseline failed rc={baseline.return_code} stderr_tail={baseline.stderr_tail[-500:]}",
                log_file,
            )
            raise RuntimeError("baseline run failed; fix the trader/backtester before tuning")

        for sweep_pass in range(1, max(1, args.passes) + 1):
            log_message(f"[pass] {sweep_pass}/{max(1, args.passes)} starting", log_file)
            improved_this_pass = False
            for stage_index, (parameter, values) in enumerate(STAGES, start=1):
                log_message(
                    f"[stage] pass={sweep_pass} step={stage_index}/{len(STAGES)} parameter={parameter}",
                    log_file,
                )
                stage_reference = current_result
                stage_best: CandidateResult = stage_reference
                for value in values:
                    if args.max_candidates and evaluated >= args.max_candidates:
                        log_message("[stop] reached max_candidates limit", log_file)
                        break
                    candidate_config = dict(current_config)
                    candidate_config[parameter] = float(value)
                    result = evaluate_candidate(
                        stage=f"pass{sweep_pass}",
                        parameter=parameter,
                        value=float(value),
                        config=candidate_config,
                        candidate_index=evaluated + 1,
                        args=args,
                        runner_prefix=runner_prefix,
                        use_wsl_paths=use_wsl_paths,
                    )
                    evaluated += 1
                    all_rows.append(candidate_row(result))
                    log_message(
                        f"[eval] {parameter}={value:g} rc={result.return_code} "
                        f"total={result.total_pnl if result.total_pnl is not None else 'nan'} "
                        f"score={result.score}",
                        log_file,
                    )
                    if result.status != "ok":
                        log_message(
                            f"[fail] {parameter}={value:g} stderr_tail={result.stderr_tail[-500:]}",
                            log_file,
                        )
                        continue

                    if compare_score(result.score, stage_best.score) > 0:
                        stage_best = result

                    if best_result is None or compare_score(result.score, best_result.score) > 0:
                        previous_total = best_result.total_pnl if best_result and best_result.total_pnl is not None else None
                        best_result = result
                        champion_events.append(champion_record(result, f"{parameter}={value:g}"))
                        append_jsonl(champion_log_path, champion_record(result, f"{parameter}={value:g}"))
                        delta_text = ""
                        if previous_total is not None and result.total_pnl is not None:
                            delta_text = f" delta={result.total_pnl - previous_total:+.2f}"
                        log_message(
                            f"[champion] pass={sweep_pass} {parameter}={value:g} "
                            f"total_pnl={result.total_pnl:.2f}{delta_text} "
                            f"days={result.day_pnls} config={json.dumps(result.config, sort_keys=True)}",
                            log_file,
                        )

                if compare_score(stage_best.score, stage_reference.score) > 0:
                    current_config = dict(stage_best.config)
                    current_result = stage_best
                    improved_this_pass = True
                    log_message(
                        f"[stage-best] parameter={parameter} value={stage_best.value:g} "
                        f"total_pnl={stage_best.total_pnl:.2f} config={json.dumps(stage_best.config, sort_keys=True)}",
                        log_file,
                    )
                else:
                    log_message(
                        f"[stage-best] parameter={parameter} retained current config "
                        f"total_pnl={stage_reference.total_pnl:.2f} config={json.dumps(stage_reference.config, sort_keys=True)}",
                        log_file,
                    )

                if args.max_candidates and evaluated >= args.max_candidates:
                    break

            if not improved_this_pass:
                log_message(f"[pass] {sweep_pass} made no change to the champion", log_file)
            if args.max_candidates and evaluated >= args.max_candidates:
                break

        write_csv(results_csv_path, all_rows)
        if best_result is not None:
            best_config_path.write_text(
                json.dumps(
                    {
                        "config": best_result.config,
                        "total_pnl": best_result.total_pnl,
                        "day_pnls": best_result.day_pnls,
                        "score": {
                            "total": best_result.score[0],
                            "min_day": best_result.score[1],
                            "mean_day": best_result.score[2],
                            "negative_std": best_result.score[3],
                        },
                        "run_id": best_result.run_id,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        summary = {
            "evaluated": evaluated,
            "champion_events": len(champion_events),
            "best": None
            if best_result is None
            else {
                "run_id": best_result.run_id,
                "config": best_result.config,
                "total_pnl": best_result.total_pnl,
                "day_pnls": best_result.day_pnls,
                "score": {
                    "total": best_result.score[0],
                    "min_day": best_result.score[1],
                    "mean_day": best_result.score[2],
                    "negative_std": best_result.score[3],
                },
            },
        }
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        log_message(f"[done] evaluated={evaluated} champion_events={len(champion_events)}", log_file)
        if best_result is not None:
            log_message(
                f"[done] best total_pnl={best_result.total_pnl:.2f} "
                f"days={best_result.day_pnls} config={json.dumps(best_result.config, sort_keys=True)}",
                log_file,
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
