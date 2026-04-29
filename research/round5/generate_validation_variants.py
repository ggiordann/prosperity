from __future__ import annotations

import json
from pathlib import Path

from generate_variants import ALL_PRODUCTS, BASE_RUN, OUT, render


def load_day_product_pnl() -> dict[int, dict[str, float]]:
    out = {}
    for path in sorted(BASE_RUN.glob("round5-day+*-metrics.json")):
        day = int(path.name.split("+")[1].split("-")[0])
        data = json.loads(path.read_text())
        out[day] = {p: float(data["final_pnl_by_product"].get(p, 0.0)) for p in ALL_PRODUCTS}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pnl = load_day_product_pnl()
    rows = []
    for test_day in sorted(pnl):
        train_days = [d for d in sorted(pnl) if d != test_day]
        train_totalpos = [p for p in ALL_PRODUCTS if sum(pnl[d][p] for d in train_days) > 0]
        train_pos2 = [p for p in ALL_PRODUCTS if sum(pnl[d][p] > 0 for d in train_days) >= 1 and sum(pnl[d][p] for d in train_days) > 0]
        for filter_name, products in [("train_totalpos", train_totalpos), ("train_pos2", train_pos2)]:
            for micro in [False, True]:
                name = f"val_{filter_name}_test{test_day}_{'micro' if micro else 'mm'}"
                render(
                    OUT / f"{name}.py",
                    products=products,
                    quote_size=5,
                    improve=1,
                    use_micro_lag=micro,
                    micro_bias_mult=1.0,
                    micro_take_edge=4.0,
                )
                rows.append({"name": name, "path": str((OUT / f"{name}.py").relative_to(Path(__file__).resolve().parents[2])), "test_day": test_day, "n_products": len(products)})
    (OUT / "validation_manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} validation variants")


if __name__ == "__main__":
    main()
