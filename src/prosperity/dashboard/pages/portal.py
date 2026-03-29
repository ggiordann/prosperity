from __future__ import annotations

from pathlib import Path

import streamlit as st


def render(submissions_root: Path):
    st.header("Portal / Submission Packages")
    packages = sorted(path.name for path in submissions_root.iterdir() if path.is_dir()) if submissions_root.exists() else []
    st.write({"packages": packages})
