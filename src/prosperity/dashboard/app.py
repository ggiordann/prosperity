from __future__ import annotations

from pathlib import Path

import streamlit as st

from prosperity.dashboard.data_access import fetch_table, open_db
from prosperity.dashboard.pages import candidates, lineage, overview, portal, runs, sources


def run_dashboard(db_path: Path, submissions_root: Path) -> None:
    connection = open_db(db_path)
    strategies = fetch_table(connection, "strategies")
    run_rows = fetch_table(connection, "runs")
    promotions = fetch_table(connection, "promotions")
    documents = fetch_table(connection, "documents")

    st.set_page_config(page_title="Prosperity Research Platform", layout="wide")
    page = st.sidebar.radio("Page", ["Overview", "Candidates", "Runs", "Lineage", "Sources", "Portal"])
    if page == "Overview":
        overview.render(strategies, run_rows, promotions)
    elif page == "Candidates":
        candidates.render(strategies)
    elif page == "Runs":
        runs.render(run_rows)
    elif page == "Lineage":
        lineage.render(strategies)
    elif page == "Sources":
        sources.render(documents)
    else:
        portal.render(submissions_root)
