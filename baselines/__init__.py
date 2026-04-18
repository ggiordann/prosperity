"""Baseline strategy registry."""

from pathlib import Path

BASELINE_ROOT = Path(__file__).resolve().parent

BASELINES = {
    "legacy_jinxingtest": BASELINE_ROOT / "legacy_jinxingtest.py",
    "legacy_newalgo": BASELINE_ROOT / "legacy_newalgo.py",
    "round1_256418": BASELINE_ROOT / "round1_256418.py",
}
