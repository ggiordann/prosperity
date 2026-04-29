from __future__ import annotations

import json
from pathlib import Path

from generate_variants import ALL_PRODUCTS, BASE_RUN, OUT, render


def baseline_table() -> dict[str, list[float]]:
    out = {p: [] for p in ALL_PRODUCTS}
    for path in sorted(BASE_RUN.glob("round5-day+*-metrics.json")):
        data = json.loads(path.read_text())
        for p in ALL_PRODUCTS:
            out[p].append(float(data["final_pnl_by_product"].get(p, 0.0)))
    return out


def main() -> None:
    pnl = baseline_table()
    totalpos = [p for p, xs in pnl.items() if sum(xs) > 0]
    drop_obvious = [
        p for p, xs in pnl.items()
        if all(x < 0 for x in xs) or (sum(x > 0 for x in xs) <= 1 and sum(xs) < -3000)
    ]
    robust = [p for p in ALL_PRODUCTS if p not in drop_obvious]
    specs = []
    for subset_name, products in [("totalpos", totalpos), ("robust", robust)]:
        for mult in [0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00]:
            for take in [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]:
                for min_edge in [0.0, 0.5, 1.0]:
                    name = f"focus_{subset_name}_m{str(mult).replace('.','p')}_t{str(take).replace('.','p')}_e{str(min_edge).replace('.','p')}"
                    path = OUT / f"{name}.py"
                    render(
                        path,
                        products=products,
                        quote_size=5,
                        improve=1,
                        min_edge=min_edge,
                        use_micro_lag=True,
                        micro_bias_mult=mult,
                        micro_take_edge=take,
                    )
                    specs.append({"name": name, "path": str(path.relative_to(Path(__file__).resolve().parents[2])), "n_products": len(products), "micro_bias_mult": mult, "micro_take_edge": take, "min_edge": min_edge})
    manifest = OUT / "focused_manifest.json"
    manifest.write_text(json.dumps(specs, indent=2), encoding="utf-8")
    print(f"wrote {len(specs)} focused variants to {manifest}")


if __name__ == "__main__":
    main()
