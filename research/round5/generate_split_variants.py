from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "round5" / "generated_traders"
BASE = OUT / "split_micro_totalpos.py"


def main() -> None:
    text0 = BASE.read_text(encoding="utf-8")
    specs = []
    for oval_m in [1.00, 1.25, 1.50]:
        for oval_t in [5.0, 5.5, 6.0, 6.5]:
            for oval_e in [0.0, 0.5, 1.0]:
                for square_m in [0.50, 0.75, 1.00, 1.25]:
                    for square_t in [5.0, 5.5, 6.0, 6.5]:
                        for square_e in [0.0, 0.5]:
                            name = (
                                f"split_om{str(oval_m).replace('.','p')}_ot{str(oval_t).replace('.','p')}_oe{str(oval_e).replace('.','p')}"
                                f"_sm{str(square_m).replace('.','p')}_st{str(square_t).replace('.','p')}_se{str(square_e).replace('.','p')}"
                            )
                            text = text0
                            text = text.replace("fair += 1.25 * 0.067 * (hist[-1] - hist[-51])", f"fair += {oval_m!r} * 0.067 * (hist[-1] - hist[-51])")
                            text = text.replace("take_edge = 5.5\n                mm_edge = 0.5", f"take_edge = {oval_t!r}\n                mm_edge = {oval_e!r}")
                            text = text.replace("fair += 0.75 * 0.138 * (hist[-1] - hist[-101])", f"fair += {square_m!r} * 0.138 * (hist[-1] - hist[-101])")
                            text = text.replace("take_edge = 6.0\n                mm_edge = 0.0", f"take_edge = {square_t!r}\n                mm_edge = {square_e!r}")
                            path = OUT / f"{name}.py"
                            path.write_text(text, encoding="utf-8")
                            specs.append({"name": name, "path": str(path.relative_to(ROOT)), "n_products": 38, "oval_m": oval_m, "oval_t": oval_t, "oval_e": oval_e, "square_m": square_m, "square_t": square_t, "square_e": square_e})
    manifest = OUT / "split_manifest.json"
    manifest.write_text(json.dumps(specs, indent=2), encoding="utf-8")
    print(f"wrote {len(specs)} split variants to {manifest}")


if __name__ == "__main__":
    main()
