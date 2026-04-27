from __future__ import annotations

import ast
import csv
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_DIR = REPO_ROOT / ".research_repos" / "p4-chennethelius" / "strategies" / "round3"
BACKTESTER_DIR = REPO_ROOT / "prosperity_rust_backtester"
BACKTESTER_BIN = BACKTESTER_DIR / "target" / "release" / "rust_backtester"
OUTPUT_DIR = REPO_ROOT / "round 3" / "analysis" / "chennethelius_round3_review"

RESULTS_CSV = OUTPUT_DIR / "round3_results.csv"
PER_DAY_CSV = OUTPUT_DIR / "round3_results_per_day.csv"
FEATURE_CSV = OUTPUT_DIR / "round3_feature_summary.csv"
RISK_CSV = OUTPUT_DIR / "round3_over_700k_risk_rank.csv"
REPORT_MD = OUTPUT_DIR / "round3_key_findings.md"

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


@dataclass
class StrategyResult:
    name: str
    path: Path
    total_pnl: float
    total_own_trades: int
    min_day_pnl: float
    max_day_pnl: float
    mean_day_pnl: float
    day_std_pnl: float
    day_sharpe: float
    day_pnls: dict[int, float]
    day_trades: dict[int, int]
    docstring_excerpt: str
    features: list[str]
    stdout: str


def windows_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


def extract_docstring_and_source(path: Path) -> tuple[str, str]:
    source = path.read_text(encoding="utf-8", errors="replace")
    module = ast.parse(source)
    docstring = ast.get_docstring(module) or ""
    return docstring, source


def build_excerpt(docstring: str) -> str:
    lines = [line.strip() for line in docstring.splitlines() if line.strip()]
    if not lines:
        return "No module docstring."
    excerpt_lines: list[str] = []
    for line in lines:
        excerpt_lines.append(line)
        if len(" ".join(excerpt_lines)) >= 220 or len(excerpt_lines) >= 4:
            break
    excerpt = " ".join(excerpt_lines)
    return excerpt[:280].rstrip()


def detect_features(source: str, docstring: str) -> list[str]:
    haystack = f"{docstring}\n{source}".lower()
    hits: list[str] = []
    for feature, keywords in FEATURES.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            hits.append(feature)
    return hits


def compute_day_std(day_pnls: dict[int, float]) -> float:
    values = list(day_pnls.values())
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def compute_day_sharpe(mean_day_pnl: float, day_std_pnl: float) -> float:
    if day_std_pnl <= 0:
        return float("inf")
    return mean_day_pnl / day_std_pnl


def ensure_backtester_ready() -> None:
    if BACKTESTER_BIN.exists():
        return
    raise FileNotFoundError(
        f"Missing backtester binary at {BACKTESTER_BIN}. Build it first with "
        f"`wsl bash -lc 'cd {windows_to_wsl(BACKTESTER_DIR)} && ./scripts/cargo_local.sh build --release'`."
    )


