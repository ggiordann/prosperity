from __future__ import annotations

import json

import streamlit as st


def render(strategies):
    st.header("Lineage")
    rows = []
    for row in strategies:
        spec = json.loads(row["spec_json"])
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "family": row["family"],
                "parents": ", ".join(spec["metadata"].get("parent_ids", [])),
                "created_by_role": spec["metadata"].get("created_by_role"),
            }
        )
    st.dataframe(rows)
