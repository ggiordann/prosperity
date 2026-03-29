from __future__ import annotations

import streamlit as st


def render(strategies):
    st.header("Candidates")
    st.dataframe([dict(row) for row in strategies])