def run_backtest(path: Path) -> StrategyResult:
    trader_wsl = windows_to_wsl(path)
    backtester_wsl = windows_to_wsl(BACKTESTER_DIR)
    cmd = (
        f"cd {backtester_wsl} && "
        f"target/release/rust_backtester --trader {shell_quote(trader_wsl)} "
        f"--dataset round3 --products off --artifact-mode none"
    )
    proc = subprocess.run(
        ["wsl.exe", "bash", "-lc", cmd],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    if proc.returncode != 0:
        raise RuntimeError(f"Backtest failed for {path.name}:\n{output}")

    day_pnls: dict[int, float] = {}
    day_trades: dict[int, int] = {}
    total_pnl = None
    total_own_trades = None

    for line in output.splitlines():
        line = line.rstrip()
        match = ROW_RE.match(line)
        if not match:
            continue
        set_name = match.group("set")
        own_trades = int(match.group("own_trades"))
        pnl = float(match.group("final_pnl"))
        if set_name == "TOTAL":
            total_pnl = pnl
            total_own_trades = own_trades
        else:
            day = int(match.group("day"))
            day_pnls[day] = pnl
            day_trades[day] = own_trades

    if total_pnl is None or total_own_trades is None or not day_pnls:
        raise RuntimeError(f"Could not parse backtest output for {path.name}:\n{output}")

    docstring, source = extract_docstring_and_source(path)
    excerpt = build_excerpt(docstring)
    features = detect_features(source, docstring)
    mean_day_pnl = statistics.mean(day_pnls.values())
    day_std_pnl = compute_day_std(day_pnls)
    return StrategyResult(
        name=path.stem,
        path=path,
        total_pnl=total_pnl,
        total_own_trades=total_own_trades,
        min_day_pnl=min(day_pnls.values()),
        max_day_pnl=max(day_pnls.values()),
        mean_day_pnl=mean_day_pnl,
        day_std_pnl=day_std_pnl,
        day_sharpe=compute_day_sharpe(mean_day_pnl, day_std_pnl),
        day_pnls=day_pnls,
        day_trades=day_trades,
        docstring_excerpt=excerpt,
        features=features,
        stdout=output.strip(),
    )


def shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def write_results_csv(results: list[StrategyResult]) -> None:
    with RESULTS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "strategy",
                "total_pnl",
                "day_0_pnl",
                "day_1_pnl",
                "day_2_pnl",
                "min_day_pnl",
                "max_day_pnl",
                "mean_day_pnl",
                "day_std_pnl",
                "day_sharpe",
                "total_own_trades",
                "features",
                "docstring_excerpt",
                "path",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.name,
                    f"{result.total_pnl:.2f}",
                    f"{result.day_pnls.get(0, 0.0):.2f}",
                    f"{result.day_pnls.get(1, 0.0):.2f}",
                    f"{result.day_pnls.get(2, 0.0):.2f}",
                    f"{result.min_day_pnl:.2f}",
                    f"{result.max_day_pnl:.2f}",
                    f"{result.mean_day_pnl:.2f}",
                    f"{result.day_std_pnl:.2f}",
                    f"{result.day_sharpe:.6f}",
                    result.total_own_trades,
                    ", ".join(result.features),
                    result.docstring_excerpt,
                    str(result.path),
                ]
            )


def write_per_day_csv(results: list[StrategyResult]) -> None:
    with PER_DAY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strategy", "day", "pnl", "own_trades"])
        for result in results:
            for day in sorted(result.day_pnls):
                writer.writerow(
                    [result.name, day, f"{result.day_pnls[day]:.2f}", result.day_trades[day]]
                )


def write_feature_csv(results: list[StrategyResult]) -> list[dict[str, object]]:
    grouped: dict[str, list[StrategyResult]] = defaultdict(list)
    for result in results:
        for feature in result.features:
            grouped[feature].append(result)

    rows: list[dict[str, object]] = []
    with FEATURE_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["feature", "strategy_count", "avg_total_pnl", "median_total_pnl", "best_strategy", "best_pnl"]
        )
        for feature, members in sorted(grouped.items()):
            best = max(members, key=lambda item: item.total_pnl)
            avg_pnl = statistics.mean(item.total_pnl for item in members)
            median_pnl = statistics.median(item.total_pnl for item in members)
            row = {
                "feature": feature,
                "strategy_count": len(members),
                "avg_total_pnl": avg_pnl,
                "median_total_pnl": median_pnl,
                "best_strategy": best.name,
                "best_pnl": best.total_pnl,
            }
            rows.append(row)
            writer.writerow(
                [
                    feature,
                    len(members),
                    f"{avg_pnl:.2f}",
                    f"{median_pnl:.2f}",
                    best.name,
                    f"{best.total_pnl:.2f}",
                ]
            )
    return rows


