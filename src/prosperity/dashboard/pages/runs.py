from __future__ import annotations

import streamlit as st


def render(runs):
    st.header("Runs")
    st.dataframe([dict(row) for row in runs])
