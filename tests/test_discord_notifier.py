from __future__ import annotations

from prosperity.external.discord_notifier import (
    build_cycle_summary_payload,
    render_cycle_summary_message,
    send_cycle_summary_message,
)
from prosperity.settings import AppSettings


def _sample_cycle_summary() -> dict:
    return {
        "iteration": 3,
        "session_name": "discord-test",
        "decision": "hold",
        "champion_before": "champion-alpha",
        "champion_pnl": 2944.5,
        "candidate_count": 4,
        "ingested_documents": 59,
        "strategist": {
            "thesis": "tighten execution around the current tomato alpha while keeping emr stable.",
        },
        "best_candidate": {
            "strategy_id": "candidate-beta",
            "metrics": {
                "total_pnl": 2610.0,
                "own_trade_count": 142,
                "per_product_pnl": {
                    "EMR": {"SUB": 896.0},
                    "TOM": {"SUB": 1714.0},
                },
            },
            "scoring": {"score": 0.653},
            "robustness": {"score": 0.307},
            "plagiarism": {"max_score": 0.164},
        },
    }


def test_render_cycle_summary_message_contains_key_fields():
    settings = AppSettings()
    rendered = render_cycle_summary_message(_sample_cycle_summary(), settings)
    assert "strategy:" in rendered
    assert "pnl:" in rendered
    assert "health:" in rendered
    assert "candidate-beta" in rendered


def test_build_cycle_summary_payload_creates_embed():
    settings = AppSettings()
    payload = build_cycle_summary_payload(_sample_cycle_summary(), settings)
    assert "embeds" in payload
    assert len(payload["embeds"]) == 1
    embed = payload["embeds"][0]
    assert embed["title"] == "prosperity loop #3"
    field_names = [field["name"] for field in embed["fields"]]
    assert "strategy" in field_names
    assert "pnl vs champion" in field_names
    assert "system health" in field_names
    assert payload["content"] is None
    assert payload["allowed_mentions"] == {"parse": []}


def test_build_cycle_summary_payload_pings_on_promotion():
    settings = AppSettings()
    settings.discord.promote_ping_user_id = "1487799311113650316"
    cycle = _sample_cycle_summary()
    cycle["decision"] = "promote"
    payload = build_cycle_summary_payload(cycle, settings)
    assert payload["content"] == "<@1487799311113650316>"
    assert payload["allowed_mentions"] == {"users": ["1487799311113650316"]}


def test_send_cycle_summary_message_skips_without_bot_token():
    settings = AppSettings()
    settings.discord.enabled = True
    settings.discord.channel_id = "1487759408711729192"
    settings.discord.bot_token = None
    result = send_cycle_summary_message(_sample_cycle_summary(), settings)
    assert result["status"] == "skipped"
    assert "bot_token" in result["reason"]
