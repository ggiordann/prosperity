#!/usr/bin/env python3
"""Rank Round 3 candidate traders by robustness, not just local PnL.

This script is meant to help choose which local winner is least likely to
collapse when the Prosperity website backtest differs from the local Rust
simulator. It re-runs a curated set of candidate traders through the local
Rust backtester, then scores them on:

- local total PnL
- day-to-day stability
- sensitivity proxy using nearby family variants
- simplicity proxy from source complexity
- proximity to the simpler `hybrid.py` baseline

Outputs go to:

    analysis/round3_submission_robustness/
"""

from __future__ import annotations

import ast
import csv
import math
import re
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKTESTER_DIR = (REPO_ROOT / "prosperity_rust_backtester").resolve()
BACKTESTER_BIN = (BACKTESTER_DIR / "target" / "release" / "rust_backtester").resolve()
ROUND3_REVIEW_CSV = (
    REPO_ROOT / "analysis" / "chennethelius_round3_review" / "round3_results.csv"
).resolve()
OUTPUT_DIR = (REPO_ROOT / "analysis" / "round3_submission_robustness").resolve()
SUMMARY_CSV = OUTPUT_DIR / "round3_submission_robustness.csv"
REPORT_MD = OUTPUT_DIR / "round3_submission_robustness.md"

ROW_RE = re.compile(
    r"^(?P<set>TOTAL|D[=+]\d+)\s+"
    r"(?P<day>-|\d+)\s+"
    r"(?P<ticks>\d+)\s+"
    r"(?P<own_trades>\d+)\s+"
    r"(?P<final_pnl>-?\d+(?:\.\d+)?)\s+"
    r"(?P<run_dir>.+)$"
)

FEATURES = {
    "kalman_mean_reversion": ["kalman", "mr_gain", "fair_static"],
    "microprice_fair": ["micro-price", "microprice", "micro = ", "volume-weighted micro"],
    "option_iv_smile": ["black-scholes", "black scholes", "smile", "implied vol", " iv "],
    "informed_flow": ["informed", "market_trades", "signed trade", "flow"],
    "inventory_aware": ["inventory", "stoikov", "skew"],
    "ema_trend": ["ema", "trend"],
    "vev_divergence_mm": ["diverge", "anchor", "quote_size"],
    "drawdown_controls": ["drawdown", "circuit-breaker", "cooldown"],
    "full_limits_focus": ["200/300", "full limits", "position_limit"],
}

CANDIDATE_PATHS = {
    "hybrid": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "hybrid.py",
    "v16_hp_smaller_mr": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v16_hp_smaller_mr.py",
    "v17_hp_mr500": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v17_hp_mr500.py",
    "v18_both_mr_smaller": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v18_both_mr_smaller.py",
    "v19_vfe_mr_3000": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v19_vfe_mr_3000.py",
    "v22_negskew_stable": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v22_negskew_stable.py",
    "v24_partial_hedge": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v24_partial_hedge.py",
    "v25_worst_mid_fair": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v25_worst_mid_fair.py",
    "v26_worst_mid_target": REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3" / "v26_worst_mid_target.py",
    "30u30": REPO_ROOT / "scripts" / "30u30.py",
}

NEIGHBOR_MAP = {
    "hybrid": ["v11_hybrid_plus_informed", "v16_hp_smaller_mr", "v24_partial_hedge"],
    "v16_hp_smaller_mr": ["v17_hp_mr500", "v18_both_mr_smaller", "v19_vfe_mr_3000", "v24_partial_hedge", "v25_worst_mid_fair", "v26_worst_mid_target", "30u30"],
    "v17_hp_mr500": ["v16_hp_smaller_mr", "v18_both_mr_smaller", "30u30"],
    "v18_both_mr_smaller": ["v16_hp_smaller_mr", "v17_hp_mr500", "v19_vfe_mr_3000"],
    "v19_vfe_mr_3000": ["v16_hp_smaller_mr", "v18_both_mr_smaller", "v25_worst_mid_fair", "v26_worst_mid_target"],
    "v22_negskew_stable": ["v16_hp_smaller_mr", "v21_safe_structural", "v24_partial_hedge"],
    "v24_partial_hedge": ["v23_delta_hedge", "v16_hp_smaller_mr", "30u30"],
    "v25_worst_mid_fair": ["v16_hp_smaller_mr", "v19_vfe_mr_3000", "v26_worst_mid_target"],
    "v26_worst_mid_target": ["v16_hp_smaller_mr", "v19_vfe_mr_3000", "v25_worst_mid_fair"],
    "30u30": ["v24_partial_hedge", "v16_hp_smaller_mr", "v17_hp_mr500"],
}


@dataclass
class CandidateResult:
    name: str
    path: Path
    total_pnl: float
    day_pnls: dict[int, float]
    own_trades: int
    min_day_pnl: float
    mean_day_pnl: float
    day_std_pnl: float
    pseudo_sharpe: float
    loc_noncomment: int
    function_count: int
    feature_count: int
    feature_set: set[str]
    baseline_proximity: float
    sensitivity_avg_gap: float
    sensitivity_score: float
    robustness_score: float = 0.0