def write_risk_csv(results: list[StrategyResult], pnl_floor: float = 700_000.0) -> list[StrategyResult]:
    eligible = [result for result in results if result.total_pnl >= pnl_floor]
    eligible.sort(key=lambda item: (-item.day_sharpe, item.day_std_pnl, -item.total_pnl))
    with RISK_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank_by_sharpe",
                "strategy",
                "total_pnl",
                "day_0_pnl",
                "day_1_pnl",
                "day_2_pnl",
                "mean_day_pnl",
                "day_std_pnl",
                "day_sharpe",
                "min_day_pnl",
                "total_own_trades",
            ]
        )
        for rank, result in enumerate(eligible, start=1):
            writer.writerow(
                [
                    rank,
                    result.name,
                    f"{result.total_pnl:.2f}",
                    f"{result.day_pnls.get(0, 0.0):.2f}",
                    f"{result.day_pnls.get(1, 0.0):.2f}",
                    f"{result.day_pnls.get(2, 0.0):.2f}",
                    f"{result.mean_day_pnl:.2f}",
                    f"{result.day_std_pnl:.2f}",
                    f"{result.day_sharpe:.6f}",
                    f"{result.min_day_pnl:.2f}",
                    result.total_own_trades,
                ]
            )
    return eligible


def build_key_findings(
    results: list[StrategyResult],
    feature_rows: list[dict[str, object]],
    risk_ranked: list[StrategyResult],
) -> list[str]:
    findings: list[str] = []
    top = results[0]
    second = results[1] if len(results) > 1 else None
    most_stable = max(results, key=lambda item: item.min_day_pnl)
    most_active = max(results, key=lambda item: item.total_own_trades)
    feature_counter = Counter(feature for result in results for feature in result.features)

    findings.append(
        f"`{top.name}` is the champion on total Round 3 PnL at {top.total_pnl:,.2f}, "
        f"with day PnL split of {top.day_pnls.get(0, 0.0):,.2f} / "
        f"{top.day_pnls.get(1, 0.0):,.2f} / {top.day_pnls.get(2, 0.0):,.2f}."
    )
    if second is not None:
        findings.append(
            f"The top of the table is tight: `{top.name}` beats `{second.name}` by "
            f"{top.total_pnl - second.total_pnl:,.2f} total PnL."
        )
    findings.append(
        f"`{most_stable.name}` has the best worst-day result at {most_stable.min_day_pnl:,.2f}, "
        f"so it looks like the most stable of the batch rather than just the spikiest."
    )
    findings.append(
        f"`{most_active.name}` is the busiest strategy at {most_active.total_own_trades:,} own trades; "
        f"that makes it a useful check on whether extra turnover was actually buying more PnL."
    )
    if risk_ranked:
        lowest_risk = risk_ranked[0]
        findings.append(
            f"Among the `{len(risk_ranked)}` strategies above 700k total PnL, `{lowest_risk.name}` has the best "
            f"three-day pseudo-Sharpe at {lowest_risk.day_sharpe:.3f} with day-PnL stdev {lowest_risk.day_std_pnl:,.2f}."
        )

    top_feature_rows = sorted(feature_rows, key=lambda row: float(row["avg_total_pnl"]), reverse=True)[:3]
    for row in top_feature_rows:
        findings.append(
            f"Feature family `{row['feature']}` appears in {row['strategy_count']} files and averages "
            f"{float(row['avg_total_pnl']):,.2f} total PnL; its best member is `{row['best_strategy']}` "
            f"at {float(row['best_pnl']):,.2f}."
        )

    if feature_counter:
        common = ", ".join(f"`{name}` ({count})" for name, count in feature_counter.most_common(5))
        findings.append(f"The most common design ingredients across the folder are {common}.")

    return findings


