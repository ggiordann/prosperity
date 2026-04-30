from __future__ import annotations

import json
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
BT = ROOT / "prosperity_rust_backtester"
MANIFEST = ROOT / "research" / "round5" / "pebbles" / "generated_traders" / "manifest.json"
OUT = ROOT / "research" / "round5" / "pebbles" / "variant_results.csv"
TOTAL_RE = re.compile(r"^TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", re.MULTILINE)
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
        "--products",
        "off",
        "--artifact-mode",
        "none",
    ]
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(Path.home() / "Library" / "Caches" / "rust_backtester" / "target")
    proc = subprocess.run(cmd, cwd=BT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, env=env)
    text = proc.stdout
    match = TOTAL_RE.search(text)
    days = {f"day_{m.group(1)}": float(m.group(3)) for m in DAY_RE.finditer(text)}
    return {
        **spec,
        "returncode": proc.returncode,
        "total_pnl": float(match.group(1)) if match else None,
        **days,
        "stdout_tail": text[-1000:],
    }


def main() -> None:
    specs = json.loads(MANIFEST.read_text())
    workers = int(os.environ.get("R5_WORKERS", "4"))
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, spec) for spec in specs]
        for idx, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if idx % 10 == 0 or idx == len(futures):
                best = max((r for r in rows if r.get("total_pnl") is not None), key=lambda r: r["total_pnl"], default=None)
                suffix = f" best={best['name']} pnl={best['total_pnl']:.1f}" if best else ""
                print(f"{idx}/{len(specs)}{suffix}", flush=True)
    df = pd.DataFrame(rows).sort_values("total_pnl", ascending=False)
    df.to_csv(OUT, index=False)
    print(df[["name", "total_pnl", "day_2", "day_3", "day_4"]].head(25).to_string(index=False))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
