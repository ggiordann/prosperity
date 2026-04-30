#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


DEFAULT_CONFIG = Path(__file__).with_name("manual_scenarios.json")
SIDE_SIGN = {"buy": 1, "sell": -1, "flat": 0}


@dataclass(frozen=True)
class ReturnRange:
    low: float
    mode: float
    high: float

    @property
    def expected(self) -> float:
        return (self.low + self.mode + self.high) / 3.0


@dataclass(frozen=True)
class Position:
    side: str
    pct: int

    @property
    def sign(self) -> int:
        return SIDE_SIGN[self.side]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        config = json.load(fh)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    products = config.get("products")
    if not isinstance(products, dict) or not products:
        raise ValueError("config must contain a non-empty 'products' object")

    for product, values in products.items():
        parse_range(product, values)

    for scenario, body in config.get("scenarios", {}).items():
        overrides = body.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError(f"scenario {scenario!r} overrides must be an object")
        for product, values in overrides.items():
            if product not in products:
                raise ValueError(f"scenario {scenario!r} overrides unknown product {product!r}")
            parse_range(product, values)

    for portfolio_name, raw_portfolio in config.get("portfolios", {}).items():
        parse_portfolio(portfolio_name, raw_portfolio, set(products))


def parse_range(product: str, values: dict[str, Any]) -> ReturnRange:
    try:
        low = float(values["low"])
        mode = float(values["mode"])
        high = float(values["high"])
    except KeyError as exc:
        raise ValueError(f"{product!r} range must define low, mode, and high") from exc
    if not low <= mode <= high:
        raise ValueError(f"{product!r} range must satisfy low <= mode <= high")
    return ReturnRange(low=low, mode=mode, high=high)


def parse_portfolio(
    name: str,
    raw_portfolio: dict[str, Any],
    product_names: set[str],
) -> dict[str, Position]:
    portfolio: dict[str, Position] = {}
    for product, raw_position in raw_portfolio.items():
        if product not in product_names:
            raise ValueError(f"portfolio {name!r} contains unknown product {product!r}")
        side = str(raw_position.get("side", "")).lower()
        if side not in SIDE_SIGN:
            raise ValueError(f"portfolio {name!r} product {product!r} has invalid side {side!r}")
        pct = int(raw_position.get("pct", 0))
        if pct < 0 or pct > 100:
            raise ValueError(f"portfolio {name!r} product {product!r} pct must be in [0, 100]")
        if pct == 0:
            side = "flat"
        portfolio[product] = Position(side=side, pct=pct)
    return portfolio


def scenario_names(config: dict[str, Any], requested: str) -> list[str]:
    scenarios = list(config.get("scenarios", {}))
    if requested == "all":
        return scenarios or ["base"]
    if requested == "weighted":
        return ["weighted"]
    if requested == "base":
        return ["base"]
    if requested not in config.get("scenarios", {}):
        raise ValueError(f"unknown scenario {requested!r}; use base, all, weighted, or a configured name")
    return [requested]


def scenario_ranges(config: dict[str, Any], scenario: str) -> dict[str, ReturnRange]:
    ranges = {product: parse_range(product, values) for product, values in config["products"].items()}
    if scenario == "base":
        return ranges
    body = config.get("scenarios", {}).get(scenario)
    if body is None:
        raise ValueError(f"unknown scenario {scenario!r}")
    for product, values in body.get("overrides", {}).items():
        ranges[product] = parse_range(product, values)
    return ranges


def scenario_weights(config: dict[str, Any]) -> dict[str, float]:
    scenarios = config.get("scenarios", {})
    weights = {name: float(body.get("weight", 1.0)) for name, body in scenarios.items()}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("scenario weights must sum to a positive number")
    return {name: weight / total for name, weight in weights.items()}


def weighted_expected_returns(config: dict[str, Any]) -> dict[str, float]:
    weights = scenario_weights(config)
    products = config["products"]
    expected = {product: 0.0 for product in products}
    for scenario, weight in weights.items():
        ranges = scenario_ranges(config, scenario)
        for product, rng in ranges.items():
            expected[product] += weight * rng.expected
    return expected


