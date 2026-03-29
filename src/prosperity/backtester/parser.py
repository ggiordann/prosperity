from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class BacktestDayResult(BaseModel):
    set_name: str
    day: int
    ticks: int
    own_trades: int
    final_pnl: float
    run_dir: str


class ProductContribution(BaseModel):
    product: str
    values: dict[str, float]


class BacktestSummary(BaseModel):
    trader: str
    dataset: str
    mode: str
    artifacts: str
    day_results: list[BacktestDayResult] = Field(default_factory=list)
    product_contributions: list[ProductContribution] = Field(default_factory=list)

    @property
    def total_final_pnl(self) -> float:
        return sum(row.final_pnl for row in self.day_results)


DAY_ROW = re.compile(
    r"^(?P<set_name>\S+)\s+(?P<day>-?\d+)\s+(?P<ticks>\d+)\s+(?P<own_trades>\d+)\s+(?P<final_pnl>-?\d+(?:\.\d+)?)\s+(?P<run_dir>.+)$"
)


def parse_backtester_output(stdout: str) -> BacktestSummary:
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    trader = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("trader:")), "")
    dataset = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("dataset:")), "")
    mode = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("mode:")), "")
    artifacts = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("artifacts:")), "")
    summary = BacktestSummary(trader=trader, dataset=dataset, mode=mode, artifacts=artifacts)

    product_header: list[str] | None = None
    for line in lines:
        match = DAY_ROW.match(line)
        if match:
            summary.day_results.append(
                BacktestDayResult(
                    set_name=match.group("set_name"),
                    day=int(match.group("day")),
                    ticks=int(match.group("ticks")),
                    own_trades=int(match.group("own_trades")),
                    final_pnl=float(match.group("final_pnl")),
                    run_dir=match.group("run_dir").strip(),
                )
            )
            continue
        if line.startswith("PRODUCT"):
            product_header = line.split()
            continue
        if product_header and line[0].isalnum():
            parts = line.split()
            if len(parts) == len(product_header):
                summary.product_contributions.append(
                    ProductContribution(
                        product=parts[0],
                        values={
                            product_header[i]: float(parts[i])
                            for i in range(1, len(parts))
                        },
                    )
                )
    return summary


def summary_to_dict(summary: BacktestSummary) -> dict[str, Any]:
    return summary.model_dump()
