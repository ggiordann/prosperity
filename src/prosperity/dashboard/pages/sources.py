from __future__ import annotations

import streamlit as st


def render(documents):
    st.header("Sources")
    st.dataframe([dict(row) for row in documents])