def sample_returns(
    config: dict[str, Any],
    rng: random.Random,
    scenario: str,
) -> dict[str, float]:
    if scenario == "weighted":
        weights = scenario_weights(config)
        roll = rng.random()
        cumulative = 0.0
        for scenario_name, weight in weights.items():
            cumulative += weight
            if roll <= cumulative:
                scenario = scenario_name
                break
    ranges = scenario_ranges(config, scenario)
    return {
        product: rng.triangular(return_range.low, return_range.high, return_range.mode)
        for product, return_range in ranges.items()
    }


def fee_for_pct(budget: float, pct: int) -> float:
    allocation = pct / 100.0
    return budget * allocation * allocation


def position_pnl(budget: float, position: Position, raw_return: float) -> float:
    allocation = position.pct / 100.0
    return budget * (allocation * position.sign * raw_return - allocation * allocation)


def portfolio_pnl(
    budget: float,
    products: list[str],
    portfolio: dict[str, Position],
    returns: dict[str, float],
) -> float:
    total = 0.0
    for product in products:
        position = portfolio.get(product, Position(side="flat", pct=0))
        total += position_pnl(budget, position, returns[product])
    return total


def portfolio_fee(budget: float, products: list[str], portfolio: dict[str, Position]) -> float:
    return sum(fee_for_pct(budget, portfolio.get(product, Position("flat", 0)).pct) for product in products)


def portfolio_budget_used(products: list[str], portfolio: dict[str, Position]) -> int:
    return sum(portfolio.get(product, Position("flat", 0)).pct for product in products)


def portfolio_signature(products: list[str], portfolio: dict[str, Position]) -> tuple[tuple[str, int], ...]:
    return tuple(
        (
            portfolio.get(product, Position("flat", 0)).side,
            portfolio.get(product, Position("flat", 0)).pct,
        )
        for product in products
    )


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return math.nan
    idx = min(len(sorted_values) - 1, max(0, round((len(sorted_values) - 1) * q)))
    return sorted_values[idx]


def summarize(values: list[float]) -> dict[str, float]:
    sorted_values = sorted(values)
    positives = sum(1 for value in values if value > 0)
    return {
        "mean": mean(values),
        "stdev": pstdev(values) if len(values) > 1 else 0.0,
        "p05": percentile(sorted_values, 0.05),
        "p25": percentile(sorted_values, 0.25),
        "p50": percentile(sorted_values, 0.50),
        "p75": percentile(sorted_values, 0.75),
        "p95": percentile(sorted_values, 0.95),
        "prob_profit": positives / len(values),
    }


def format_money(value: float) -> str:
    return f"{value:,.0f}"


def format_pct(value: float) -> str:
    return f"{100.0 * value:5.1f}%"


def render_stats_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        "portfolio",
        "used",
        "fee",
        "mean",
        "p05",
        "p50",
        "p95",
        "win%",
    ]
    table = [headers]
    for row in rows:
        table.append(
            [
                row["portfolio"],
                f"{row['used_pct']}%",
                format_money(row["fee"]),
                format_money(row["stats"]["mean"]),
                format_money(row["stats"]["p05"]),
                format_money(row["stats"]["p50"]),
                format_money(row["stats"]["p95"]),
                format_pct(row["stats"]["prob_profit"]),
            ]
        )
    widths = [max(len(str(line[col])) for line in table) for col in range(len(headers))]
    rendered = []
    for i, line in enumerate(table):
        rendered.append("  ".join(str(value).rjust(widths[col]) for col, value in enumerate(line)))
        if i == 0:
            rendered.append("  ".join("-" * width for width in widths))
    return "\n".join(rendered)


def render_robust_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        "portfolio",
        "used",
        "fee",
        "mean",
        "p10",
        "p50",
        "p90",
        "stdev",
        "avgReg",
        "p90Reg",
        "score",
    ]
    table = [headers]
    for row in rows:
        table.append(
            [
                row["portfolio"],
                f"{row['used_pct']}%",
                format_money(row["fee"]),
                format_money(row["mean"]),
                format_money(row["p10"]),
                format_money(row["p50"]),
                format_money(row["p90"]),
                format_money(row["stdev"]),
                format_money(row["avg_regret"]),
                format_money(row["p90_regret"]),
                format_money(row["score"]),
            ]
        )
    widths = [max(len(str(line[col])) for line in table) for col in range(len(headers))]
    rendered = []
    for i, line in enumerate(table):
        rendered.append("  ".join(str(value).rjust(widths[col]) for col, value in enumerate(line)))
        if i == 0:
            rendered.append("  ".join("-" * width for width in widths))
    return "\n".join(rendered)