def windows_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


def shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def parse_source_metrics(path: Path) -> tuple[int, int, set[str]]:
    source = path.read_text(encoding="utf-8", errors="replace")
    module = ast.parse(source)
    loc_noncomment = sum(
        1
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    function_count = sum(isinstance(node, ast.FunctionDef) for node in ast.walk(module))
    haystack = source.lower()
    feature_set = {
        feature
        for feature, keywords in FEATURES.items()
        if any(keyword.lower() in haystack for keyword in keywords)
    }
    return loc_noncomment, function_count, feature_set


def run_backtest(path: Path) -> tuple[float, dict[int, float], int]:
    cmd = (
        f"cd {shell_quote(windows_to_wsl(BACKTESTER_DIR))} && "
        f"./target/release/rust_backtester --trader {shell_quote(windows_to_wsl(path))} "
        "--dataset round3 --products off --artifact-mode none"
    )
    proc = subprocess.run(
        ["wsl.exe", "bash", "-lc", cmd],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        raise RuntimeError(f"Backtest failed for {path.name}:\n{output}")

    total_pnl = None
    own_trades = None
    day_pnls: dict[int, float] = {}
    for line in output.splitlines():
        match = ROW_RE.match(line.rstrip())
        if not match:
            continue
        pnl = float(match.group("final_pnl"))
        trades = int(match.group("own_trades"))
        if match.group("set") == "TOTAL":
            total_pnl = pnl
            own_trades = trades
        else:
            day = int(match.group("day"))
            day_pnls[day] = pnl
    if total_pnl is None or own_trades is None or not day_pnls:
        raise RuntimeError(f"Could not parse backtest output for {path.name}:\n{output}")
    return total_pnl, day_pnls, own_trades


def read_reference_pnls() -> dict[str, float]:
    reference: dict[str, float] = {}
    with ROUND3_REVIEW_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            reference[row["strategy"]] = float(row["total_pnl"])
    return reference


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize(value: float, low: float, high: float, invert: bool = False) -> float:
    if math.isclose(high, low):
        return 1.0
    scaled = (value - low) / (high - low)
    if invert:
        scaled = 1.0 - scaled
    return clamp01(scaled)


def sensitivity_metrics(name: str, own_total_pnl: float, reference_pnls: dict[str, float]) -> tuple[float, float]:
    neighbors = [reference_pnls[item] for item in NEIGHBOR_MAP.get(name, []) if item in reference_pnls]
    if not neighbors:
        return 0.0, 1.0
    avg_gap = statistics.fmean(abs(own_total_pnl - neighbor) for neighbor in neighbors)
    score = 1.0 / (1.0 + avg_gap / 10000.0)
    return avg_gap, score


def compute_robustness_scores(results: list[CandidateResult], hybrid_features: set[str]) -> None:
    total_pnls = [item.total_pnl for item in results]
    min_days = [item.min_day_pnl for item in results]
    stds = [item.day_std_pnl for item in results]
    sharpes = [item.pseudo_sharpe for item in results]
    locs = [item.loc_noncomment for item in results]
    fn_counts = [item.function_count for item in results]
    sensitivity_scores = [item.sensitivity_score for item in results]
    baseline_scores = [item.baseline_proximity for item in results]

    for item in results:
        pnl_score = normalize(item.total_pnl, min(total_pnls), max(total_pnls))
        min_day_score = normalize(item.min_day_pnl, min(min_days), max(min_days))
        std_score = normalize(item.day_std_pnl, min(stds), max(stds), invert=True)
        sharpe_score = normalize(item.pseudo_sharpe, min(sharpes), max(sharpes))
        stability_score = (min_day_score + std_score + sharpe_score) / 3.0

        loc_score = normalize(item.loc_noncomment, min(locs), max(locs), invert=True)
        fn_score = normalize(item.function_count, min(fn_counts), max(fn_counts), invert=True)
        simplicity_score = (loc_score + fn_score) / 2.0

        sensitivity_norm = normalize(item.sensitivity_score, min(sensitivity_scores), max(sensitivity_scores))
        baseline_norm = normalize(item.baseline_proximity, min(baseline_scores), max(baseline_scores))

        item.robustness_score = (
            0.25 * pnl_score
            + 0.35 * stability_score
            + 0.20 * sensitivity_norm
            + 0.10 * simplicity_score
            + 0.10 * baseline_norm
        )


def build_results() -> list[CandidateResult]:
    reference_pnls = read_reference_pnls()
    results: list[CandidateResult] = []

    hybrid_path = CANDIDATE_PATHS["hybrid"]
    _, _, hybrid_features = parse_source_metrics(hybrid_path)

    for name, path in CANDIDATE_PATHS.items():
        total_pnl, day_pnls, own_trades = run_backtest(path)
        loc_noncomment, function_count, feature_set = parse_source_metrics(path)
        day_values = [day_pnls[day] for day in sorted(day_pnls)]
        mean_day_pnl = statistics.fmean(day_values)
        day_std_pnl = statistics.pstdev(day_values) if len(day_values) > 1 else 0.0
        pseudo_sharpe = mean_day_pnl / day_std_pnl if day_std_pnl > 0 else float("inf")
        baseline_proximity = jaccard_similarity(feature_set, hybrid_features)
        avg_gap, sensitivity_score = sensitivity_metrics(name, total_pnl, reference_pnls)

        results.append(
            CandidateResult(
                name=name,
                path=path,
                total_pnl=total_pnl,
                day_pnls=day_pnls,
                own_trades=own_trades,
                min_day_pnl=min(day_values),
                mean_day_pnl=mean_day_pnl,
                day_std_pnl=day_std_pnl,
                pseudo_sharpe=pseudo_sharpe,
                loc_noncomment=loc_noncomment,
                function_count=function_count,
                feature_count=len(feature_set),
                feature_set=feature_set,
                baseline_proximity=baseline_proximity,
                sensitivity_avg_gap=avg_gap,
                sensitivity_score=sensitivity_score,
            )
        )

    compute_robustness_scores(results, hybrid_features)
    results.sort(key=lambda item: item.robustness_score, reverse=True)
    return results


def write_csv(results: list[CandidateResult]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "robustness_rank",
                "strategy",
                "total_pnl",
                "day_0_pnl",
                "day_1_pnl",
                "day_2_pnl",
                "min_day_pnl",
                "mean_day_pnl",
                "day_std_pnl",
                "pseudo_sharpe",
                "own_trades",
                "loc_noncomment",
                "function_count",
                "feature_count",
                "baseline_proximity",
                "sensitivity_avg_gap",
                "sensitivity_score",
                "robustness_score",
                "path",
            ]
        )
        for rank, item in enumerate(results, start=1):
            writer.writerow(
                [
                    rank,
                    item.name,
                    f"{item.total_pnl:.2f}",
                    f"{item.day_pnls.get(0, 0.0):.2f}",
                    f"{item.day_pnls.get(1, 0.0):.2f}",
                    f"{item.day_pnls.get(2, 0.0):.2f}",
                    f"{item.min_day_pnl:.2f}",
                    f"{item.mean_day_pnl:.2f}",
                    f"{item.day_std_pnl:.2f}",
                    f"{item.pseudo_sharpe:.6f}",
                    item.own_trades,
                    item.loc_noncomment,
                    item.function_count,
                    item.feature_count,
                    f"{item.baseline_proximity:.4f}",
                    f"{item.sensitivity_avg_gap:.2f}",
                    f"{item.sensitivity_score:.6f}",
                    f"{item.robustness_score:.6f}",
                    str(item.path),
                ]
            )


def write_report(results: list[CandidateResult]) -> None:
    top = results[0]
    lines = [
        "# Round 3 Submission Robustness",
        "",
        "This ranking is designed for the case where the Prosperity website and the local Rust backtester disagree.",
        "It intentionally favors strategies that are not just locally profitable, but also stable, simple, and less sensitive to nearby tweaks.",
        "",
        "## Top Picks",
        "",
        f"- Best overall robustness score: `{top.name}`",
        f"- Raw PnL leader in this set: `{max(results, key=lambda item: item.total_pnl).name}`",
        f"- Strongest simple baseline: `hybrid`",
        "",
        "## Ranking",
        "",
        "| Rank | Strategy | Robustness | Total PnL | Min Day | Day Std | Sharpe-like | Sensitivity Gap | Baseline Proximity |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, item in enumerate(results, start=1):
        lines.append(
            f"| {rank} | `{item.name}` | {item.robustness_score:.3f} | {item.total_pnl:,.2f} | "
            f"{item.min_day_pnl:,.2f} | {item.day_std_pnl:,.2f} | {item.pseudo_sharpe:.3f} | "
            f"{item.sensitivity_avg_gap:,.2f} | {item.baseline_proximity:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Reading It",
            "",
            "- `Total PnL`: what the local Rust backtester says.",
            "- `Min Day`: worst single public round-3 day. Higher is better.",
            "- `Day Std`: lower means less day-to-day swing.",
            "- `Sharpe-like`: mean day PnL divided by day PnL standard deviation.",
            "- `Sensitivity Gap`: average PnL gap to nearby family variants. Lower is better.",
            "- `Baseline Proximity`: feature similarity to the simpler `hybrid.py` baseline. Higher is usually safer.",
            "",
            "## Files",
            "",
            f"- CSV: `{SUMMARY_CSV}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not BACKTESTER_BIN.exists():
        raise FileNotFoundError(f"Missing release backtester at {BACKTESTER_BIN}")
    results = build_results()
    write_csv(results)
    write_report(results)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {REPORT_MD}")
    print(f"Top robustness pick: {results[0].name}")


if __name__ == "__main__":
    main()
