from __future__ import annotations


def promotion_decision(score: float, plagiarism_score: float, threshold: float = 0.55) -> tuple[str, str]:
    if plagiarism_score >= 0.82:
        return "blocked", "Hard blocked due to high external code similarity."
    if score >= threshold:
        return "promote", "Candidate cleared scoring and plagiarism thresholds."
    return "reject", "Candidate did not clear promotion threshold."
