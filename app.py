"""
Nifty Total Market (Nifty 500 + Microcap 250) RS Rating scanner - Streamlit app.
RS Rating, Minervini Trend Template, VCP setups, volume breakouts, Weinstein stages,
liquidity flag, market breadth and sector strength.

Run locally:   pip install -r requirements.txt && streamlit run app.py
Deploy free:   push this folder to GitHub -> share.streamlit.io -> New app -> app.py

How the data arrives: a daily GitHub Actions job (build_data.py, see .github/workflows/) saves the
results to data/latest.csv after the market closes, and this app just reads them - so it opens in
seconds. Until the first daily run exists, the app falls back to calculating everything live.

Files in the repository: app.py, ui.py, nse500_rs_rating.py, build_data.py, requirements.txt,
.github/workflows/daily_scan.yml   (optional: .streamlit/config.toml)
"""
import json
import os
import re
import sys
from html import escape as _esc
from io import BytesIO
from datetime import datetime, timedelta, timezone

import pandas as pd
import numpy as np
import streamlit as st
import altair as alt
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nse500_rs_rating as m  # noqa: E402
import ui  # noqa: E402

CACHE_HOURS = 6
IST = timezone(timedelta(hours=5, minutes=30))
LIQ_TEXT = f"avg {m.LIQUIDITY_DAYS}-day traded value ≥ ₹{m.MIN_TRADED_VALUE_CR:.0f} crore"

st.set_page_config(page_title="MarketPulse 750", page_icon="📈", layout="wide")

# Inject a stylesheet early so loading messages are themed too. The user-selected
# font and density are restored from session state and controls appear in Settings.
font = st.session_state.get("appearance_font", list(ui.FONTS)[0])
density = st.session_state.get("appearance_density", "Comfortable")
ui.inject_css(font)

# ---------------- Page skeleton ----------------
# Containers are created in the order they appear on the page and filled later, so the filter
# widgets can run before the stat cards are counted while the layout stays top-to-bottom.
slot_notice = st.container()
slot_header = st.container()
slot_pills = st.container()
slot_stats = st.container()
slot_tabs = st.container()
slot_view = st.container()
with slot_view:
    with st.container(key="view-row"):
        v_title, v_view, v_filters, v_columns = st.columns([5, 1.7, 1.2, 1.9], gap="small", vertical_alignment="center")


_view_row_columns = {"used": False}   # only the first table on a screen takes the button in the view row


def _popover(container, label, **kwargs):
    """A popover button; falls back for Streamlit versions with the older width option."""
    try:
        return container.popover(label, width="stretch", **kwargs)
    except TypeError:
        return container.popover(label, use_container_width=True, **kwargs)


def _open_stock_search():
    """Top search box: choosing a stock opens its chart dialog, then the box clears itself."""
    pick = st.session_state.get("top_stock_search")
    if pick:
        st.session_state["_symbol_chart_request"] = str(pick).split(" · ", 1)[0].strip()
    st.session_state["top_stock_search"] = None


# ---------------- Data loading (cached, shared by all visitors) ----------------
DATA_DIR = os.path.join(HERE, "data")
LATEST = os.path.join(DATA_DIR, "latest.csv")
META = os.path.join(DATA_DIR, "meta.json")
# Optional live data source. When unset, the app reads the committed data/ folder in
# this checkout (ideal for a fresh fork). Set MARKETPULSE_DATA_URL (env var or Streamlit
# secret) to the raw data URL of your own repository to refresh without a redeploy.
def _configured_data_url():
    value = os.environ.get("MARKETPULSE_DATA_URL", "").strip()
    if not value:
        try:
            value = str(st.secrets.get("MARKETPULSE_DATA_URL", "") or "").strip()
        except Exception:
            value = ""
    return value.rstrip("/")


DATA_URL = _configured_data_url()


@st.cache_data(ttl=1800, show_spinner=False)