def print_portfolio(
    budget: float,
    products: list[str],
    portfolio: dict[str, Position],
    expected_returns: dict[str, float] | None = None,
) -> None:
    columns = ["Tradable good", "Buy/Sell", "Percentage", "Investment", "Fee"]
    if expected_returns is not None:
        columns.append("Expected return")
    print("\t".join(columns))
    for product in products:
        position = portfolio.get(product, Position("flat", 0))
        investment = budget * position.pct / 100.0
        side = "Buy" if position.side == "buy" else "Sell" if position.side == "sell" else "Flat"
        row = [
            product,
            side,
            f"{position.pct}%",
            format_money(investment),
            format_money(fee_for_pct(budget, position.pct)),
        ]
        if expected_returns is not None:
            row.append(f"{expected_returns[product]:+.1%}")
        print("\t".join(row))


def compare(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    budget = float(config.get("budget", 1_000_000))
    products = list(config["products"])
    portfolios = {
        name: parse_portfolio(name, raw_portfolio, set(products))
        for name, raw_portfolio in config["portfolios"].items()
    }
    names = scenario_names(config, args.scenario)
    if args.scenario == "all" and config.get("scenarios"):
        names = names + ["weighted"]

    for scenario in names:
        rng = random.Random(args.seed)
        samples = {
            name: []
            for name in portfolios
        }
        for _ in range(args.trials):
            returns = sample_returns(config, rng, scenario)
            for name, portfolio in portfolios.items():
                samples[name].append(portfolio_pnl(budget, products, portfolio, returns))

        rows = []
        for name, portfolio in portfolios.items():
            rows.append(
                {
                    "portfolio": name,
                    "used_pct": portfolio_budget_used(products, portfolio),
                    "fee": portfolio_fee(budget, products, portfolio),
                    "stats": summarize(samples[name]),
                }
            )
        rows.sort(key=lambda row: row["stats"]["mean"], reverse=True)
        print(f"\nScenario: {scenario}  trials={args.trials:,}  seed={args.seed}")
        print(render_stats_table(rows))


def optimize_ev_for_expected_returns(
    budget: float,
    products: list[str],
    expected_returns: dict[str, float],
    max_budget_pct: int,
    max_pct_per_product: int,
    fixed_sides: bool,
) -> dict[str, Position]:
    states: dict[int, tuple[float, dict[str, Position]]] = {0: (0.0, {})}
    for product in products:
        product_options: list[tuple[int, Position, float]] = [(0, Position("flat", 0), 0.0)]
        expected_return = expected_returns[product]
        sides = ["buy", "sell"]
        if fixed_sides and expected_return != 0:
            sides = ["buy" if expected_return > 0 else "sell"]

        for pct in range(1, max_pct_per_product + 1):
            for side in sides:
                position = Position(side=side, pct=pct)
                score = position_pnl(budget, position, expected_return)
                product_options.append((pct, position, score))

        next_states: dict[int, tuple[float, dict[str, Position]]] = {}
        for used_pct, (current_score, current_positions) in states.items():
            for option_pct, position, option_score in product_options:
                new_used = used_pct + option_pct
                if new_used > max_budget_pct:
                    continue
                new_score = current_score + option_score
                prior = next_states.get(new_used)
                if prior is None or new_score > prior[0]:
                    new_positions = dict(current_positions)
                    new_positions[product] = position
                    next_states[new_used] = (new_score, new_positions)
        states = next_states

    _, best_positions = max(states.values(), key=lambda item: item[0])
    return best_positions


def oracle_portfolio_for_returns(
    budget: float,
    products: list[str],
    expected_returns: dict[str, float],
    max_budget_pct: int,
    max_pct_per_product: int,
) -> dict[str, Position]:
    portfolio: dict[str, Position] = {}
    for product in products:
        expected_return = expected_returns[product]
        if expected_return == 0:
            portfolio[product] = Position("flat", 0)
            continue
        side = "buy" if expected_return > 0 else "sell"
        best_position = Position("flat", 0)
        best_score = 0.0
        for pct in range(1, max_pct_per_product + 1):
            position = Position(side, pct)
            score = position_pnl(budget, position, expected_return)
            if score > best_score:
                best_position = position
                best_score = score
        portfolio[product] = best_position

    if portfolio_budget_used(products, portfolio) <= max_budget_pct:
        return portfolio

    return optimize_ev_for_expected_returns(
        budget=budget,
        products=products,
        expected_returns=expected_returns,
        max_budget_pct=max_budget_pct,
        max_pct_per_product=max_pct_per_product,
        fixed_sides=True,
    )


def optimize(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    budget = float(config.get("budget", 1_000_000))
    products = list(config["products"])

    if args.scenario == "weighted":
        expected_returns = weighted_expected_returns(config)
    else:
        ranges = scenario_ranges(config, args.scenario)
        expected_returns = {product: return_range.expected for product, return_range in ranges.items()}

    portfolio = optimize_ev_for_expected_returns(
        budget=budget,
        products=products,
        expected_returns=expected_returns,
        max_budget_pct=args.max_budget_pct,
        max_pct_per_product=args.max_pct_per_product,
        fixed_sides=not args.allow_wrong_way,
    )

    print(f"EV-optimal integer portfolio for scenario={args.scenario}")
    print(f"Budget used: {portfolio_budget_used(products, portfolio)}%")
    print(f"Fee: {format_money(portfolio_fee(budget, products, portfolio))}")
    print(f"Expected PnL: {format_money(portfolio_pnl(budget, products, portfolio, expected_returns))}")
    print()
    print_portfolio(budget, products, portfolio, expected_returns)


def add_candidate(
    candidates: dict[tuple[tuple[str, int], ...], tuple[str, dict[str, Position]]],
    products: list[str],
    name: str,
    portfolio: dict[str, Position],
) -> None:
    signature = portfolio_signature(products, portfolio)
    if signature not in candidates:
        candidates[signature] = (name, portfolio)


def robust_score(row: dict[str, Any], criterion: str) -> float:
    if criterion == "mean":
        return row["mean"]
    if criterion == "p10":
        return row["p10"]
    if criterion == "p05":
        return row["p05"]
    if criterion == "min_regret":
        return -row["avg_regret"]
    if criterion == "score":
        return row["score"]
    raise ValueError(f"unknown criterion {criterion!r}")


def robust(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    budget = float(config.get("budget", 1_000_000))
    products = list(config["products"])
    product_set = set(products)

    candidates: dict[tuple[tuple[str, int], ...], tuple[str, dict[str, Position]]] = {}
    for name, raw_portfolio in config.get("portfolios", {}).items():
        add_candidate(candidates, products, name, parse_portfolio(name, raw_portfolio, product_set))

    scenario_list = ["base", "weighted"] + list(config.get("scenarios", {}))
    for scenario in scenario_list:
        if scenario == "weighted":
            expected_returns = weighted_expected_returns(config)
        else:
            ranges = scenario_ranges(config, scenario)
            expected_returns = {product: return_range.expected for product, return_range in ranges.items()}
        portfolio = optimize_ev_for_expected_returns(
            budget=budget,
            products=products,
            expected_returns=expected_returns,
            max_budget_pct=args.max_budget_pct,
            max_pct_per_product=args.max_pct_per_product,
            fixed_sides=True,
        )
        add_candidate(candidates, products, f"ev_opt_{scenario}", portfolio)

    candidate_rng = random.Random(args.seed)
    for i in range(args.candidate_worlds):
        expected_returns = sample_returns(config, candidate_rng, args.scenario)
        portfolio = optimize_ev_for_expected_returns(
            budget=budget,
            products=products,
            expected_returns=expected_returns,
            max_budget_pct=args.max_budget_pct,
            max_pct_per_product=args.max_pct_per_product,
            fixed_sides=True,
        )
        add_candidate(candidates, products, f"sample_ev_opt_{i}", portfolio)

    eval_rng = random.Random(args.seed + 1)
    values = {signature: [] for signature in candidates}
    regrets = {signature: [] for signature in candidates}
    for _ in range(args.worlds):
        expected_returns = sample_returns(config, eval_rng, args.scenario)
        oracle = oracle_portfolio_for_returns(
            budget=budget,
            products=products,
            expected_returns=expected_returns,
            max_budget_pct=args.max_budget_pct,
            max_pct_per_product=args.max_pct_per_product,
        )
        oracle_pnl = portfolio_pnl(budget, products, oracle, expected_returns)
        for signature, (_, portfolio) in candidates.items():
            candidate_pnl = portfolio_pnl(budget, products, portfolio, expected_returns)
            values[signature].append(candidate_pnl)
            regrets[signature].append(oracle_pnl - candidate_pnl)

    rows: list[dict[str, Any]] = []
    for signature, (name, portfolio) in candidates.items():
        sorted_values = sorted(values[signature])
        sorted_regrets = sorted(regrets[signature])
        value_mean = mean(values[signature])
        value_stdev = pstdev(values[signature]) if len(values[signature]) > 1 else 0.0
        avg_regret = mean(regrets[signature])
        row = {
            "portfolio": name,
            "used_pct": portfolio_budget_used(products, portfolio),
            "fee": portfolio_fee(budget, products, portfolio),
            "mean": value_mean,
            "p05": percentile(sorted_values, 0.05),
            "p10": percentile(sorted_values, 0.10),
            "p50": percentile(sorted_values, 0.50),
            "p90": percentile(sorted_values, 0.90),
            "p95": percentile(sorted_values, 0.95),
            "stdev": value_stdev,
            "avg_regret": avg_regret,
            "p90_regret": percentile(sorted_regrets, 0.90),
            "score": value_mean - args.risk_aversion * value_stdev - args.regret_aversion * avg_regret,
            "portfolio_obj": portfolio,
        }
        rows.append(row)

    rows.sort(key=lambda row: robust_score(row, args.criterion), reverse=True)
    print(
        f"Robust search scenario={args.scenario} worlds={args.worlds:,} "
        f"candidates={len(candidates):,} seed={args.seed} criterion={args.criterion}"
    )
    print(render_robust_table(rows[: args.top]))
    best = rows[0]
    print()
    print(f"Best portfolio: {best['portfolio']}")
    print(f"Budget used: {best['used_pct']}%")
    print(f"Fee: {format_money(best['fee'])}")
    print()
    print_portfolio(budget, products, best["portfolio_obj"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fee-aware Monte Carlo and EV optimizer for IMC Prosperity manual trading.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser("compare", help="Monte Carlo compare configured portfolios.")
    compare_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    compare_parser.add_argument("--scenario", default="all")
    compare_parser.add_argument("--trials", type=int, default=100_000)
    compare_parser.add_argument("--seed", type=int, default=42)
    compare_parser.set_defaults(func=compare)

    optimize_parser = subparsers.add_parser("optimize", help="Find an EV-optimal integer portfolio.")
    optimize_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    optimize_parser.add_argument("--scenario", default="weighted")
    optimize_parser.add_argument("--max-budget-pct", type=int, default=100)
    optimize_parser.add_argument("--max-pct-per-product", type=int, default=50)
    optimize_parser.add_argument(
        "--allow-wrong-way",
        action="store_true",
        help="Allow the optimizer to choose buy or sell regardless of expected return sign.",
    )
    optimize_parser.set_defaults(func=optimize)

    robust_parser = subparsers.add_parser(
        "robust",
        help="Generate many EV candidates and rank them across sampled belief worlds.",
    )
    robust_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    robust_parser.add_argument("--scenario", default="weighted")
    robust_parser.add_argument("--worlds", type=int, default=5_000)
    robust_parser.add_argument("--candidate-worlds", type=int, default=500)
    robust_parser.add_argument("--seed", type=int, default=42)
    robust_parser.add_argument("--top", type=int, default=10)
    robust_parser.add_argument("--max-budget-pct", type=int, default=100)
    robust_parser.add_argument("--max-pct-per-product", type=int, default=50)
    robust_parser.add_argument(
        "--criterion",
        choices=["mean", "p10", "p05", "min_regret", "score"],
        default="score",
    )
    robust_parser.add_argument(
        "--risk-aversion",
        type=float,
        default=0.05,
        help="Penalty multiplier for PnL standard deviation when criterion=score.",
    )
    robust_parser.add_argument(
        "--regret-aversion",
        type=float,
        default=0.25,
        help="Penalty multiplier for average oracle regret when criterion=score.",
    )
    robust_parser.set_defaults(func=robust)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
