from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BT = ROOT / "prosperity_rust_backtester"
MANIFEST = Path(os.environ.get("R5_MANIFEST", ROOT / "research" / "round5" / "generated_traders" / "manifest.json"))
OUT = Path(os.environ.get("R5_RESULTS", ROOT / "research" / "round5" / "variant_results.csv"))
TOTAL_RE = re.compile(r"^TOTAL\s+-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", re.MULTILINE)
DAY_RE = re.compile(r"^D\+(\d+)\s+(\d+)\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", re.MULTILINE)


def run_one(spec: dict) -> dict:
    trader = ROOT / spec["path"]
    cmd = [
        "./scripts/cargo_local.sh",
        "run",
        "--release",
        "--",
        "--trader",
        str(trader),
        "--dataset",
        "round5",
        "--products",
        "off",
        "--artifact-mode",
        "none",
    ]
    env = os.environ.copy()
    env["CARGO_TARGET_DIR"] = str(Path.home() / "Library" / "Caches" / "rust_backtester" / "target")
    proc = subprocess.run(cmd, cwd=BT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90, env=env)
    text = proc.stdout
    total = None
    match = TOTAL_RE.search(text)
    if match:
        total = float(match.group(1))
    days = {f"day_{m.group(1)}": float(m.group(3)) for m in DAY_RE.finditer(text)}
    return {
        **spec,
        "returncode": proc.returncode,
        "total_pnl": total,
        **days,
        "stdout_tail": text[-1000:],
    }


def main() -> None:
    specs = json.loads(MANIFEST.read_text())
    if len(sys.argv) > 1:
        needles = sys.argv[1:]
        specs = [s for s in specs if any(n in s["name"] for n in needles)]
    workers = int(os.environ.get("R5_WORKERS", "4"))
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, spec) for spec in specs]
        for idx, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            rows.append(row)
            if idx % 10 == 0 or idx == len(futures):
                best = max((r for r in rows if r.get("total_pnl") is not None), key=lambda r: r["total_pnl"], default=None)
                msg = f"{idx}/{len(futures)}"
                if best:
                    msg += f" best={best['name']} pnl={best['total_pnl']:.1f}"
                print(msg, flush=True)
    df = pd.DataFrame(rows).sort_values("total_pnl", ascending=False)
    df.to_csv(OUT, index=False)
    print(df[["name", "total_pnl", "day_2", "day_3", "day_4", "n_products"]].head(30).to_string(index=False))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