def build_report(
    results: list[StrategyResult],
    feature_rows: list[dict[str, object]],
    risk_ranked: list[StrategyResult],
) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    top10 = results[:10]
    findings = build_key_findings(results, feature_rows, risk_ranked)

    leaderboard_lines = [
        "| Rank | Strategy | Total PnL | Day 0 | Day 1 | Day 2 | Min Day | Own Trades |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, result in enumerate(top10, start=1):
        leaderboard_lines.append(
            f"| {index} | `{result.name}` | {result.total_pnl:,.2f} | "
            f"{result.day_pnls.get(0, 0.0):,.2f} | {result.day_pnls.get(1, 0.0):,.2f} | "
            f"{result.day_pnls.get(2, 0.0):,.2f} | {result.min_day_pnl:,.2f} | "
            f"{result.total_own_trades:,} |"
        )

    feature_lines = [
        "| Feature | Files | Avg Total PnL | Median Total PnL | Best Strategy | Best PnL |",
        "| --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in sorted(feature_rows, key=lambda item: float(item["avg_total_pnl"]), reverse=True):
        feature_lines.append(
            f"| `{row['feature']}` | {row['strategy_count']} | {float(row['avg_total_pnl']):,.2f} | "
            f"{float(row['median_total_pnl']):,.2f} | `{row['best_strategy']}` | {float(row['best_pnl']):,.2f} |"
        )

    risk_lines = [
        "| Sharpe Rank | Strategy | Total PnL | Mean Day PnL | Day PnL Std | Pseudo-Sharpe | Min Day |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, result in enumerate(risk_ranked, start=1):
        risk_lines.append(
            f"| {index} | `{result.name}` | {result.total_pnl:,.2f} | {result.mean_day_pnl:,.2f} | "
            f"{result.day_std_pnl:,.2f} | {result.day_sharpe:.3f} | {result.min_day_pnl:,.2f} |"
        )

    strategy_note_lines = []
    for result in results:
        strategy_note_lines.append(
            f"- `{result.name}`: {result.docstring_excerpt} "
            f"Features: {', '.join(result.features) if result.features else 'none detected'}."
        )

    return "\n".join(
        [
            "# Chennethelius Round 3 Strategy Review",
            "",
            f"Generated: {generated}",
            "",
            "## Scope",
            "",
            "- Source repo: `https://github.com/chennethelius/slu-imc-prosperity-4`",
            f"- Strategy folder reviewed: `{STRATEGY_DIR}`",
            f"- Backtester: `{BACKTESTER_BIN}` against `datasets/round3`",
            f"- Files tested: {len(results)}",
            "",
            "## Champions",
            "",
            *leaderboard_lines,
            "",
            "## Key Findings",
            "",
            *[f"- {finding}" for finding in findings],
            "",
            "## Feature Performance",
            "",
            *feature_lines,
            "",
            "## Risk Rank (>700k PnL)",
            "",
            "This uses only the three round-day PnL observations, so treat the Sharpe-like score as a rough sorter, not a statistically strong estimate.",
            "",
            *risk_lines,
            "",
            "## File-by-File Notes",
            "",
            *strategy_note_lines,
            "",
            "## Output Files",
            "",
            f"- Summary CSV: `{RESULTS_CSV}`",
            f"- Per-day CSV: `{PER_DAY_CSV}`",
            f"- Feature CSV: `{FEATURE_CSV}`",
            f"- Risk-ranked CSV: `{RISK_CSV}`",
        ]
    )


def main() -> None:
    ensure_backtester_ready()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    strategy_paths = sorted(STRATEGY_DIR.glob("*.py"))
    results: list[StrategyResult] = []
    for path in strategy_paths:
        print(f"Running {path.name}...")
        results.append(run_backtest(path))

    results.sort(key=lambda item: item.total_pnl, reverse=True)
    write_results_csv(results)
    write_per_day_csv(results)
    feature_rows = write_feature_csv(results)
    risk_ranked = write_risk_csv(results)
    report = build_report(results, feature_rows, risk_ranked)
    REPORT_MD.write_text(report, encoding="utf-8")

    print(f"Wrote {REPORT_MD}")
    print(f"Champion: {results[0].name} ({results[0].total_pnl:,.2f})")


if __name__ == "__main__":
    main()
