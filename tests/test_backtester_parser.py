from __future__ import annotations

from prosperity.backtester.parser import parse_backtester_output


def test_parse_backtester_output_extracts_summary(sample_backtester_stdout):
    summary = parse_backtester_output(sample_backtester_stdout)
    assert summary.dataset == "tutorial"
    assert summary.total_final_pnl == 2770.5
    assert summary.day_results[0].set_name == "SUB"
    assert summary.product_contributions[1].values["SUB"] == 1874.5
