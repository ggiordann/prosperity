from __future__ import annotations

import json
from pathlib import Path

from prosperity.compilation.submission_builder import build_submission_artifact
from prosperity.utils import ensure_dir


def package_manual_submission(
    output_root: Path,
    strategy_id: str,
    source_path: Path,
    metadata: dict,
    explanation: str,
) -> Path:
    package_dir = build_submission_artifact(
        strategy_id=strategy_id,
        spec=metadata,
        compiled_code=source_path.read_text(encoding="utf-8"),
        output_dir=ensure_dir(output_root),
        explanation=explanation,
    )
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["mode"] = "manual"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return package_dir
