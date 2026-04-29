from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BT = ROOT / "prosperity_rust_backtester"
MANIFEST = ROOT / "research" / "round5" / "generated_traders" / "validation_manifest.json"
OUT = ROOT / "research" / "round5" / "validation_results.csv"
DAY_RE = re.compile(r"^D\+(\d+)\s+(\d+)\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", re.MULTILINE)


def run_one(spec: dict) -> dict:
    cmd = [
        "./scripts/cargo_local.sh",
        "run",
        "--release",
        "--",
        "--trader",
        str(ROOT / spec["path"]),
        "--dataset",
        "round5",
        "--day",
        str(spec["test_day"]),
        "--products",
        "off",
        "--artifact-mode",
        "none",
    ]
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(Path.home() / "Library" / "Caches" / "rust_backtester" / "target")
    proc = subprocess.run(cmd, cwd=BT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, env=env)
    m = DAY_RE.search(proc.stdout)
    return {**spec, "returncode": proc.returncode, "test_pnl": float(m.group(3)) if m else None, "stdout_tail": proc.stdout[-1000:]}


def main() -> None:
    specs = json.loads(MANIFEST.read_text())
    rows = [run_one(spec) for spec in specs]
    df = pd.DataFrame(rows).sort_values(["test_day", "name"])
    df.to_csv(OUT, index=False)
    print(df[["name", "test_day", "test_pnl", "n_products"]].to_string(index=False))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
