from __future__ import annotations

import json

from prosperity.compilation.submission_builder import build_submission_artifact
from prosperity.external.manual_submission import package_manual_submission


def test_build_submission_artifact_writes_bundle(sample_spec, tmp_path):
    bundle_dir = build_submission_artifact(
        strategy_id=sample_spec.metadata.id,
        spec=sample_spec,
        compiled_code="class Trader:\n    pass\n",
        output_dir=tmp_path,
        explanation="demo",
    )
    assert (bundle_dir / "submission.py").exists()
    assert (bundle_dir / "metadata.json").exists()


def test_manual_submission_marks_bundle_as_manual(temp_source_file, sample_metadata, tmp_path):
    bundle_dir = package_manual_submission(
        output_root=tmp_path,
        strategy_id="manual-demo",
        source_path=temp_source_file,
        metadata=sample_metadata,
        explanation="manual package",
    )
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "manual"
