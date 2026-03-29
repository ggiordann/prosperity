from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prosperity.dsl.schema import StrategySpec
from prosperity.utils import ensure_dir, json_dumps


def build_submission_artifact(
    strategy_id: str,
    spec: StrategySpec | dict[str, Any],
    compiled_code: str,
    output_dir: Path,
    explanation: str,
) -> Path:
    bundle_dir = ensure_dir(output_dir / strategy_id)
    metadata = spec.model_dump(mode="json") if isinstance(spec, StrategySpec) else spec
    (bundle_dir / "submission.py").write_text(compiled_code, encoding="utf-8")
    (bundle_dir / "metadata.json").write_text(json_dumps(metadata), encoding="utf-8")
    (bundle_dir / "explanation.md").write_text(explanation, encoding="utf-8")
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "strategy_id": strategy_id,
                "files": ["submission.py", "metadata.json", "explanation.md"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return bundle_dir
