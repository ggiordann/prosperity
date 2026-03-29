from __future__ import annotations

import json
from pathlib import Path

import pytest

from prosperity.generation.family_registry import tutorial_market_maker


@pytest.fixture()
def sample_spec():
    return tutorial_market_maker()


@pytest.fixture()
def sample_backtester_stdout() -> str:
    return "\n".join(
        [
            "trader: /tmp/trader.py",
            "dataset: tutorial",
            "mode: summary",
            "artifacts: /tmp/runs",
            "SET DAY TICKS OWN_TRADES FINAL_PNL RUN_DIR",
            "SUB 0 1000 12 2770.5 runs/example-run",
            "PRODUCT SUB",
            "EMR 896.0",
            "TOM 1874.5",
        ]
    )


@pytest.fixture()
def temp_source_file(tmp_path: Path) -> Path:
    source = tmp_path / "candidate.py"
    source.write_text("class Trader:\n    pass\n", encoding="utf-8")
    return source


@pytest.fixture()
def sample_metadata() -> dict:
    return {"strategy_id": "demo", "family": "unit_test", "notes": ["hello"]}


@pytest.fixture()
def sample_manifest_json(sample_metadata: dict) -> str:
    return json.dumps(sample_metadata)
