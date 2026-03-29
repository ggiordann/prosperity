from __future__ import annotations

import streamlit as st


def render(strategies, runs, promotions):
    st.header("Overview")
    st.metric("Strategies", len(strategies))
    st.metric("Runs", len(runs))
    st.metric("Promotions", len(promotions))
    st.subheader("Recent Strategies")
    st.dataframe([dict(row) for row in strategies[:10]])
