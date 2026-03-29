from __future__ import annotations

from prosperity.evaluation.plagiarism_guard import scan_public_code_similarity


def test_plagiarism_guard_flags_identical_reference(tmp_path):
    research_root = tmp_path / ".research_repos"
    repo_dir = research_root / "demo_repo"
    repo_dir.mkdir(parents=True)
    reference_code = "def alpha():\n    return 42\n"
    (repo_dir / "strategy.py").write_text(reference_code, encoding="utf-8")
    result = scan_public_code_similarity(reference_code, research_root, tmp_path / "cache")
    assert result["max_score"] > 0.95
    assert result["nearest"][0]["path"].endswith("strategy.py")
