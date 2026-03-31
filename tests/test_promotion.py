from __future__ import annotations

from prosperity.evaluation.promotion import champion_challenger_decision


def test_champion_challenger_decision_shadow_promotes_plateaued_alternate_family():
    best_candidate = {
        "decision": "promote",
        "family": "alt-family",
        "search_bucket": "family_lab",
        "metrics": {"total_pnl": 290.0},
        "robustness": {"score": 0.44},
        "validation": {"score": 0.70},
        "scoring": {"score": 0.69},
    }
    champion_eval = {
        "metrics": {"total_pnl": 300.0},
        "robustness": {"score": 0.33},
        "validation": {"score": 0.58},
        "scoring": {"score": 0.67},
    }
    decision, reason = champion_challenger_decision(
        best_candidate,
        champion_eval,
        champion_family="champion-family",
        min_improvement=5.0,
        stale_champion_cycles=12,
        shadow_pnl_gap=20.0,
        shadow_robustness_delta=0.05,
        shadow_validation_delta=0.08,
        plateau_state={"hold_streak": 14},
    )
    assert decision == "shadow_promote"
    assert "Shadow-promoted" in reason
