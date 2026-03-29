from __future__ import annotations


def rows_to_chart_points(rows, value_key: str):
    return [{"label": row["strategy_id"] if "strategy_id" in row.keys() else row["run_id"], "value": row[value_key]} for row in rows if value_key in row.keys()]
