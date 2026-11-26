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
# --- FUNDAMENTALS PANEL START (rollback-safe) ---
import fundamentals_panel as fp  # noqa: E402
# --- FUNDAMENTALS PANEL END ---

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
def load_saved(key, base=None):
    """Load the saved scan. `key` is a freshness marker for Streamlit's cache;
    `base` is the folder or URL containing latest.csv and meta.json."""
    source = base if base is not None else key
    cache_bust = key if isinstance(source, str) and source.startswith("http") else None
    return m.load_saved_results(source, cache_bust=cache_bust)


@st.cache_data(ttl=300, max_entries=30, show_spinner=False)
def load_scan_history_index(refresh_token="initial"):
    """List dated snapshots from the configured source (local folder by default)."""
    if not DATA_URL:
        path = os.path.join(DATA_DIR, "history", "index.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("scans", [])
    response = requests.get(
        f"{DATA_URL}/history/index.json", params={"_": refresh_token}, timeout=20
    )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("scans", [])


@st.cache_data(ttl=300, max_entries=30, show_spinner=False)
def load_scan_history(scan_date, refresh_token="initial"):
    """Load one dated full-scan CSV and restore boolean columns from CSV text."""
    if DATA_URL:
        url = f"{DATA_URL}/history/{scan_date}.csv"
        response = requests.get(url, params={"_": refresh_token}, timeout=30)
        response.raise_for_status()
        frame = pd.read_csv(BytesIO(response.content))
    else:
        frame = pd.read_csv(os.path.join(DATA_DIR, "history", f"{scan_date}.csv"))
    for column in frame.columns:
        if frame[column].dtype == object:
            values = set(frame[column].dropna().unique())
            if values and values <= {"True", "False", True, False}:
                frame[column] = frame[column].map(
                    {"True": True, "False": False, True: True, False: False}
                ).fillna(False).astype(bool)
    return frame


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_universe():
    """Live fallback: Nifty Total Market list from NSE -> local copy -> Nifty 500 + Microcap 250."""
    return m.load_universe(local_file=os.path.join(HERE, m.LOCAL_UNIVERSE_FILE))


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def load_shares(tickers: tuple):
    """Live fallback: shares outstanding from Yahoo (cached for a week)."""
    return m.download_shares(list(tickers))


@st.cache_data(ttl=CACHE_HOURS * 3600, show_spinner=False)
def compute(meta: pd.DataFrame, shares: pd.Series):
    """Live fallback: download everything and calculate inside the app (3-5 minutes)."""
    md = m.download_market_data(meta["Ticker"].tolist())
    prices = md["Close"]
    bench = m.get_benchmark()
    result, as_of = m.build_table(prices, bench, meta, ohlcv=md, shares=shares)
    return result, as_of, datetime.now(IST), prices.shape[1]


@st.cache_data(ttl=3600, show_spinner=False, max_entries=200)
def load_chart_history(symbol: str, period: str):
    """Cache on-demand chart downloads so reopening the same stock is instant."""
    return m.download_chart_history(symbol, period)


saved = None
remote_data_error = None
if DATA_URL:
    try:
        refresh_token = st.session_state.get("data_refresh_token", "initial")
        saved = load_saved(f"{DATA_URL}:{refresh_token}", DATA_URL)
    except Exception as e:
        remote_data_error = e
        saved = None
if saved is None and os.path.exists(LATEST):
    try:
        # The scan can refresh meta.json without changing latest.csv (for example, if
        # the market data is identical). Track both files so the Updated time cannot go stale.
        saved = load_saved((os.path.getmtime(LATEST), os.path.getmtime(META)), DATA_DIR)
    except Exception as e:
        st.warning(f"Could not read the saved data ({e}). Calculating live instead.")

if saved is not None:
    mode = "saved"
    result, info = saved
    as_of = pd.Timestamp(info["as_of"])
    fetched_at = datetime.fromisoformat(info["generated_at"])
    n_universe = int(info.get("universe", len(result)))
else:
    mode = "live"
    st.info("No saved daily data found yet, so the app is calculating everything live. This takes "
            "3-5 minutes. Once the daily GitHub job has run, this page will open in seconds.")
    meta = fetch_universe()
    if meta is None:
        st.warning("Could not download the Nifty Total Market list from NSE. Upload "
                   "`ind_niftytotalmarket_list.csv` (nseindia.com → Indices → Nifty Total Market → "
                   "Download list), or add it to the app folder.")
        up = st.file_uploader("ind_niftytotalmarket_list.csv", type="csv")
        if up is None:
            st.stop()
        meta = m.parse_universe(pd.read_csv(up))
    n_universe = len(meta)

    try:
        with st.spinner("Downloading ~750 stocks from Yahoo Finance (first load takes 3-5 minutes)..."):
            if st.session_state.get("shares_failed"):             # Yahoo throttled us: retry on Refresh only
                shares = pd.Series(float("nan"), index=meta["Ticker"])
            else:
                shares = load_shares(tuple(meta["Ticker"]))
                if shares.notna().mean() < 0.5:                   # don't keep a bad result for a week
                    load_shares.clear()
                    st.session_state["shares_failed"] = True
            result, as_of, fetched_at, n_prices = compute(meta, shares)
    except Exception as e:
        st.error(f"Data download failed: {e}")
        if st.button("Retry"):
            st.rerun()
        st.stop()

if remote_data_error is not None:
    st.warning(f"Could not fetch the latest scan files from GitHub ({remote_data_error}). "
               "Showing the deployed local copy if available.")

n_liquid = int(result["Liquid"].sum())
market_context = m.market_breadth(result)

def reload_latest_data():
    load_saved.clear()
    load_scan_history_index.clear()
    load_scan_history.clear()
    st.session_state["data_refresh_token"] = datetime.now(IST).isoformat(timespec="seconds")
    st.session_state["latest_data_refresh_notice"] = True
    if mode == "live":
        compute.clear()
        fetch_universe.clear()
        st.session_state.pop("shares_failed", None)
    st.rerun()


with slot_header:
    head_left, head_theme, head_right = st.columns([3, .62, 1.15], gap="small", vertical_alignment="center")
    with head_left:
        ui.brand("MarketPulse 750", "Nifty Total Market · Momentum &amp; relative strength",
                 "RS, trend, VCP and breakout scans across the Nifty Total Market (Nifty 500 + Microcap 250).")
    with head_theme:
        with st.container(key="theme-toggle"):
            _theme_label = lambda value: "☀️" if value == "light" else "🌙"
            try:
                st.segmented_control("Theme", ["light", "dark"], format_func=_theme_label,
                                     key="appearance_theme", label_visibility="collapsed",
                                     help="Switch the whole app between light and dark theme")
            except (TypeError, AttributeError):  # older Streamlit versions
                st.radio("Theme", ["light", "dark"], format_func=_theme_label,
                         key="appearance_theme", horizontal=True, label_visibility="collapsed")
    with head_right:
        _names = result["Company Name"].fillna("").astype(str)
        search_labels = sorted(f"{sym} · {name}" if name else str(sym)
                               for sym, name in zip(result["Symbol"].astype(str), _names))
        st.selectbox("Search any stock", search_labels, index=None, placeholder="Search any stock…",
                     key="top_stock_search", label_visibility="collapsed", on_change=_open_stock_search)
with slot_pills:
    ui.pills([f"<b>As of</b> {as_of:%d %b %Y}", f"<b>Updated</b> {fetched_at:%d %b, %H:%M} IST",
              f"<b>{len(result)}</b> of {n_universe} stocks rated", f"<b>{n_liquid}</b> liquid",
              f"<b>Market breadth</b> {market_context['market_state']}"])
age_days = (datetime.now(IST).date() - as_of.date()).days
if mode == "saved" and age_days > 4:
    with slot_notice:
        st.warning(f"⚠️ This data is from {as_of:%d %b %Y} ({age_days} days ago). The daily job may have "
                   f"stopped - open your GitHub repository's **Actions** tab to check.")

# ---------------- Appearance and filters ----------------
custom_rules = []


def reset_filters():
    """Return every filter widget to its default on the next rerun."""
    keys = ["filter_liquid_only", "filter_min_cap", "filter_include_unknown",
            "filter_min_rs", "filter_pref_rs", "filter_rsi_min", "filter_sector",
            "filter_search", "custom_screen_metrics"]
    for key in keys:
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith(("custom_operator_", "custom_value_",
                           "custom_lower_", "custom_upper_")):
            st.session_state.pop(key, None)


filters_pop = _popover(v_filters, "Filters", icon=":material/tune:")
with filters_pop:
    st.markdown("##### Filters")
    liquid_only = st.toggle("Liquid stocks only", value=False, key="filter_liquid_only",
                            help=f"Liquid = {LIQ_TEXT}. Applies to the stock lists. Breadth and sector "
                                 f"figures always use liquid stocks.")
    cap_ok = bool(result["Market_Cap_Cr"].notna().mean() >= 0.5)
    min_cap = st.number_input("Market cap above (₹ crore)", min_value=0, value=500, step=100,
                              key="filter_min_cap",
                              disabled=not cap_ok,
                              help="Market cap = shares outstanding × latest close (Yahoo Finance). "
                                   "Set 0 to switch the filter off. Applies to the stock lists; breadth, "
                                   "sector figures don't use it.")
    incl_unknown = st.checkbox("Include unknown market cap", value=False, key="filter_include_unknown",
                               disabled=not cap_ok,
                               help="Stocks for which Yahoo has no share count.")
    if cap_ok:
        n_cap = int((result["Market_Cap_Cr"] > min_cap).sum())
        n_unk = int(result["Market_Cap_Cr"].isna().sum())
        st.caption(f"{n_cap} stocks above ₹{min_cap:,} cr · {n_unk} with unknown market cap")
    else:
        st.caption("⚠️ Market cap data is missing from the current data, so this filter is off. "
                   "It is usually back after the next daily update.")
    min_rs = st.slider("Minimum RS Rating", 1, 99, 1, key="filter_min_rs")
    pref_rs = st.slider("RS for 'Top picks'", 50, 99, m.PREFERRED_RS, key="filter_pref_rs")
    rsi_min = st.slider("RSI above (Top picks)", 0, 80, 50, key="filter_rsi_min")
    pick_sector = st.multiselect("Sector", sorted(result["Sector"].dropna().unique()), key="filter_sector")
    q = st.text_input("Search symbol / company", key="filter_search")
    custom_metric_fields = [
        "RS_Rating", "RS_Change", "RS_Excess_3M_%", "RS_Excess_6M_%", "Weighted_Return_%",
        "TT_Score", "RSI14", "Pct_Above_50SMA", "Pct_From_52W_High", "Vol_x_50d",
        "Up_Down_Vol_Ratio_20D", "Avg_Value_Cr", "Market_Cap_Cr", "Sector_Strength",
        "Pct_To_Pivot", "Breakout_Vol_x", "Base_Days", "Base_Depth_%",
    ]
    metric_options = {
        f"{ui.SPEC[field]['t']} · {field}": field
        for field in custom_metric_fields
        if field in result.columns and field in ui.SPEC
        and pd.api.types.is_numeric_dtype(result[field].dtype)
        and not pd.api.types.is_bool_dtype(result[field].dtype)
    }
    with st.expander("🧰 Custom screen builder", expanded=False):
        picked_metrics = st.multiselect(
            "Add numeric conditions",
            list(metric_options),
            max_selections=3,
            key="custom_screen_metrics",
            help="Choose up to three numeric fields. Conditions combine with AND.",
        )
        if picked_metrics:
            st.caption("All selected conditions must match. These rules affect stock-list screens only.")
        for option in picked_metrics:
            field = metric_options[option]
            values = pd.to_numeric(result[field], errors="coerce").dropna()
            if values.empty:
                continue
            low, high = float(values.min()), float(values.max())
            step = max(0.1, (high - low) / 100)
            middle = float(values.median())
            q25, q75 = float(values.quantile(.25)), float(values.quantile(.75))
            st.markdown(f"**{ui.SPEC[field]['t']}**")
            operator = st.selectbox(
                "Condition", ["At least", "At most", "Between"],
                key=f"custom_operator_{field}",
            )
            if operator == "Between":
                lower = st.number_input("From", value=q25, step=step, format="%.2f",
                                        key=f"custom_lower_{field}")
                upper = st.number_input("To", value=q75, step=step, format="%.2f",
                                        key=f"custom_upper_{field}")
                custom_rules.append((field, operator, lower, upper))
            else:
                threshold = st.number_input("Value", value=middle, step=step, format="%.2f",
                                            key=f"custom_value_{field}")
                custom_rules.append((field, operator, threshold, None))
    with st.expander("🎨 Appearance", expanded=False):
        font = st.selectbox("Font", list(ui.FONTS), index=0, key="appearance_font")
        density = st.radio("Table density", ["Comfortable", "Compact"], horizontal=True,
                           key="appearance_density")
        st.caption("Use the ☀️ / 🌙 switch in the header to change the whole app's "
                   "theme instantly — including charts and tables.")
    st.divider()
    st.caption(f"Prices as of **{as_of.date()}**  \nUpdated {fetched_at:%d %b %Y, %H:%M} IST  \n" +
               ("Refreshed automatically every weekday evening (~5 pm IST)" if mode == "saved"
                else f"Live calculation - refreshes every {CACHE_HOURS} hours"))
    c_reset, c_reload = st.columns(2)
    with c_reset:
        if st.button("🧹 Reset filters", use_container_width=True, key="reset_filters"):
            reset_filters()
    with c_reload:
        if st.button("🔄 Reload data", use_container_width=True, key="reload_filters"):
            reload_latest_data()

if st.session_state.pop("latest_data_refresh_notice", False):
    if remote_data_error is None and mode == "saved":
        st.toast("Loaded the latest scan files from GitHub.", icon="✅")
    elif remote_data_error is not None:
        st.toast("GitHub refresh failed; showing the deployed copy if available.", icon="⚠️")
    else:
        st.toast("No saved scan found; calculating data live.", icon="ℹ️")

ui.inject_css(font)

# ---------------- Apply filters ----------------
def apply_stock_filters(frame):
    """Apply the current Filters to a current or historical scan."""
    filtered = frame
    if liquid_only and "Liquid" in filtered.columns:
        filtered = filtered[filtered["Liquid"]]
    if cap_ok and min_cap > 0 and "Market_Cap_Cr" in filtered.columns:
        keep = filtered["Market_Cap_Cr"] > min_cap
        if incl_unknown:
            keep |= filtered["Market_Cap_Cr"].isna()
        filtered = filtered[keep]
    if "RS_Rating" in filtered.columns:
        filtered = filtered[filtered["RS_Rating"] >= min_rs]
    if pick_sector and "Sector" in filtered.columns:
        filtered = filtered[filtered["Sector"].isin(pick_sector)]
    if q.strip() and {"Symbol", "Company Name"}.issubset(filtered.columns):
        search = q.strip().lower()
        filtered = filtered[
            filtered["Symbol"].fillna("").str.lower().str.contains(search, regex=False)
            | filtered["Company Name"].fillna("").str.lower().str.contains(search, regex=False)
        ]
    for field, operator, lower_or_value, upper in custom_rules:
        if field not in filtered.columns:
            return filtered.iloc[0:0]
        values = pd.to_numeric(filtered[field], errors="coerce")
        if operator == "At least":
            filtered = filtered[values >= lower_or_value]
        elif operator == "At most":
            filtered = filtered[values <= lower_or_value]
        else:
            filtered = filtered[(values >= lower_or_value) & (values <= upper)]
    return filtered


def _vcp_breakout_frame(frame):
    """Fresh VCP pivot crosses that are still trending up.

    Uses the dedicated scan columns when available. Older daily snapshots are
    approximated from the generic breakout fields, so this view never breaks
    while waiting for the first scan that writes the new columns.
    """
    if frame is None or frame.empty:
        return frame
    out = frame.copy()

    def num(col):
        return pd.to_numeric(out[col], errors="coerce") if col in out.columns else pd.Series(np.nan, index=out.index)

    if "VCP_Breakout_Days_Ago" in out.columns:
        days, vol_x, ret = (num("VCP_Breakout_Days_Ago"), num("VCP_Breakout_Vol_x"),
                            num("VCP_Breakout_Return_%"))
    else:
        vcp = out.get("VCP", pd.Series(False, index=out.index)).fillna(False).astype(bool)
        above = num("Pct_To_Pivot") < 0
        brk = out.get("Vol_Breakout", pd.Series(False, index=out.index)).fillna(False).astype(bool)
        days = num("Breakout_Days_Ago").where(vcp & above & brk)
        vol_x = num("Breakout_Vol_x")
        pivot, close = num("Pivot"), num("Close")
        ret = ((close / pivot - 1) * 100).where(pivot > 0)
    out["VCP_Breakout_Days_Ago"] = days
    out["VCP_Breakout_Vol_x"] = vol_x
    out["VCP_Breakout_Return_%"] = ret

    fresh = days.notna() & (days <= getattr(m, "VCP_BREAKOUT_RECENT", 5))
    # Pct_To_Pivot is pivot/close - 1, so a negative value means price is above the pivot.
    pivot_pct = num("Pct_To_Pivot")
    above_pivot = pivot_pct < 0 if pivot_pct.notna().any() else (num("Close") > num("Pivot"))
    stage2 = num("Stage_Num") == 2
    rs_up = out.get("RS_Line_Uptrend", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    above50 = num("Pct_Above_50SMA") > 0
    out = out.assign(_rs_sort=num("RS_Rating"))
    return (out[fresh & above_pivot & stage2 & rs_up & above50]
            .sort_values(["VCP_Breakout_Days_Ago", "_rs_sort"], ascending=[True, False])
            .drop(columns="_rs_sort"))


# --- MINERVINI PRO START (rollback-safe helpers) ---
def _series_flag(series, index, default=False):
    """Interpret an optional scanner column as a boolean Series."""
    if series is None:
        return pd.Series(default, index=index)
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    return (series.astype(str).str.strip().str.lower()
            .isin({"true", "1", "1.0", "yes"}).fillna(default))


def _vcp_contraction_stats(series):
    """Parse VCP text like '21→6→5' into (leg count, largest step ratio)."""
    def parse(value):
        try:
            levels = [int(x) for x in re.findall(r"\d+", str(value)) if int(x) > 0]
        except (TypeError, ValueError):
            levels = []
        if len(levels) < 2:
            return 0, np.nan
        return len(levels), max(b / a for a, b in zip(levels, levels[1:]))

    parsed = series.fillna("").astype(str).map(parse)
    return parsed.map(lambda x: x[0]).astype(int), parsed.map(lambda x: x[1])
# --- MINERVINI PRO END ---


ENTRY_PRESETS = {
    "Strict":   dict(rs=80, tt=7, sec=60, ext=12, brk=3, pivot=5),
    "Balanced": dict(rs=80, tt=6, sec=55, ext=15, brk=5, pivot=5),
    "Relaxed":  dict(rs=75, tt=6, sec=50, ext=18, brk=5, pivot=7),
    # --- MINERVINI PRO START (rollback-safe) ---
    "Minervini Pro": dict(rs=80, tt=8, sec=60, ext=12, brk=3, pivot=5, pro=True),
    # --- MINERVINI PRO END ---
}


def _entry_candidates(frame, preset):
    """Quality leaders at a usable entry point, scored on trend, sector, timing and risk."""
    if frame is None or frame.empty:
        return frame
    cfg = ENTRY_PRESETS.get(preset, ENTRY_PRESETS["Balanced"])
    # --- MINERVINI PRO START (rollback-safe) ---
    is_pro = bool(cfg.get("pro", False))
    # --- MINERVINI PRO END ---
    out = frame.copy()
    idx = out.index

    def num(col):
        return pd.to_numeric(out[col], errors="coerce") if col in out.columns else pd.Series(np.nan, index=idx)

    def flag(col):
        if col not in out.columns:
            return pd.Series(False, index=idx)
        series = out[col]
        if pd.api.types.is_bool_dtype(series):
            return series.fillna(False).astype(bool)
        return series.astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes"}).fillna(False)

    # --- MINERVINI PRO START (rollback-safe) ---
    pro_extra = pd.Series(True, index=idx)
    vcp_legs, vcp_step = _vcp_contraction_stats(
        out.get("VCP_Contractions", pd.Series("", index=idx)))
    if is_pro:
        # Hard rules from the X post that can be checked with existing scan data.
        pro_extra &= num("Close") >= 30
        pro_extra &= num("Pct_From_52W_High") >= -25
        pro_extra &= num("Pct_Above_52W_Low") >= 100
        pro_extra &= num("TT_Score") >= 8
        # Prefer the new 3-month slope column when a rescan provides it; until then
        # the existing 1-month Trend Template condition is used.
        if "SMA200_Rising_63D" in out.columns:
            pro_extra &= _series_flag(out["SMA200_Rising_63D"], idx)
        else:
            pro_extra &= flag("TT3_200SMA_up")
        # 52-week high recency is additive: it is only enforced once a rescan
        # provides the column, so today's data file keeps working.
        if "High_52W_Recent_6M" in out.columns:
            pro_extra &= _series_flag(out["High_52W_Recent_6M"], idx)
    # --- MINERVINI PRO END ---

    market_ok = bool(flag("Market_Trend_OK").all()) if "Market_Trend_OK" in out.columns else True
    rs, tt, sec = num("RS_Rating"), num("TT_Score"), num("Sector_Strength")
    above50, pct = num("Pct_Above_50SMA"), num("Pct_To_Pivot")
    vol_min = getattr(m, "BREAKOUT_VOL_X", 1.5)

    # Fresh breakout: dedicated VCP cross when available, otherwise the generic volume breakout.
    vcp_days = num("VCP_Breakout_Days_Ago") if "VCP_Breakout_Days_Ago" in out.columns else pd.Series(np.nan, index=idx)
    gen_days = num("Breakout_Days_Ago")
    vol_x = num("Breakout_Vol_x").fillna(num("VCP_Breakout_Vol_x"))
    vcp_fresh = vcp_days.notna() & (vcp_days <= cfg["brk"]) & (pct < 0) & (vol_x >= vol_min)
    gen_fresh = (gen_days.notna() & (gen_days <= cfg["brk"]) & flag("Vol_Breakout")
                 & (vol_x >= vol_min) & ~(pct.notna() & (pct >= 0)))
    break_days = vcp_days.where(vcp_fresh, gen_days.where(gen_fresh))
    fresh = break_days.notna()

    # At pivot: price still below but within the pivot zone, with quiet/contracting volume.
    dry = (flag("VCP_Setup") | flag("Vol_Dry_Up") | flag("VCP") | flag("VCP_Vol_Contracting"))
    at_pivot = (pct >= 0) & (pct <= cfg["pivot"]) & dry

    quality = (flag("Liquid") & (num("Stage_Num") == 2) & (rs >= cfg["rs"]) & (tt >= cfg["tt"])
               & (sec >= cfg["sec"]) & (above50 > 0) & (above50 <= cfg["ext"]) & flag("RS_Line_Uptrend"))
    keep = quality & (fresh | at_pivot) & market_ok
    # --- MINERVINI PRO START (rollback-safe) ---
    if is_pro:
        keep &= pro_extra
    # --- MINERVINI PRO END ---

    # Transparent 0-100 score: leader quality 60, entry position 20, volume 10, RS momentum 10.
    score = pd.Series(np.select(
        [rs >= 90, rs >= 85, rs >= 80, rs >= 75], [25, 20, 15, 10], default=0), index=idx, dtype=float)
    score += pd.Series(np.select([tt >= 8, tt >= 7, tt >= 6], [20, 15, 10], default=0), index=idx)
    score += pd.Series(np.select([sec >= 80, sec >= 70, sec >= 60, sec >= 50],
                                 [15, 12, 8, 5], default=0), index=idx)

    position = pd.Series(0.0, index=idx)
    position[fresh & (break_days <= 1)] = 20
    position[fresh & (break_days > 1) & (break_days <= 3)] = 17
    position[fresh & (break_days > 3)] = 12
    position[at_pivot & (pct <= 2)] = 20
    position[at_pivot & (pct > 2) & (pct <= 3.5)] = 16
    position[at_pivot & (pct > 3.5)] = 12
    score += position

    vol_score = pd.Series(0.0, index=idx)
    vol_score[fresh & (vol_x >= 2.0)] = 10
    vol_score[fresh & (vol_x >= vol_min) & (vol_x < 2.0)] = 8
    vol_score[fresh & vol_score.eq(0)] = 4
    vol_score[at_pivot & (flag("VCP_Vol_Contracting") | flag("Vol_Dry_Up"))] = 8
    pressure = out.get("Volume_Pressure_20D", pd.Series("", index=idx)).astype(str)
    up_pressure = at_pivot & pressure.str.contains("Up-volume", na=False)
    vol_score[up_pressure] = np.maximum(vol_score[up_pressure], 6)
    score += vol_score

    hits = (flag("RS_Improving").astype(int) + (num("RS_Excess_3M_%") > 0).astype(int)
            + (num("RS_Change") > 0).astype(int))
    score += hits.map({3: 10.0, 2: 6.0, 1: 3.0, 0: 0.0}).fillna(0.0)
    # Extension risk: a stock can pass the hard limit yet still be a poor chase.
    score -= pd.Series(np.select([above50 > 15, above50 > 12, above50 > 9],
                                 [10, 6, 3], default=0), index=idx)

    # --- MINERVINI PRO START (rollback-safe) ---
    # VCP depth is a preference, not a hard filter: the X post calls 3 legs and
    # 50% tightening "ideals", so they add score instead of removing names.
    if is_pro:
        score += pd.Series(np.select([vcp_legs >= 3, vcp_legs == 2], [6, 3], default=0), index=idx)
        score += pd.Series(np.select([vcp_step <= 0.5, vcp_step <= 0.7], [5, 2], default=0), index=idx)
        score += (flag("VCP_Vol_Contracting") | flag("Vol_Dry_Up")).astype(int) * 3
        score += pressure.str.contains("Up-volume", na=False).astype(int) * 2
        score += (num("Green_Days_20D") > num("Red_Days_20D")).astype(int) * 2
    # --- MINERVINI PRO END ---

    close, pivot, sma50 = num("Close"), num("Pivot"), num("SMA50")
    stop = (pivot * 0.92).where(pivot > 0, sma50 * 0.95)
    # --- MINERVINI PRO START (rollback-safe) ---
    # Only the new preset switches to the X-post ATR stop (2 x ATR, max 10%).
    if is_pro and "ATR_Stop_Distance_%" in out.columns:
        atr_stop = close * (1 - num("ATR_Stop_Distance_%") / 100)
        stop = atr_stop.where(atr_stop.notna(), stop)
    # --- MINERVINI PRO END ---
    stop_dist = ((close - stop) / close * 100).where((close > 0) & (stop > 0)).clip(0, 25).round(1)

    reasons = []
    for sym in idx:
        bits = []
        if bool(fresh.loc[sym]):
            label = "VCP breakout" if bool(vcp_fresh.loc[sym]) else "Breakout"
            day = break_days.loc[sym]
            bits.append(f"{label} {int(day)}d ago" if pd.notna(day) else label)
            if pd.notna(vol_x.loc[sym]):
                bits.append(f"{vol_x.loc[sym]:.1f}× vol")
        else:
            gap = pct.loc[sym]
            bits.append(f"{gap:.1f}% to pivot" if pd.notna(gap) else "near pivot")
            if bool(dry.loc[sym]):
                bits.append("dry volume")
        for value, label in ((rs.loc[sym], "RS"), (tt.loc[sym], "TT"), (sec.loc[sym], "Sec")):
            if pd.notna(value):
                bits.append(f"{label} {int(value)}" + ("/8" if label == "TT" else ""))
        # --- MINERVINI PRO START (rollback-safe) ---
        if is_pro:
            bits.append("Minervini Pro")
            if int(vcp_legs.loc[sym]) >= 3:
                bits.append("3 VCP legs")
            if pd.notna(vcp_step.loc[sym]) and float(vcp_step.loc[sym]) <= 0.5:
                bits.append("50% tightening")
        # --- MINERVINI PRO END ---
        reasons.append(" · ".join(bits))

    out["Entry_Score"] = score.round().clip(0, 100).astype(int)
    out["Entry_Type"] = np.select([fresh, at_pivot], ["Fresh breakout", "At pivot"], default="")
    out["Stop_Distance_%"] = stop_dist
    out["Entry_Reason"] = reasons
    return out.loc[keep].sort_values(["Entry_Score", "RS_Rating"], ascending=[False, False])


# --- MASTER LIST START (rollback-safe helper) ---
CONFLUENCE_WEIGHTS = {
    "Top Picks": 12,
    "Momentum Leader": 10,
    "Trend Template": 10,
    "VCP Setup": 12,
    "VCP Breakout": 10,
    "Entry Candidates": 14,
    "Volume Breakout": 8,
    "Stage 1 Bases": 5,
    "RS Blue Dot": 8,
    "Minervini Pro": 13,
}


def _build_confluence_frame(base, sources):
    """One row per symbol, with weighted membership tags and an A/B/C tier."""
    if base is None or base.empty or "Symbol" not in base.columns:
        empty = base.iloc[0:0].copy() if base is not None else pd.DataFrame()
        for col in ("Confluence_Score", "Tier", "Filter_Count", "In_Filters"):
            empty[col] = pd.Series(dtype=object)
        return empty

    tags, weights = {}, {}
    for label, frame, weight in sources:
        if frame is None or frame.empty:
            continue
        if "Symbol" in frame.columns:
            symbols = frame["Symbol"].dropna().astype(str).unique()
        else:
            symbols = pd.Series(frame.index.dropna().astype(str)).unique()
        for sym in symbols:
            tags.setdefault(sym, []).append(label)
            weights[sym] = weights.get(sym, 0) + weight
    if not tags:
        empty = base.iloc[0:0].copy()
        for col in ("Confluence_Score", "Tier", "Filter_Count", "In_Filters"):
            empty[col] = pd.Series(dtype=object)
        return empty

    def num(col):
        return (pd.to_numeric(base[col], errors="coerce") if col in base.columns
                else pd.Series(np.nan, index=base.index))

    def flag(col):
        return _series_flag(base[col], base.index) if col in base.columns else pd.Series(False, index=base.index)

    syms = base["Symbol"].astype(str)
    rs = num("RS_Rating").fillna(0)
    tt = num("TT_Score").fillna(0)
    sec = num("Sector_Strength").fillna(0)
    quality = (rs * 0.25 + (tt / 8) * 20 + sec * 0.10
               + num("Stage_Num").eq(2).astype(int) * 5
               + flag("RS_Line_Uptrend").astype(int) * 5)
    signal = syms.map(weights).fillna(0) * 1.2
    score = (quality + np.minimum(signal, 35)).clip(0, 100).round().astype(int)
    tier = np.select([score >= 85, score >= 70], ["A", "B"], default="C")

    out = base[syms.isin(tags)].drop_duplicates(subset="Symbol", keep="first").copy()
    out_syms = out["Symbol"].astype(str)
    out["Confluence_Score"] = out_syms.map(dict(zip(syms, score))).astype(int)
    out["Tier"] = out_syms.map(dict(zip(syms, tier)))
    out["Filter_Count"] = out_syms.map({k: len(v) for k, v in tags.items()}).astype(int)
    out["In_Filters"] = out_syms.map({k: " · ".join(v) for k, v in tags.items()})
    return out.sort_values(["Confluence_Score", "RS_Rating", "Filter_Count"],
                           ascending=[False, False, False])
# --- MASTER LIST END ---


df = apply_stock_filters(result)
entry_candidates = _entry_candidates(df, st.session_state.get("entry_preset", "Balanced"))

top = df[df.TT_Pass & (df.RS_Rating >= pref_rs) & df.RS_Line_Near_High & (df.RSI14 > rsi_min)]
tt = df[df.TT_Pass]
blue = df[df.RS_Blue_Dot & (df.RS_Rating >= pref_rs)]
vcp = df[df.VCP_Setup].sort_values("Pct_To_Pivot")
brk = df[df.Vol_Breakout].sort_values(["Breakout_Days_Ago", "Breakout_Vol_x"], ascending=[True, False])
s1 = df[df.Stage1_Base].sort_values("Base_Days", ascending=False)

# Momentum Candidates: objective daily fields narrow the universe; chart-only
# checks are shown with the screen so the rule-based output is not mistaken for
# an automatic assessment of subjective price action.
momentum_max_pivot_gap = 10.0
momentum_required = ["Pct_From_52W_High", "Pct_Above_50SMA", "Base_Forming",
                     "Base_Depth_%", "Pct_To_Pivot", "RS_Line_Near_High", "Market_Trend_OK"]
momentum_ready = all(field in df.columns for field in momentum_required)
momentum_market_ok = bool(
    result["Market_Trend_OK"].fillna(False).astype(bool).all()
) if "Market_Trend_OK" in result.columns and not result.empty else False
if momentum_ready:
    momentum_candidates = df[
        (pd.to_numeric(df["Pct_From_52W_High"], errors="coerce") >= -25)
        & (pd.to_numeric(df["Pct_Above_50SMA"], errors="coerce") >= 0)
        & df["Base_Forming"].fillna(False).astype(bool)
        & (pd.to_numeric(df["Base_Depth_%"], errors="coerce") <= 20)
        & (pd.to_numeric(df["Pct_To_Pivot"], errors="coerce") >= 0)
        & (pd.to_numeric(df["Pct_To_Pivot"], errors="coerce") <= momentum_max_pivot_gap)
        & df["RS_Line_Near_High"].fillna(False).astype(bool)
    ].copy()
    if not momentum_market_ok:
        momentum_candidates = momentum_candidates.iloc[0:0]
    momentum_candidates = momentum_candidates.sort_values(
        ["Pct_To_Pivot", "RS_Rating"], ascending=[True, False]
    )
else:
    momentum_candidates = df.iloc[0:0].copy()

# --- MASTER LIST START (rollback-safe: reads existing screens only) ---
master_sources = [
    ("Top Picks", top, CONFLUENCE_WEIGHTS["Top Picks"]),
    ("Momentum Leader", momentum_candidates, CONFLUENCE_WEIGHTS["Momentum Leader"]),
    ("Trend Template", tt, CONFLUENCE_WEIGHTS["Trend Template"]),
    ("VCP Setup", vcp, CONFLUENCE_WEIGHTS["VCP Setup"]),
    ("VCP Breakout", _vcp_breakout_frame(df), CONFLUENCE_WEIGHTS["VCP Breakout"]),
    ("Entry Candidates", entry_candidates, CONFLUENCE_WEIGHTS["Entry Candidates"]),
    ("Volume Breakout", brk, CONFLUENCE_WEIGHTS["Volume Breakout"]),
    ("Stage 1 Bases", s1, CONFLUENCE_WEIGHTS["Stage 1 Bases"]),
    ("RS Blue Dot", blue, CONFLUENCE_WEIGHTS["RS Blue Dot"]),
    ("Minervini Pro", _entry_candidates(df, "Minervini Pro"), CONFLUENCE_WEIGHTS["Minervini Pro"]),
]
master_list = _build_confluence_frame(df, master_sources)
# --- MASTER LIST END ---

# ---------------- KPI cards ----------------
with slot_stats:
    ui.kpis([
        ("Top Picks", len(top), f"RS ≥ {pref_rs} · trend · RS line", ""),
        ("Trend Template", len(tt), "8 rules pass", ""),
        ("VCP Setups", len(vcp), "tight · near pivot", ""),
        ("Volume Breakouts", len(brk), f"last {m.BREAKOUT_RECENT_DAYS} days", ""),
        ("Stage 1 Bases", len(s1), "early setups", ""),
        ("RS Blue Dot", len(blue), "RS line leads", ""),
    ])


def _reset_columns(state_key, defaults):
    st.session_state[state_key] = list(defaults)


def choose_table_columns(frame, defaults, key, label="Visible columns"):
    """Let each result table choose from the columns it can actually render."""
    available = [c for c in frame.columns if c in ui.SPEC]
    default_keys = [c for c in defaults if c in available]
    state_key = f"visible_columns_{key}"
    migration_key = f"daily_change_column_migrated_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_keys
    elif not st.session_state.get(migration_key, False):
        # Add the new default daily-change column to existing sessions while
        # preserving each user's other column selections.
        if "Chg_1D_%" in default_keys and "Chg_1D_%" not in st.session_state[state_key]:
            st.session_state[state_key] = [*st.session_state[state_key], "Chg_1D_%"]
    st.session_state[migration_key] = True
    if not _view_row_columns["used"]:
        _view_row_columns["used"] = True
        column_panel = _popover(v_columns, "Customize columns", icon=":material/view_column:")
    else:  # a second table on the same screen keeps its own expander beside it
        column_panel = st.expander("⚙️ Customize columns", expanded=False)
    with column_panel:
        selected = st.multiselect(
            label,
            available,
            key=state_key,
            help="Search for fields, select the columns you want, and remove chips to hide columns.",
        )
        st.button("Reset default columns", key=f"reset_{state_key}",
                  on_click=_reset_columns, args=(state_key, default_keys))
    return selected


def stock_strength_map(frame, key):
    """Plot current stock results by cross-sectional RS rank and benchmark-relative return."""
    required = ["Symbol", "RS_Rating", "RS_Excess_3M_%"]
    if frame.empty:
        st.info("No stocks match the current filters.")
        return
    missing = [column for column in required if column not in frame.columns]
    if missing:
        st.info("The strength map will be available after the next scan adds its required fields.")
        return

    max_stocks = min(250, len(frame))
    limit = max_stocks
    if max_stocks > 25:
        limit = st.slider("Stocks to plot · highest RS first", 25, max_stocks,
                          min(100, max_stocks), key=f"map_limit_{key}")
    chart_data = frame.sort_values("RS_Rating", ascending=False).head(limit).copy()
    chart_data["RS_Rating"] = pd.to_numeric(chart_data["RS_Rating"], errors="coerce")
    chart_data["RS_Excess_3M_%"] = pd.to_numeric(chart_data["RS_Excess_3M_%"], errors="coerce")
    if "Vol_x_50d" in chart_data:
        chart_data["Chart_Volume"] = pd.to_numeric(chart_data["Vol_x_50d"], errors="coerce").fillna(1).clip(.5, 5)
    else:
        chart_data["Chart_Volume"] = 1.0
    if "Trend_State" not in chart_data:
        chart_data["Trend_State"] = "Mixed"
    chart_data = chart_data.dropna(subset=["RS_Rating", "RS_Excess_3M_%"])
    if chart_data.empty:
        st.info("The selected rows do not have enough RS data to plot.")
        return

    x_extent = max(1.0, float(chart_data["RS_Excess_3M_%"].abs().max())) * 1.08
    points = alt.Chart(chart_data).mark_circle(opacity=.82, stroke="white", strokeWidth=.5).encode(
        x=alt.X("RS_Excess_3M_%:Q", title="RS vs benchmark · 3M (%)",
                scale=alt.Scale(domain=[-x_extent, x_extent], nice=False)),
        y=alt.Y("RS_Rating:Q", title="RS Rating · rank within scan", scale=alt.Scale(domain=[1, 99])),
        size=alt.Size("Chart_Volume:Q", title="Today’s volume / 50-day avg",
                      scale=alt.Scale(range=[30, 400]), legend=None),
        color=alt.Color("Trend_State:N", title="Trend",
                        scale=alt.Scale(
                            domain=["Strong trend", "Developing", "Mixed", "Weakening"],
                            range=["#16a36a", "#3b82f6", "#9299a6", "#dc4c5a"],
                        )),
        tooltip=[
            alt.Tooltip("Symbol:N", title="Symbol"),
            alt.Tooltip("Company Name:N", title="Company") if "Company Name" in chart_data else alt.Tooltip("Symbol:N", title="Company"),
            alt.Tooltip("RS_Rating:Q", title="RS Rating", format=".0f"),
            alt.Tooltip("RS_Excess_3M_%:Q", title="RS vs benchmark · 3M (%)", format="+.1f"),
            alt.Tooltip("Trend_State:N", title="Trend"),
            alt.Tooltip("Stage:N", title="Stage") if "Stage" in chart_data else alt.Tooltip("Trend_State:N", title="Trend"),
            alt.Tooltip("Chart_Volume:Q", title="Volume / 50-day avg", format=".1f×"),
        ],
    )
    label_data = chart_data.nlargest(min(6, len(chart_data)), "RS_Rating")
    labels = alt.Chart(label_data).mark_text(dy=-10, fontSize=10, fontWeight=600).encode(
        x=alt.X("RS_Excess_3M_%:Q", scale=alt.Scale(domain=[-x_extent, x_extent], nice=False)),
        y=alt.Y("RS_Rating:Q", scale=alt.Scale(domain=[1, 99])),
        text=alt.Text("Symbol:N"),
        color=alt.Color("Trend_State:N", scale=alt.Scale(
            domain=["Strong trend", "Developing", "Mixed", "Weakening"],
            range=["#16a36a", "#3b82f6", "#9299a6", "#dc4c5a"],
        ), legend=None),
    )
    zero_line = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(
        color="#8b93a1", strokeDash=[5, 4], opacity=.75
    ).encode(x="x:Q")
    rs_line = alt.Chart(pd.DataFrame({"y": [70]})).mark_rule(
        color="#8b93a1", strokeDash=[5, 4], opacity=.75
    ).encode(y="y:Q")
    chart = (points + labels + zero_line + rs_line).properties(height=440).configure_view(
        stroke=None
    ).configure_axis(grid=True, labelFontSize=11, titleFontSize=12)
    st.altair_chart(chart, use_container_width=True)
    st.caption("Each bubble is a stock. Positive horizontal values mean outperformance versus the scan’s "
               "benchmark; vertical position is the scanner’s separate 1–99 RS Rating. Bubble size reflects "
               "today’s volume relative to its 50-day average. Hover or tap a bubble for details.")


def show(frame, name, text, keys=None, sort=("RS_Rating", -1), titles=None, scan_date=None,
         history_dates=None, history_key=None):
    _set_view_note(text, len(frame))
    if custom_rules:
        rule_labels = []
        for field, operator, lower_or_value, upper in custom_rules:
            label = ui.SPEC[field]["t"]
            rule_labels.append(
                f"{label} {lower_or_value:g}–{upper:g}" if operator == "Between"
                else f"{label} {'≥' if operator == 'At least' else '≤'} {lower_or_value:g}"
            )
        st.caption("Custom conditions (AND): " + " · ".join(rule_labels))
    with v_view:
        view = st.segmented_control("View", ["List", "Strength map"], default="List",
                                    key=f"result_view_{name}", label_visibility="collapsed")
    if view == "Strength map":
        stock_strength_map(frame, name)
    else:
        defaults = list(keys or ui.COLS_DEFAULT)
        visible = choose_table_columns(frame, defaults, name)
        if visible:
            ui.table(frame, visible, sort, font, density, titles=titles,
                     search_keys=["Symbol", "Company Name"], market_context=market_context)
        else:
            st.info("Select at least one column to display this table.")
    if history_dates:
        selected_date = st.selectbox(
            "As of scan date",
            history_dates,
            index=history_dates.index(scan_date) if scan_date in history_dates else 0,
            key=history_key,
            format_func=lambda value: f"Scan ({datetime.fromisoformat(value).strftime('%a, %d %b %Y')})",
            help="History is retained for the most recent 30 calendar days. The Filters are applied to the selected scan.",
        )
        st.caption(f"Results above use the {selected_date} scan. Header metrics still show the latest scan.")
    if not frame.empty:
        st.download_button("⬇️ Download CSV", frame.to_csv(index=False).encode("utf-8"),
                           file_name=f"totalmarket_{name}_{scan_date or as_of.date()}.csv", mime="text/csv",
                           key=f"dl_{name}")


def select_setup_scan(screen_key):
    """Choose the stored date from session state and load its snapshot."""
    state_key = f"setup_scan_date_{screen_key}"
    try:
        refresh_token = st.session_state.get("data_refresh_token", "initial")
        scans = load_scan_history_index(refresh_token)
    except Exception as error:
        st.warning(f"Could not load scan history ({error}). Showing the latest scan instead.")
        return df, None, [], state_key

    dates = [str(item.get("date", "")) for item in scans if item.get("date")]
    if not dates:
        st.info("No archived scans yet. A date selector will appear after the next successful Daily scan; showing the latest scan for now.")
        return df, None, [], state_key
    selected_date = st.session_state.get(state_key, dates[0])
    if selected_date not in dates:
        selected_date = dates[0]
        st.session_state[state_key] = selected_date
    try:
        snapshot = load_scan_history(selected_date, refresh_token)
        return apply_stock_filters(snapshot), selected_date, dates, state_key
    except Exception as error:
        st.error(f"Could not load the {selected_date} scan ({error}). Showing the latest scan instead.")
        return df, None, [], state_key


def rotation_chart(rotation, group_title):
    """Quadrant map of group-level relative strength and the share of members improving."""
    rotation = rotation.copy()
    # Keep the quadrant definitions tied to the two plotted axes.
    rotation["Quadrant"] = np.select(
        [
            (rotation["Median_RS_3M"] >= 0) & (rotation["Improving_Pct"] >= 50),
            (rotation["Median_RS_3M"] < 0) & (rotation["Improving_Pct"] >= 50),
            (rotation["Median_RS_3M"] >= 0) & (rotation["Improving_Pct"] < 50),
        ],
        ["Leading", "Improving", "Weakening"],
        default="Lagging",
    )
    colors = alt.Scale(
        domain=["Leading", "Improving", "Weakening", "Lagging"],
        range=["#16a36a", "#3b82f6", "#e6a323", "#dc4c5a"],
    )
    x_extent = max(1.0, float(rotation["Median_RS_3M"].abs().max())) * 1.08
    x_enc = alt.X(
        "Median_RS_3M:Q",
        title="Median RS vs benchmark · 3M (%)",
        scale=alt.Scale(domain=[-x_extent, x_extent], nice=False),
    )
    y_enc = alt.Y(
        "Improving_Pct:Q",
        title="Members with improving RS (%)",
        scale=alt.Scale(domain=[0, 100]),
    )
    points = alt.Chart(rotation).mark_circle(opacity=0.88, stroke="white", strokeWidth=0.6).encode(
        x=x_enc,
        y=y_enc,
        size=alt.Size("Stocks:Q", title="Liquid stocks", scale=alt.Scale(range=[100, 850]),
                       legend=None),
        color=alt.Color("Quadrant:N", title="Rotation", scale=colors,
                        legend=alt.Legend(orient="top", direction="horizontal")),
        tooltip=[
            alt.Tooltip("Group:N", title=group_title),
            alt.Tooltip("Quadrant:N", title="Quadrant"),
            alt.Tooltip("Median_RS_3M:Q", title="Median 3M RS vs benchmark (%)", format=".1f"),
            alt.Tooltip("Improving_Pct:Q", title="Members with improving RS (%)", format=".0f"),
            alt.Tooltip("Stocks:Q", title="Liquid stocks", format=".0f"),
        ],
    )
    label_rows = pd.concat(
        [g.sort_values("Median_RS_3M", ascending=False).head(2)
         for _, g in rotation.groupby("Quadrant")],
        ignore_index=True,
    )
    labels = alt.Chart(label_rows).mark_text(dy=-11, fontSize=10, fontWeight=600, limit=115).encode(
        x=x_enc, y=y_enc, text=alt.Text("Group:N"),
        color=alt.Color("Quadrant:N", scale=colors, legend=None),
    )
    vertical = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(
        color="#8b93a1", strokeDash=[5, 4], opacity=0.8
    ).encode(x="x:Q")
    horizontal = alt.Chart(pd.DataFrame({"y": [50]})).mark_rule(
        color="#8b93a1", strokeDash=[5, 4], opacity=0.8
    ).encode(y="y:Q")
    chart = (points + labels + vertical + horizontal).properties(height=420).configure_view(
        stroke=None
    ).configure_axis(grid=True, labelFontSize=11, titleFontSize=12)
    st.altair_chart(chart, use_container_width=True)
    return rotation


def show_breadth_and_sectors():
    b = m.market_breadth(result)
    _set_view_note(f"Every figure on this tab uses <b>liquid stocks only</b> ({LIQ_TEXT}): "
                   f"<b>{b['stocks']}</b> of {len(result)} rated stocks. Stock filters don't apply here.",
                   count=b["stocks"], count_text=f"{b['stocks']} liquid stocks analysed")
    ui.adv_dec(b["advancers"], b["decliners"], b["unchanged"])
    ui.kpis([
        ("52-week highs", b["new_52w_highs"], "closing basis", "#10b981"),
        ("52-week lows", b["new_52w_lows"], "closing basis", "#ef4444"),
        ("RS line at high", f"{b['pct_rsline_high']:.0f}%", "of liquid stocks", "#ec4899"),
        ("RS ≥ 80", f"{b['pct_rs80']:.0f}%", "market leaders", "#6366f1"),
    ])
    ui.meters([
        ("Above 50-day SMA", b["pct_above_50"], "short-term trend"),
        ("Above 150-day SMA", b["pct_above_150"], "intermediate trend"),
        ("Above 200-day SMA", b["pct_above_200"], "long-term trend"),
        ("Stage 2 · Advancing", b["pct_stage2"], "price above a rising 30-week average"),
        ("Pass Trend Template", b["pct_tt"], "all 8 Minervini conditions"),
    ])

    st.markdown("#### Sector strength")
    min_n = st.slider("Minimum liquid stocks per sector", 1, 10, 3,
                      help="Small groups give noisy scores, so they are hidden below this size.")
    groups = m.sector_strength(result, min_stocks=min_n)
    if groups.empty:
        st.info("No sectors meet the minimum size.")
        return
    liquid_groups = result[result["Liquid"] & result["Sector"].notna()].copy()
    rotation = (liquid_groups.groupby("Sector").agg(
        Median_RS_3M=("RS_Excess_3M_%", "median"),
        Improving_Pct=("RS_Improving", "mean"),
        Stocks=("Symbol", "size"),
    ).reset_index().rename(columns={"Sector": "Group"}))
    rotation["Improving_Pct"] = rotation["Improving_Pct"] * 100
    rotation = rotation[rotation["Stocks"] >= min_n].dropna(
        subset=["Median_RS_3M", "Improving_Pct"]
    )
    if not rotation.empty:
        st.markdown("#### Sector rotation map")
        ui.note("Each bubble is a group; larger bubbles contain more liquid stocks. The horizontal axis is "
                "median 3-month RS versus the benchmark. The vertical axis is the share of group members "
                "whose RS improved versus the prior 3-month period. This scanner-derived rotation map is "
                "not a classic index-based RRG chart.")
        rotation = rotation_chart(rotation, "Sector")
        quadrant_counts = rotation["Quadrant"].value_counts()
        ui.kpis([
            ("Leading", int(quadrant_counts.get("Leading", 0)), "positive RS · most members improving", "#16a36a"),
            ("Improving", int(quadrant_counts.get("Improving", 0)), "negative RS · most members improving", "#3b82f6"),
            ("Weakening", int(quadrant_counts.get("Weakening", 0)), "positive RS · fewer members improving", "#e6a323"),
            ("Lagging", int(quadrant_counts.get("Lagging", 0)), "negative RS · fewer members improving", "#dc4c5a"),
        ])
    ui.note(f"<b>{len(groups)}</b> sectors · Ranked by a blend of <b>median RS Rating (50%)</b>, "
            f"<b>share of stocks with RS ≥ 80 (25%)</b> "
            f"and <b>share passing the Trend Template (25%)</b>.")
    group_columns = choose_table_columns(groups, ui.COLS_SECTOR_STRENGTH, "sector_strength",
                                        label="Visible sector columns")
    if group_columns:
        ui.table(groups, group_columns, ("Rank", 1), font, density, titles={"Group": "Sector"},
                 search_keys=["Group"], search_label="Search sector")
    else:
        st.info("Select at least one column to display the sector table.")
    st.download_button("⬇️ Download CSV", groups.to_csv(index=False).encode("utf-8"),
                       file_name=f"totalmarket_sector_strength_{as_of.date()}.csv",
                       mime="text/csv", key="dl_group_table")
    st.markdown("#### Stocks in a sector")
    pick = st.selectbox("Choose a sector (listed by strength)", groups["Group"].tolist())
    members = result[(result["Sector"] == pick) & result["Liquid"]].sort_values(
        "RS_Rating", ascending=False)
    show(members, "sector_stocks", f"Liquid stocks in <b>{pick}</b>, sorted by RS Rating.")


def _fmt_price(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def chart_base_history(history: pd.DataFrame) -> pd.DataFrame:
    """Find completed base breakouts plus the current forming base (chart session only).

    A base starts at its left-side peak and the pivot is that peak's high. It is complete when
    price closes above the pivot within 20 sessions of the base window; it has failed when a
    later close is 8% under the pivot or below the 50-day average. Rows are newest first and
    numbered oldest first (B1 = oldest) so the numbers match the circles drawn on the chart.
    """
    frame = history.dropna(subset=["High", "Low", "Close", "Volume"]).copy()
    n = len(frame)
    if n < 55:
        return pd.DataFrame()
    highs, lows = frame["High"].to_numpy(), frame["Low"].to_numpy()
    closes, volumes = frame["Close"].to_numpy(), frame["Volume"].to_numpy()
    sma50 = pd.Series(closes).rolling(50, min_periods=50).mean().to_numpy()
    dates = frame.index
    earliest = max(0, n - 252)
    candidates = []
    for end in range(max(29, earliest), n - 1):
        for length in (15, 20, 30, 45, 60, 90, 120, 150):
            start = end - length + 1
            if start < 0:
                continue
            peak = start + int(np.argmax(highs[start:end + 1]))
            span = end - peak + 1
            if span < 15:                      # need at least ~3 weeks after the peak
                continue
            pivot = float(highs[peak])
            low = float(lows[peak:end + 1].min())
            depth = (pivot - low) / pivot if pivot > 0 else 1
            if depth < .08 or depth > (.20 if span < 25 else .35):
                continue
            if np.isfinite(sma50[peak]) and closes[peak] < sma50[peak]:
                continue                       # a base must start from strength, not a downtrend
            if abs(closes[end] / closes[peak] - 1) > .15:
                continue
            after = next((j for j in range(end + 1, min(n, end + 21)) if closes[j] > pivot), None)
            if after is None or n - 1 - after > 252:
                continue
            if np.isfinite(sma50[after]) and closes[after] < sma50[after]:
                continue
            candidates.append({"start_i": peak, "end_i": end, "breakout_i": after, "span": span,
                               "depth": depth * 100, "pivot": pivot, "low": low})
    # Several windows describe the same base: keep the longest one per breakout cluster.
    candidates.sort(key=lambda item: (item["breakout_i"], item["span"]), reverse=True)
    distinct = []
    for item in candidates:
        if any(abs(item["breakout_i"] - old["breakout_i"]) < 15
               or (item["start_i"] < old["breakout_i"] and item["breakout_i"] > old["start_i"])
               for old in distinct):
            continue
        distinct.append(item)
        if len(distinct) == 5:
            break

    bases = []
    for item in distinct:
        b, pivot = item["breakout_i"], item["pivot"]
        avg_vol = float(np.nanmean(volumes[max(0, b - 50):b])) if b > 0 else 0.0
        vol_x = float(volumes[b] / avg_vol) if avg_vol > 0 else float("nan")
        fail = next((j for j in range(b + 1, n)
                     if closes[j] < pivot * .92 or (np.isfinite(sma50[j]) and closes[j] < sma50[j])), None)
        stop = fail if fail is not None else n - 1
        best_i = b + int(np.argmax(highs[b:stop + 1]))
        best_px = float(highs[best_i])
        best = (best_px / pivot - 1) * 100
        now = float(closes[-1] / pivot - 1) * 100
        line = pivot * .92
        if fail is not None:
            close_f = float(closes[fail])
            tests = []
            if close_f < line:
                tests.append(f"below the 8%-under-pivot level ({_fmt_price(line)})")
            if np.isfinite(sma50[fail]) and close_f < sma50[fail]:
                tests.append(f"below its 50-day average ({_fmt_price(float(sma50[fail]))})")
            then, status = f"Failed {dates[fail]:%d %b %y} · best {best:+.1f}% first", "Failed"
            reason = [
                f"On {dates[fail]:%d %b %y} the stock closed at {_fmt_price(close_f)}, " + " and ".join(tests) + ". "
                "That is the first close after the breakout that broke either rule, so the base is marked Failed.",
                f"Best = the highest price after the breakout and before it failed: {_fmt_price(best_px)} on "
                f"{dates[best_i]:%d %b %y}, which is {best:+.1f}% above the pivot ({_fmt_price(pivot)}).",
                f"To check by hand: open {dates[fail]:%d %b %y} on the chart and compare that day's close with the "
                "blue 50-day line and with the level 8% under the pivot."]
        else:
            close_l, sma_l = float(closes[-1]), float(sma50[-1])
            levels = f"the 8%-under-pivot level ({_fmt_price(line)})"
            if np.isfinite(sma_l):
                levels += f" and its 50-day average ({_fmt_price(sma_l)})"
            then, status = f"Holding · best {best:+.1f}% · now {now:+.1f}%", "Holding"
            reason = [
                f"The latest close ({_fmt_price(close_l)} on {dates[-1]:%d %b %y}) is still above {levels}, so the "
                "breakout has not failed.",
                f"Best so far: {_fmt_price(best_px)} on {dates[best_i]:%d %b %y} ({best:+.1f}% vs the pivot "
                f"{_fmt_price(pivot)}). Now: {now:+.1f}% vs the pivot.",
                "It turns Failed on the first close below either level."]
        bases.append({**item, "forming": False, "vol_x": vol_x, "then": then, "status": status,
                      "best": best, "now": now, "breakout": f"{dates[b]:%d %b %y}", "reason": reason,
                      "volume": f"{vol_x:.1f}×" if np.isfinite(vol_x) else "—"})

    # Current base: the highest high since the last breakout, if price has pulled back from it.
    first = max([x["breakout_i"] for x in bases] + [n - 150]) + 1 if bases else max(0, n - 150)
    first = max(0, min(first, n - 16))
    peak = first + int(np.argmax(highs[first:]))
    span = n - peak
    if span >= 15:
        pivot = float(highs[peak])
        low = float(lows[peak:].min())
        depth = (pivot - low) / pivot * 100 if pivot > 0 else 0
        under = (pivot - closes[-1]) / pivot * 100
        if 8 <= depth <= 35 and under > 0:
            bases.append({"start_i": peak, "end_i": n - 1, "breakout_i": None, "span": span,
                          "depth": depth, "pivot": pivot, "low": low, "forming": True,
                          "then": f"Forming · {under:.1f}% under pivot", "status": "Forming",
                          "best": 0.0, "now": -under, "breakout": "–", "volume": "–",
                          "reason": [f"No close above the pivot ({_fmt_price(pivot)}) yet. The latest close is "
                                     f"{_fmt_price(float(closes[-1]))}, which is {under:.1f}% under it.",
                                     f"It counts as a breakout on a close above {_fmt_price(pivot)}. The base low so far is "
                                     f"{_fmt_price(low)} ({depth:.0f}% deep)."]})

    bases.sort(key=lambda item: item["start_i"])
    rows = []
    for number, item in enumerate(bases, 1):
        stop_i = item["breakout_i"] if item["breakout_i"] is not None else n - 1
        rows.append({
            "Base": f"B{number}", "Started": f"{dates[item['start_i']]:%d %b %y}",
            "Length": f"{max(1, round(item['span'] / 5))} wk", "Depth": f"{item['depth']:.0f}%",
            "Pivot": _fmt_price(item["pivot"]), "Breakout": item["breakout"], "Volume": item["volume"],
            "Then": item["then"],
            "_n": number, "_start": f"{dates[item['start_i']]:%Y-%m-%d}",
            "_end": f"{dates[stop_i]:%Y-%m-%d}", "_forming": bool(item["forming"]),
            "_breakout": "" if item["breakout_i"] is None else f"{dates[item['breakout_i']]:%Y-%m-%d}",
            "_pivot": float(item["pivot"]), "_low": float(item["low"]),
            "_status": item["status"], "_best": float(item["best"]), "_now": float(item["now"]),
            "_reason": list(item.get("reason", [])),
        })
    return pd.DataFrame(rows[::-1])


def fetch_chart_payload(symbol: str, period: str) -> dict:
    """Fetch and calculate chart-only data in memory; no disk or repository writes."""
    history = load_chart_history(symbol, period)
    relative = history["Close"] / history["Benchmark_Close"].replace(0, np.nan)
    relative = relative / relative.dropna().iloc[0] * 100 if relative.notna().any() else relative
    base_history = chart_base_history(history)
    return {
        "symbol": symbol, "period": period,
        "benchmark": history.attrs.get("benchmark", "Unavailable"),
        "bars": [{
            "date": day.strftime("%Y-%m-%d"),
            "timestamp": int(pd.Timestamp(day).tz_localize(IST).timestamp() * 1000),
            "open": float(row.Open), "high": float(row.High), "low": float(row.Low),
            "close": float(row.Close), "volume": int(row.Volume) if pd.notna(row.Volume) else 0,
            "rs": float(relative.loc[day]) if pd.notna(relative.loc[day]) else None,
        } for day, row in history.iterrows()],
        "dates": [day.strftime("%Y-%m-%d") for day in history.index],
        "base_history": base_history.to_dict("records"),
    }


def _clear_chart_request() -> None:
    st.session_state.pop("_symbol_chart_request", None)
    st.session_state.pop("symbol_chart_dialog_data", None)


_DIALOG_HAS_DISMISS = True


def _md_escape(text: str) -> str:
    return re.sub(r"([\\`*_\[\]<>#|~$])", r"\\\1", str(text))


def _dialog_title(symbol: str) -> str:
    """Title row text: SYMBOL  Company name."""
    symbol = str(symbol).strip().upper()
    parts = [f"**{_md_escape(symbol)}**"]
    match = result[result["Symbol"].astype(str) == symbol]
    if not match.empty:
        company = str(match.iloc[0].get("Company Name", "") or "")
        if company and company.lower() != "nan":
            parts.append(_md_escape(company))
    return "  ".join(parts)


_DIALOG_CSS = """<style>
[data-testid="stDialog"] section[role="dialog"] h2{padding:8px 56px 0 20px;min-height:0}
[data-testid="stDialog"] section[role="dialog"] h2 p{font-size:.88rem;font-weight:500;line-height:1.35;opacity:.85}
[data-testid="stDialog"] section[role="dialog"] h2 p strong{font-family:Georgia,"Times New Roman",serif;font-size:1.3rem;font-weight:800;letter-spacing:.01em;margin-right:6px}
[data-testid="stDialog"] section[role="dialog"] h2 span{margin-right:0}
[data-testid="stDialog"] section[role="dialog"] > button{z-index:20;top:10px}
[data-testid="stDialog"] section[role="dialog"] > div:last-child{padding:4px 20px 16px}
[data-testid="stDialog"] [data-testid="stVerticalBlock"]{gap:.4rem}
[data-testid="stDialog"] [data-testid="stElementContainer"]:has(.mp-dcss){display:none}
@media(max-width:640px){[data-testid="stDialog"] section[role="dialog"] > div:last-child{padding:4px 10px 12px}}
</style><span class="mp-dcss"></span>"""


_BASE_TABLE_CSS = """<style>
.mp-bt{border:1px solid var(--mp-line);border-radius:10px;padding:8px 12px 8px;margin-bottom:16px;color:var(--mp-text)}
.mp-bt h4{margin:0 0 4px;font-size:.94rem;font-weight:800;line-height:1.3;padding:0;color:var(--mp-text)}
.mp-bt h4 small{font-weight:700;opacity:1;color:var(--mp-muted);margin-left:6px;font-size:.76rem}
.mp-bt table{width:100%;border-collapse:collapse;font-size:.83rem;line-height:1.2;border:0;margin:0}
.mp-bt th,.mp-bt td{border-left:0;border-right:0;background:transparent;color:var(--mp-text)}
.mp-bt th{border-top:0;border-bottom:1px solid var(--mp-line);font-weight:800;text-align:right;
padding:3px 8px;font-size:.76rem;white-space:nowrap;opacity:1}
.mp-bt td{padding:4px 8px;text-align:right;border-top:1px solid var(--mp-line);white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:600}
.mp-bt tbody tr:first-child td{border-top:0}
.mp-bt th:first-child,.mp-bt td:first-child{text-align:left;font-weight:800}
.mp-bt th:last-child,.mp-bt td:last-child{text-align:left;white-space:normal}
.mp-bt .i{position:relative;display:inline-block;width:13px;height:13px;margin-left:4px;border:1px solid var(--mp-line);
border-radius:50%;font:italic 800 9px/11px Georgia,serif;text-align:center;vertical-align:1px;cursor:pointer;outline:0;opacity:1;color:var(--mp-accent)}
.mp-bt .i:hover,.mp-bt .i:focus{opacity:1;background:var(--mp-surface2)}
.mp-bt .tip{display:none;position:absolute;top:calc(100% + 7px);left:50%;transform:translateX(-50%);width:232px;padding:7px 9px;border-radius:8px;
background:#1f2937;color:#f3f4f6;font:400 .72rem/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;font-style:normal;text-align:left;white-space:normal;
z-index:60;box-shadow:0 6px 18px rgba(0,0,0,.3);cursor:default}
.mp-bt .i:hover .tip,.mp-bt .i:focus .tip{display:block}
.mp-bt th:first-child .tip{left:-6px;transform:none}
.mp-bt td{position:relative}
.mp-bt .tip.wide{width:min(330px,86vw);left:auto;right:-6px;transform:none;top:auto;bottom:calc(100% + 7px)}
.mp-bt .tip .ln{display:block;margin-top:5px}.mp-bt .tip b{display:block;font-size:.76rem;color:#fff}
.mp-bt th:last-child .tip{left:auto;right:-6px;transform:none}
.mp-bt .fail{color:var(--mp-bad);font-weight:800}.mp-bt .form{color:var(--mp-accent);font-weight:800}.mp-bt .hold{color:var(--mp-good);font-weight:800}
.mp-bt .vcpnote{margin:0 0 8px;padding:7px 10px;border-left:3px solid var(--mp-accent);border-radius:6px;
background:var(--mp-surface2);color:var(--mp-text);font-size:.78rem;font-weight:600;line-height:1.4}
.mp-bt .vcpnote b{color:var(--mp-accent);font-weight:800}
.mp-bt .note{margin:6px 0 0;font-size:.74rem;opacity:1;line-height:1.4;color:var(--mp-text);font-weight:600}
.mp-bt .note b{color:var(--mp-text);font-weight:800}
.mp-bt .mob{display:none}
@media(max-width:640px){
 .mp-bt thead{display:none}.mp-bt table,.mp-bt tbody{display:block}
 .mp-bt tr{display:grid;grid-template-columns:repeat(4,1fr);gap:1px 8px;padding:5px 0;border-top:1px solid var(--mp-line)}
 .mp-bt tbody tr:first-child{border-top:0}
 .mp-bt td{display:block;border:0 !important;padding:0;text-align:left;white-space:normal;font-size:.76rem;line-height:1.2}
 .mp-bt td::before{content:attr(data-l);display:block;font-size:.6rem;font-weight:800;opacity:1;color:var(--mp-muted);line-height:1.05}
 .mp-bt td:first-child::before{content:none}.mp-bt td:first-child{font-size:.95rem;align-self:end}
 .mp-bt td:last-child{grid-column:1/-1}
 .mp-bt .mob{display:block}
 .mp-bt td:last-child .i{position:static}
 .mp-bt td:last-child .tip.wide{left:0;right:0;width:auto;top:auto;bottom:auto;margin-top:6px}
}
</style>"""


def _base_table_html(records, vcp_pivot=None, vcp_contractions="") -> str:
    """The 'Base history' card: one row per base, newest first (numbers match the chart circles)."""
    rows = []
    for r in records:
        if not r.get("Base"):
            continue
        then = _esc(str(r["Then"]))
        word, _, rest = then.partition(" ")
        cls = {"Failed": "fail", "Forming": "form", "Holding": "hold"}.get(word, "")
        then_html = f'<span class="{cls}">{word}</span> {rest}' if cls else then
        lines = "".join(f'<span class="ln">{_esc(str(x))}</span>' for x in (r.get("_reason") or []))
        if lines:
            then_html += (f' <span class="i" tabindex="0">i<span class="tip wide"><b>Why {_esc(word)}?</b>{lines}</span></span>')
        rows.append(
            f'<tr><td data-l="Base">{_esc(str(r["Base"]))}</td><td data-l="Started">{_esc(str(r["Started"]))}</td>'
            f'<td data-l="Length">{_esc(str(r["Length"]))}</td><td data-l="Depth">{_esc(str(r["Depth"]))}</td>'
            f'<td data-l="Base pivot">{_esc(str(r["Pivot"]))}</td><td data-l="Breakout">{_esc(str(r["Breakout"]))}</td>'
            f'<td data-l="Volume">{_esc(str(r["Volume"]))}</td><td data-l="Then">{then_html}</td></tr>')
    if not rows:
        return ""
    def tip(text: str, first: bool = False) -> str:
        return f'<span class="i" tabindex="0">i<span class="tip">{text}</span></span>'

    head = ('<thead><tr><th>Base' + tip("A pause in the uptrend before the next advance. B-numbers match the circles on the chart "
                                        "(B1 is the oldest). Started is the date of the base's left-side high.") + '</th>'
            '<th>Started</th><th>Length</th><th>Depth</th>'
            '<th>Base pivot' + tip("The base history's highest price and buy point. A close above it is the breakout. "
                                   "This is separate from the VCP pivot shown in the chart header and VCP screen: the "
                                   "VCP pivot is the high of the last tightening leg and can be lower.") + '</th>'
            '<th>Breakout</th>'
            '<th>Volume' + tip("Breakout-day volume divided by the 50-day average volume (2.0× means twice the usual volume). "
                               "Strong breakouts are usually 1.5× or more; below 1× lacked volume support.") + '</th>'
            '<th>Then' + tip("What happened after the breakout. Click the i on a row for the exact reason and the numbers to check on the chart.") + '</th></tr></thead>')
    vcp_note = ""
    if vcp_pivot is not None:
        legs = f" · pullbacks {_esc(str(vcp_contractions))}" if vcp_contractions else ""
        vcp_note = (f'<p class="vcpnote"><b>VCP pivot {_fmt_price(float(vcp_pivot))}{legs}</b> '
                    'is from the VCP scan’s last tightening leg. The <b>Base pivot</b> column below is the broader '
                    'chart base high. They are different measurements, so both are shown separately.</p>')
    return (_BASE_TABLE_CSS + '<div class="mp-bt"><h4>Base history<small>last 12 months · newest first</small></h4>'
            + vcp_note +
            f'<table>{head}<tbody>{"".join(rows)}</tbody></table>'
            '<p class="note mob">Base pivot = the base high (the breakout level). Volume = breakout-day volume vs its 50-day average.</p>'
            '<p class="note"><b>Forming</b> = no close above the base pivot yet. <b>Holding</b> = since the breakout, price has not closed '
            '8% under the base pivot or below its 50-day average. <b>Failed</b> = it did, on the date shown (the first such close). '
            '<b>Best</b> = the highest price after the breakout (before any failure) vs the base pivot. Click the i beside a result '
            'for the exact numbers. Bases follow the chart\'s Bases indicator. History, not a forecast.</p></div>')



def _num(row, key, default=None):
    """Read a numeric field from a scan row, returning `default` for missing / NaN values."""
    try:
        value = float(row.get(key))
    except (TypeError, ValueError):
        return default
    return default if value != value else value


def _chart_info(symbol, row, bars, benchmark) -> dict:
    """Header details for the chart (symbol, price, RS, stage, sector, RS-line changes)."""
    latest = bars[-1]
    prior = bars[-2]["close"] if len(bars) > 1 else latest["close"]
    info = {"symbol": symbol, "company": "", "sector": "", "sectorBadge": "",
            "price": latest["close"], "change": (latest["close"] / prior - 1) * 100 if prior else 0.0,
            "asOf": latest["date"], "rs": None, "rsChange": 0, "stage": "",
            "ttScore": None, "ttPass": False, "sectorStrength": None,
            "vcpPivot": None, "vcpContractions": "",
            "benchmark": {"^CRSLDX": "Nifty 500", "^NSEI": "Nifty 50"}.get(benchmark, "index")}
    if row is not None:
        company, sector = str(row.get("Company Name", "") or ""), str(row.get("Sector", "") or "")
        info["company"] = "" if company == "nan" else company
        info["sector"] = "" if sector == "nan" else sector
        rank, strength = _num(row, "Sector_Rank"), _num(row, "Sector_Strength")
        if rank is not None:
            info["sectorBadge"] = f"Sector #{int(rank)}"
        info["sectorStrength"] = None if strength is None else int(strength)
        rs, change = _num(row, "RS_Rating"), _num(row, "RS_Change", 0)
        info["rs"] = None if rs is None else int(rs)
        info["rsChange"] = int(change or 0)
        tt_score, tt_pass = _num(row, "TT_Score"), bool(row.get("TT_Pass", False))
        info["ttScore"] = None if tt_score is None else int(tt_score)
        info["ttPass"] = tt_pass
        stage = str(row.get("Stage", "") or "")
        info["stage"] = "" if stage == "nan" else stage
        vcp_flag = str(row.get("VCP", False)).strip().lower() in {"true", "1", "yes"}
        if vcp_flag:
            vcp_pivot = _num(row, "Pivot")
            info["vcpPivot"] = None if vcp_pivot is None else round(vcp_pivot, 2)
            contractions = str(row.get("VCP_Contractions", "") or "")
            info["vcpContractions"] = "" if contractions == "nan" else contractions
    series = [b["rs"] for b in bars]
    periods = []
    # Shortest first so the eye reads latest momentum → longer trend left to right.
    for label, lookback in (("Today", 1), ("5D", 5), ("15D", 15), ("1M", 21),
                            ("3M", 63), ("6M", 126), ("12M", 252)):
        old, now = series[max(0, len(series) - 1 - lookback)], series[-1]
        periods.append([label, (now / old - 1) * 100 if old and now else None])
    info["rsPeriods"] = periods
    return info


def _show_symbol_chart_dialog(symbol: str) -> None:
    symbol = str(symbol).strip().upper()
    st.markdown(_DIALOG_CSS, unsafe_allow_html=True)   # compact title row and spacing for this dialog
    period = "5y"  # fetched once; D/W/M and the range buttons work in the browser
    payload = st.session_state.get("symbol_chart_dialog_data")
    if not payload or payload.get("symbol") != symbol or payload.get("period") != period:
        try:
            with st.spinner(f"Loading daily history for {symbol}…"):
                payload = fetch_chart_payload(symbol, period)
            st.session_state["symbol_chart_dialog_data"] = payload
        except Exception as exc:
            st.error(f"Could not load chart history: {exc}")
            if not _DIALOG_HAS_DISMISS and st.button("Close", key=f"close_chart_error_{symbol}"):
                _clear_chart_request()
                st.rerun()
            return
    bars = payload["bars"]
    if not bars:
        st.info("No daily history is available for this symbol.")
        return
    row_match = result[result["Symbol"].astype(str) == symbol]
    row = row_match.iloc[0] if not row_match.empty else None
    info = _chart_info(symbol, row, bars, payload["benchmark"])
    # --- FUNDAMENTALS PANEL START (rollback-safe) ---
    company_name = str(row.get("Company Name", "")) if row is not None else ""
    # --- FUNDAMENTALS PANEL END ---
    as_of = datetime.strptime(payload["dates"][-1], "%Y-%m-%d").date()
    footer = (f"Chart and indicators: end-of-day data as of {as_of:%Y-%m-%d} · NSE / Yahoo Finance · "
              "may contain errors · research and education only")

    chart_slot = st.container()   # filled below the auto-detected base table
    table_html = _base_table_html(payload["base_history"], vcp_pivot=info.get("vcpPivot"),
                                  vcp_contractions=info.get("vcpContractions", ""))
    if table_html:
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("No completed or forming bases matching the rolling history rule were found.")

    # Charts are fully automatic: only the scanner's detected bases are drawn.
    with chart_slot:
        # --- FUNDAMENTALS PANEL START (rollback-safe) ---
        fp.render_launcher(symbol, context="chart_dialog")
        # --- FUNDAMENTALS PANEL END ---
        ui.chart_explorer(bars, symbol, "", "", 0.0,
                          payload["base_history"], visible_window="1Y", info=info, footer=footer)
    # --- FUNDAMENTALS PANEL START (rollback-safe) ---
    fp.render_if_requested(symbol, company_name)
    # --- FUNDAMENTALS PANEL END ---
    if not _DIALOG_HAS_DISMISS and st.button("Close chart", key=f"close_chart_dialog_{symbol}"):
        _clear_chart_request()
        st.rerun()


def show_symbol_chart_dialog(symbol: str) -> None:
    """Open the chart dialog titled with the symbol and company; closing it clears the request."""
    global _DIALOG_HAS_DISMISS
    title = _dialog_title(symbol)
    try:
        decorator = st.dialog(title, width="large", on_dismiss=_clear_chart_request)
        _DIALOG_HAS_DISMISS = True
    except TypeError:  # older Streamlit without on_dismiss: the dialog shows its own Close button
        decorator = st.dialog(title, width="large")
        _DIALOG_HAS_DISMISS = False
    decorator(_show_symbol_chart_dialog)(symbol)


SCREEN_TABS = {
    "Top Picks": "top",
    "Momentum Leader": "momentum",
    "Trend Template": "trend",
    "VCP Setup": "vcp",
    "Entry Candidates": "entry",
    "Volume Breakout": "breakouts",
    "Stage 1 Bases": "bases",
    "RS Blue Dot": "blue_dot",
    # --- MASTER LIST START (rollback-safe) ---
    "Master List": "master",
    # --- MASTER LIST END ---
    "Breadth & Sectors": "market",
    "All Stocks": "all",
    "How to Use This Scanner": "guide",
}
SCREEN_DESCRIPTIONS = {
    "top": "A focused shortlist of high-RS stocks passing the trend and RS-line checks.",
    "momentum": "A staged shortlist near a possible breakout, with explicit market, trend, base, RS and chart-review checks.",
    "trend": "Stocks meeting all eight Minervini Trend Template conditions.",
    "vcp": "Tightening bases with quieter volume and price near a possible pivot.",
    "entry": "Quality leaders at a usable entry point, scored on trend, sector, timing and risk.",
    "breakouts": "Recent price breakouts supported by elevated volume.",
    "bases": "Early sideways bases around a flat long-term moving average.",
    "blue_dot": "Stocks whose relative-strength line leads price to a 52-week high.",
    # --- MASTER LIST START (rollback-safe) ---
    "master": "One deduplicated list of every stock found by the other screens, with a weighted Confluence Score and A/B/C tier.",
    # --- MASTER LIST END ---
    "market": "Market participation, group strength, and the new rotation map.",
    "chart": "Search a stock and inspect daily candles, volume, moving averages, auto-detected bases and optional drawing tools.",
    "all": "The full rated universe, with the current Filters applied.",
    "guide": "Definitions and a practical workflow for reading scanner results.",
}
def _keep_screen_tab():
    """A tab cannot be switched off: clicking the active tab again keeps it selected."""
    if st.session_state.get("screen_tab") is None:
        st.session_state["screen_tab"] = st.session_state.get("_last_screen_tab", "Top Picks")


with slot_tabs:
    with st.container(key="screen-tabs"):
        tab_args = dict(key="screen_tab", default="Top Picks", label_visibility="collapsed", on_change=_keep_screen_tab)
        try:
            picked_tab = st.segmented_control("Screens", list(SCREEN_TABS), required=True, **tab_args)
        except TypeError:  # older Streamlit: no `required`; the callback above keeps one tab selected
            picked_tab = st.segmented_control("Screens", list(SCREEN_TABS), **tab_args)
selected_screen = picked_tab or st.session_state.get("_last_screen_tab", "Top Picks")
if selected_screen not in SCREEN_TABS:  # e.g. a session that still remembers the removed tab
    selected_screen = "Top Picks"
st.session_state["_last_screen_tab"] = selected_screen
active_screen = SCREEN_TABS[selected_screen]
if active_screen != "chart":
    # Chart candles and derived bases are discarded when the user leaves this view.
    st.session_state.pop("chart_explorer_data", None)
view_title_slot = v_title.empty()


def _set_view_note(note: str = "", count=None, count_text=None) -> None:
    """Title row: view name + result count + description, plus an (i) with the full rules."""
    badge = ""
    if count is not None:
        label = count_text or f"{count} stocks currently match"
        badge = f'<span class="cnt">({label})</span>'
    info = ""
    if note:
        paragraphs = note if isinstance(note, (list, tuple)) else [note]
        body = "".join(f'<span class="ln">{p}</span>' for p in paragraphs)
        found = f'<span class="ln"><b>{count}</b> stocks currently match.</span>' if count is not None else ""
        info = (f'<span class="i" tabindex="0">i<span class="tip"><span class="th">{selected_screen} · how it works</span>'
                f'{body}{found}</span></span>')
    view_title_slot.markdown(
        f'<div class="viewhead"><b>{selected_screen}</b>{badge}'
        f'<span class="vd">{SCREEN_DESCRIPTIONS[active_screen]}</span>{info}</div>',
        unsafe_allow_html=True)


_set_view_note()

requested_chart_symbol = st.session_state.get("_symbol_chart_request")
if requested_chart_symbol:
    valid_symbols = set(result["Symbol"].dropna().astype(str))
    if str(requested_chart_symbol) in valid_symbols:
        show_symbol_chart_dialog(str(requested_chart_symbol))
    else:
        st.warning("That symbol is not in the current scanner universe.")

if active_screen == "top":
    show(top, "top_picks", f"Passes all 8 Trend Template conditions, <b>RS ≥ {pref_rs}</b>, RS line within 5% "
                           f"of its 52-week high and <b>RSI &gt; {rsi_min}</b>.")
elif active_screen == "momentum":
    _set_view_note([
        "A rule-based shortlist for chart review. It does not confirm a breakout or issue a trade signal.",
        "<b>1. Market gate:</b> the scan benchmark (Nifty 500; Nifty 50 fallback) closes above its 10-day and 20-day "
        "averages. This is an end-of-day check. If either fails, the candidate list is paused.",
        "<b>2. Near the high:</b> within 25% of the 52-week closing high.",
        "<b>3. Above the 50-day average:</b> price is at or above its 50-day SMA.",
        "<b>4. Base:</b> detected base depth is 20% or less, and price is 0–10% below its pivot.",
        "<b>5. RS line:</b> within 5% of its 52-week high.",
        "<b>Review the chart before keeping a name:</b> check for a first leg of roughly 40% or more, with stronger up "
        "candles, above-average volume and little hesitation; a tight base that holds the 10- and 20-day averages "
        "without a large down day or heavy-volume rejection; and smooth, constructive price action. These "
        "chart-quality checks are not calculated by this screen. The breakout is the final live check.",
    ], len(momentum_candidates) if momentum_ready and momentum_market_ok else None)
    if not momentum_ready:
        st.warning("This deployment’s saved scan does not include the market trend gate yet. Push the code, then run **Daily scan** once to regenerate data.")
    else:
        market10 = bool(result["Market_Above_10SMA"].fillna(False).astype(bool).all())
        market20 = bool(result["Market_Above_20SMA"].fillna(False).astype(bool).all())
        if market10 and market20:
            st.success("Market gate passed: the scan benchmark is above both its 10-day and 20-day averages.")
        else:
            st.warning("Market gate failed: the scan benchmark is below its 10-day or 20-day average. New candidates are paused.")
        if momentum_market_ok:
            defaults = ["Symbol", "RS_Rating", "Pct_To_Pivot", "Pct_From_52W_High",
                        "Pct_Above_50SMA", "Base_Depth_%", "Chg_1D_%", "RS_Line_New_High",
                        "RS_Line_Near_High", "Up_Down_Vol_Ratio_20D", "Sector"]
            visible = choose_table_columns(momentum_candidates, defaults, "momentum_candidates")
            if visible:
                ui.table(momentum_candidates, visible, ("Pct_To_Pivot", 1), font, density,
                         search_keys=["Symbol", "Company Name"], market_context=market_context)
            else:
                st.info("Select at least one column to display this table.")
            if not momentum_candidates.empty:
                st.download_button(
                    "⬇️ Download CSV", momentum_candidates.to_csv(index=False).encode("utf-8"),
                    file_name=f"marketpulse_momentum_candidates_{as_of.date()}.csv",
                    mime="text/csv", key="dl_momentum_candidates",
                )
        elif momentum_market_ok is False:
            st.info("No candidates are shown while the market gate is below either moving average.")
elif active_screen == "chart":
    st.markdown("### 📈 Chart Explorer")
    st.caption("On-demand daily chart for research. History is held temporarily in this browser session and is not saved to project files.")
    choices = (result[["Symbol", "Company Name"]].dropna(subset=["Symbol"])
               .drop_duplicates("Symbol").sort_values("Symbol"))
    names = dict(zip(choices["Symbol"].astype(str), choices["Company Name"].fillna("").astype(str)))
    with st.form("chart_explorer_load"):
        c1, c2, c3 = st.columns([1.2, .7, .65])
        with c1:
            chart_symbol = st.selectbox(
                "Search NSE symbol or company", choices["Symbol"].astype(str).tolist(),
                format_func=lambda s: f"{s} · {names.get(s, '')}".strip(" ·"),
                key="chart_explorer_symbol",
            )
        with c2:
            chart_period = st.selectbox("History", ["1y", "2y", "5y"], index=1, key="chart_explorer_period")
        with c3:
            load_chart = st.form_submit_button("Load chart", type="primary", use_container_width=True)
    if load_chart:
        try:
            with st.spinner(f"Fetching {chart_period} of daily history for {chart_symbol}…"):
                history = load_chart_history(chart_symbol, chart_period)
            relative = history["Close"] / history["Benchmark_Close"].replace(0, np.nan)
            relative = relative / relative.dropna().iloc[0] * 100 if relative.notna().any() else relative
            base_history = chart_base_history(history)
            st.session_state["chart_explorer_data"] = {
                "symbol": chart_symbol, "period": chart_period,
                "benchmark": history.attrs.get("benchmark", "Unavailable"),
                "bars": [{
                    "date": day.strftime("%Y-%m-%d"),
                    "timestamp": int(pd.Timestamp(day).tz_localize(IST).timestamp() * 1000),
                    "open": float(row.Open), "high": float(row.High), "low": float(row.Low),
                    "close": float(row.Close), "volume": int(row.Volume) if pd.notna(row.Volume) else 0,
                    "rs": float(relative.loc[day]) if pd.notna(relative.loc[day]) else None,
                } for day, row in history.iterrows()],
                "dates": [day.strftime("%Y-%m-%d") for day in history.index],
                "base_history": base_history.to_dict("records"),
            }
        except Exception as exc:
            st.error(f"Could not load chart history: {exc}")
    loaded = st.session_state.get("chart_explorer_data")
    if loaded and loaded["symbol"] == chart_symbol and loaded["period"] == chart_period and loaded["bars"]:
        last_day = datetime.strptime(loaded["dates"][-1], "%Y-%m-%d").date()
        stock_row = result[result["Symbol"].astype(str) == chart_symbol]
        stock_row = stock_row.iloc[0] if not stock_row.empty else None
        info = _chart_info(chart_symbol, stock_row, loaded["bars"], loaded["benchmark"])
        range_default = {"1y": "1Y", "2y": "2Y", "5y": "5Y"}.get(chart_period, "2Y")
        visible_window = range_default  # initial zoom; the chart has its own range buttons
        # --- FUNDAMENTALS PANEL START (rollback-safe) ---
        fp.render_launcher(chart_symbol, context="chart_explorer")
        # --- FUNDAMENTALS PANEL END ---
        # RS Rating + RS-line changes live in the chart header, so both chart views match.
        ui.chart_explorer(loaded["bars"], chart_symbol, "", "", 0.0,
                          loaded.get("base_history", []), visible_window=visible_window, info=info)
        # --- FUNDAMENTALS PANEL START (rollback-safe) ---
        fp.render_if_requested(chart_symbol, str(names.get(chart_symbol, "") or ""))
        # --- FUNDAMENTALS PANEL END ---
        page_table = _base_table_html(loaded.get("base_history", []), vcp_pivot=info.get("vcpPivot"),
                                      vcp_contractions=info.get("vcpContractions", ""))
        if page_table:
            st.markdown(page_table, unsafe_allow_html=True)
        else:
            st.info("No completed or forming bases matching the rolling history rule were found in this chart data.")
        st.caption(f"{len(loaded['bars'])} daily candles · prices through {last_day:%d %b %Y} · source: Yahoo Finance. Chart history, RS series and base records are session-only and are not saved to project files.")
    elif loaded:
        st.info("Choose the loaded symbol and history range above, or load a new chart.")
elif active_screen == "trend":
    show(tt, "trend_template", "All 8 Minervini conditions: price above the 50/150/200 SMA, 150 &gt; 200 SMA, "
                               "200 SMA rising, 30% above the 52-week low, within 25% of the 52-week high, "
                               "RS ≥ 70.")
elif active_screen == "vcp":
    with v_title:
        vcp_mode = st.segmented_control(
            "VCP view", ["Setups", "Recent breakouts"], key="vcp_screen_mode", default="Setups",
            label_visibility="collapsed",
            help="Setups = stocks sitting at their pivot. Recent breakouts = VCP pivot crossed on strong volume.",
        )
    scan_frame, selected_scan_date, history_dates, history_key = select_setup_scan("vcp")
    if vcp_mode == "Recent breakouts":
        SCREEN_DESCRIPTIONS["vcp"] = "Fresh VCP pivot crosses that are still holding above the pivot in an uptrend."
        historical_vcp = _vcp_breakout_frame(scan_frame)
        if historical_vcp.empty:
            st.info("No fresh VCP breakouts in this scan. Check **Setups** for stocks sitting at their pivot.")
        show(historical_vcp, "vcp_breakouts",
             "<b>Fresh VCP breakouts</b>: the stock closed above its detected <b>VCP pivot</b> on at least "
             f"<b>{m.BREAKOUT_VOL_X}× the 50-day average volume</b> within the last {m.VCP_BREAKOUT_RECENT} "
             "sessions, and is still <b>above that pivot</b>, in <b>Stage 2</b>, with a rising RS line and price "
             "above its 50-day average. Sorted by most recent breakout first. Raise <b>Minimum RS Rating</b> in "
             "Filters to keep only top-ranked leaders.",
             ui.COLS_VCP_BREAKOUT, ("VCP_Breakout_Days_Ago", 1),
             titles={"Pivot": "VCP pivot"},
             scan_date=selected_scan_date, history_dates=history_dates, history_key=history_key)
    else:
        SCREEN_DESCRIPTIONS["vcp"] = "Tightening bases with quieter volume and price near a possible pivot."
        historical_vcp = scan_frame[scan_frame.get("VCP_Setup", pd.Series(False, index=scan_frame.index))
                                    .fillna(False).astype(bool)].sort_values("Pct_To_Pivot")
        show(historical_vcp, "vcp_setups",
             "<b>Stage 2</b> stocks with 2+ successively tighter pullbacks (last one ≤ 10%), volume dried up over the "
             f"last 10 days (≤ {int(m.VOL_DRYUP_RATIO * 100)}% of the 50-day average) and price "
             f"0-{m.VCP_NEAR_PIVOT:.0f}% below the <b>pivot</b>. Watch for a close above the pivot on heavy "
             "volume. Closest to pivot first.", ui.COLS_PATTERN, ("Pct_To_Pivot", 1),
             titles={"Pivot": "VCP pivot", "Pct_To_Pivot": "To VCP pivot"},
             scan_date=selected_scan_date, history_dates=history_dates, history_key=history_key)
elif active_screen == "entry":
    with v_title:
        entry_preset = st.segmented_control(
            "Entry preset", list(ENTRY_PRESETS), key="entry_preset", default="Balanced",
            label_visibility="collapsed",
            help="Strict = highest quality and tightest timing. Relaxed = more names, looser quality and risk limits. "
                 "Minervini Pro = X-post rules: ₹30+, 100% above 52-week low, full 8/8 Trend Template.",
        )
    cfg = ENTRY_PRESETS[entry_preset]
    # --- MINERVINI PRO START (rollback-safe) ---
    pro_note = (" <b>Minervini Pro</b> adds ₹30+, ≥100% above the 52-week low, a full 8/8 Trend Template, "
                "a 3-month rising 200 SMA and a recent 52-week high when those scan columns are available. "
                "Three VCP legs and 50% tightening add score rather than removing names.") \
        if entry_preset == "Minervini Pro" else ""
    # --- MINERVINI PRO END ---
    market_gate = (bool(result["Market_Trend_OK"].fillna(False).astype(bool).all())
                   if "Market_Trend_OK" in result.columns else True)
    if not market_gate:
        st.warning("Market gate failed: the scan benchmark is below its 10-day or 20-day average. "
                   "New entry candidates are paused until it recovers.")
    show(entry_candidates, "entry_candidates",
         f"<b>Entry Candidates</b> combines leader quality, sector strength, a fresh entry point and extension risk "
         f"into one ranked shortlist. Preset: <b>{entry_preset}</b> — RS ≥ {cfg['rs']}, Trend Template ≥ {cfg['tt']}/8, "
         f"sector strength ≥ {cfg['sec']}, no more than {cfg['ext']}% above the 50-day average, and either within "
         f"{cfg['pivot']}% of the pivot or a breakout no older than {cfg['brk']} sessions. "
         "Score = leader quality 60 + entry position 20 + volume 10 + RS momentum 10, less an extension penalty. "
         f"{pro_note} Continue sorting by score, then confirm on the chart.",
         ui.COLS_ENTRY, ("Entry_Score", -1),
         titles={"Pivot": "Entry pivot", "Pct_To_Pivot": "To pivot",
                 "Stop_Distance_%": "Stop %", "Entry_Reason": "Why"},
         scan_date=None)
elif active_screen == "breakouts":
    scan_frame, selected_scan_date, history_dates, history_key = select_setup_scan("breakouts")
    historical_breakouts = scan_frame[
        scan_frame.get("Vol_Breakout", pd.Series(False, index=scan_frame.index)).fillna(False).astype(bool)
    ].sort_values(["Breakout_Days_Ago", "Breakout_Vol_x"], ascending=[True, False])
    show(historical_breakouts, "volume_breakouts",
         f"Closed above the prior {m.BREAKOUT_LOOKBACK}-session high on <b>≥ {m.BREAKOUT_VOL_X}× the 50-day average "
         f"volume</b> in the last {m.BREAKOUT_RECENT_DAYS} sessions, after a base no deeper than "
         f"{int(m.MAX_BASE_DEPTH * 100)}%, closing in the upper half of the day's range.",
         ui.COLS_PATTERN, ("Breakout_Days_Ago", 1), scan_date=selected_scan_date,
         history_dates=history_dates, history_key=history_key)
elif active_screen == "bases":
    show(s1, "stage1_bases",
         "<b>Stage 1</b> = price around a flat 150-day (30-week) average after a decline, with a sideways base of "
         f"{m.BASE_WINDOWS[0]}+ sessions forming (depth ≤ {int(m.MAX_BASE_DEPTH * 100)}%). Early candidates: "
         "they only become buyable after a breakout into Stage 2. Longest bases first.",
         ui.COLS_PATTERN, ("Base_Days", -1))
elif active_screen == "blue_dot":
    show(blue, "blue_dot", f"RS line at a 52-week high while price is still more than 2% below its own high "
                           f"(RS ≥ {pref_rs}).")
# --- MASTER LIST START (rollback-safe screen) ---
elif active_screen == "master":
    show(master_list, "master",
         "<b>Master List</b> combines every stock found by Top Picks, Momentum Leader, Trend Template, VCP Setup, "
         "VCP breakouts, Entry Candidates, Volume Breakout, Stage 1 Bases, RS Blue Dot and Minervini Pro. "
         "Each symbol appears once; <b>In filters</b> keeps every source tag. "
         "<b>Confluence Score</b> = quality (RS 25 + Trend Template 20 + sector 10 + Stage 2 5 + RS line 5) "
         "+ weighted filter membership up to 35. "
         "Tier: <b>A ≥ 85</b>, <b>B 70–84</b>, <b>C &lt; 70</b>. Sorted by score, then RS Rating.",
         ui.COLS_MASTER, ("Confluence_Score", -1),
         titles={"Confluence_Score": "Confluence", "In_Filters": "In filters",
                 "Filter_Count": "# filters", "Tier": "Tier"},
         scan_date=None)
# --- MASTER LIST END ---
elif active_screen == "market":
    show_breadth_and_sectors()
elif active_screen == "all":
    show(df.sort_values("RS_Rating", ascending=False), "all",
         "Every rated stock" + (" (liquid only)" if liquid_only else "") +
         (f" with market cap above ₹{min_cap:,} cr" if cap_ok and min_cap > 0 else "") +
         ". <b>Click any column header to sort.</b>")

else:
    st.markdown("""
    <style>
    .guide-hero{position:relative;overflow:hidden;padding:28px 30px;border-radius:20px;margin:4px 0 18px;
      background:linear-gradient(120deg,color-mix(in srgb,var(--mp-accent) 16%,var(--mp-surface)),var(--mp-surface2) 56%,color-mix(in srgb,var(--mp-accent2) 12%,var(--mp-surface)));
      border:1px solid color-mix(in srgb,var(--mp-accent) 30%,var(--mp-line));box-shadow:0 14px 34px var(--mp-shadow)}
    .guide-hero:after{content:"";position:absolute;right:-60px;top:-90px;width:260px;height:260px;border-radius:50%;
      background:radial-gradient(circle,var(--mp-glow),transparent 70%);pointer-events:none}
    .guide-eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:.72rem;font-weight:800;
      color:var(--mp-accent);margin-bottom:9px}
    .guide-hero h2{margin:0 0 9px;font-size:1.72rem;letter-spacing:-.02em}
    .guide-hero p{margin:0;max-width:920px;line-height:1.62;color:var(--mp-muted);font-weight:500}
    .guide-new{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px}
    .guide-new span{padding:5px 10px;border-radius:999px;font-size:.75rem;font-weight:700;
      color:var(--mp-accent);background:color-mix(in srgb,var(--mp-accent) 10%,var(--mp-surface));
      border:1px solid color-mix(in srgb,var(--mp-accent) 22%,var(--mp-line))}
    .guide-sec{display:flex;align-items:center;gap:10px;margin:22px 0 12px}
    .guide-sec .badge{width:29px;height:29px;flex:none;border-radius:9px;display:inline-flex;align-items:center;justify-content:center;
      background:linear-gradient(135deg,var(--mp-accent),var(--mp-accent2));color:#fff;font-weight:800;font-size:.8rem;
      box-shadow:0 4px 12px color-mix(in srgb,var(--mp-accent) 30%,transparent)}
    .guide-sec h3{margin:0;font-size:1.08rem;letter-spacing:-.01em}
    .guide-card{position:relative;border:1px solid var(--mp-line);border-radius:15px;padding:17px 18px;
      min-height:158px;margin:0 0 12px;background:var(--mp-surface);box-shadow:0 6px 18px var(--mp-shadow);
      transition:transform .15s,border-color .15s}
    .guide-card:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--mp-accent) 45%,var(--mp-line))}
    .guide-card .gicon{width:35px;height:35px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;
      font-size:1.15rem;margin-bottom:10px;background:color-mix(in srgb,var(--mp-accent) 12%,var(--mp-surface2));
      color:var(--mp-accent)}
    .guide-card h4{margin:0 0 7px;font-size:1rem;letter-spacing:-.01em}
    .guide-card p{margin:0;font-size:.9rem;line-height:1.56;color:var(--mp-muted)}
    .guide-step{position:relative;border:1px solid var(--mp-line);border-radius:13px;padding:12px 14px 12px 17px;
      margin:9px 0;background:var(--mp-surface);box-shadow:0 5px 14px var(--mp-shadow)}
    .guide-step:before{content:"";position:absolute;left:0;top:11px;bottom:11px;width:3px;border-radius:99px;
      background:linear-gradient(180deg,var(--mp-accent),var(--mp-accent2))}
    .guide-step b{font-size:.98rem}
    .guide-step p{margin:4px 0 0;line-height:1.55;color:var(--mp-muted)}
    .guide-callout,.guide-good{padding:15px 17px;border-radius:13px;line-height:1.6;margin:11px 0;
      color:var(--mp-text);box-shadow:0 5px 16px var(--mp-shadow)}
    .guide-callout{background:color-mix(in srgb,#f59e0b 11%,var(--mp-surface));
      border:1px solid color-mix(in srgb,#f59e0b 30%,var(--mp-line))}
    .guide-good{background:color-mix(in srgb,var(--mp-good) 11%,var(--mp-surface));
      border:1px solid color-mix(in srgb,var(--mp-good) 30%,var(--mp-line))}
    .guide-step .gl{color:var(--mp-accent);font-weight:800}
    .guide-step .gok{color:var(--mp-good);font-weight:800}
    .guide-card code,.guide-callout code{color:var(--mp-accent);font-weight:700}
    @media (max-width:760px){
      .guide-hero{padding:22px 20px;border-radius:16px;margin:2px 0 14px}
      .guide-hero h2{font-size:1.42rem}
      .guide-hero p{font-size:.93rem}
      .guide-sec{margin:18px 0 10px}
      .guide-sec h3{font-size:1rem}
      .guide-card{min-height:0;padding:15px 16px;border-radius:13px}
      .guide-card h4{font-size:.95rem}
      .guide-step{padding:11px 13px 11px 16px}
      .guide-callout,.guide-good{padding:13px 14px;font-size:.92rem}
    }
    </style>
    <div class="guide-hero">
      <div class="guide-eyebrow">A practical walkthrough · refreshed for the current build</div>
      <h2>How to use this scanner</h2>
      <p>Use the scan to shortlist stocks with relative strength, a constructive trend and a possible setup.
      Then confirm the structure on the in-app chart and decide whether the risk fits your own plan. No single score confirms a trade.</p>
      <div class="guide-new"><span>✏ Chart drawing tools</span><span>Entry Candidates presets</span><span>VCP recent breakouts</span><span>RS Δ in chart header</span><span>Light / dark theme</span></div>
    </div>
    """, unsafe_allow_html=True)

    def _gsec(num: str, title: str) -> None:
        st.markdown(f'<div class="guide-sec"><span class="badge">{num}</span><h3>{title}</h3></div>',
                    unsafe_allow_html=True)

    _gsec("01", "The three-step workflow")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.markdown("""<div class="guide-card"><div class="gicon">🧭</div><h4>Market first</h4>
        <p>Open <b>Breadth & sectors</b>. Check participation and the rotation map before focusing on individual leaders.</p></div>""",
                    unsafe_allow_html=True)
    with g2:
        st.markdown("""<div class="guide-card"><div class="gicon">💪</div><h4>Find relative strength</h4>
        <p>Prefer a higher <b>RS Rating</b>, positive <b>RS Δ</b> and strong <b>Sector strength</b>. These answer different questions—see below.</p></div>""",
                    unsafe_allow_html=True)
    with g3:
        st.markdown("""<div class="guide-card"><div class="gicon">🔎</div><h4>Inspect the setup</h4>
        <p>Check trend, volume and base context. Open the stock chart for auto-marked bases, the VCP pivot and optional drawing tools.</p></div>""",
                    unsafe_allow_html=True)

    _gsec("02", "Start with the right meaning of RS")
    rs1, rs2 = st.columns(2)
    with rs1:
        st.markdown("""<div class="guide-card"><h4>RS Rating · rank within this universe</h4>
        <p>A 1–99 percentile-style score based on weighted 3-, 6-, 9- and 12-month returns
        (40%, 20%, 20%, 20%). Higher means stronger against the other scanned stocks—not against an index.</p></div>""",
                    unsafe_allow_html=True)
    with rs2:
        st.markdown("""<div class="guide-card"><h4>RS Δ · performance against the benchmark</h4>
        <p>The chart header now shows <b>RS Δ vs benchmark</b> for Today, 5D, 15D, 1M, 3M, 6M and 12M.
        Positive means outperformance. The <b>RS line</b> tracks the stock-to-index ratio; blue dots mark new highs.</p></div>""",
                    unsafe_allow_html=True)
    st.markdown("""<div class="guide-callout"><b>Benchmark currently used:</b> Nifty 500 (<code>^CRSLDX</code>),
    with Nifty 50 (<code>^NSEI</code>) as fallback. The chart header, RS line and “RS vs Nifty” columns use the
    benchmark series returned by the scan. The saved table does not record which fallback was used.</div>""",
                unsafe_allow_html=True)

    _gsec("03", "Read from broad context to one stock")
    steps = [
        ("A", "Breadth & sectors", "Use advancing/declining stocks and the share above the 50-, 150- and 200-day averages to judge market participation. The rotation map compares each group’s median 3-month benchmark-relative return with the share of its stocks whose RS is improving. It is a scanner-derived view, not a classic index-based RRG."),
        ("B", "RS Rating and RS Δ", "Prefer a high or improving RS Rating for leaders, then check the chart header’s RS Δ vs benchmark and whether the RS line is near a high. These are complementary signals, not guarantees."),
        ("C", "Trend Template (score / 8)", "Open the Trend Template tab or the stock’s ⓘ details. Review each condition, not just the total. A full 8/8 means all eight rules pass on the latest data; it does not mean the stock is automatically a buy."),
        ("D", "Trend, volume and setup", "Strong trend / Developing / Weakening are rule-based summaries. Volume pressure compares volume on up days with down days over 20 sessions; it is not delivery data. VCP, base and breakout labels are pattern candidates that need chart confirmation."),
        ("E", "Confirm on the in-app chart", "Click the symbol to open the KLine chart. Auto-detected bases, the VCP pivot, sector strength and the Trend Template pill are already marked; the small pencil opens optional drawing tools when you want to annotate."),
    ]
    for letter, title, description in steps:
        st.markdown(f'<div class="guide-step"><b><span class="gl">{letter}</span> · {title}</b><p>{description}</p></div>',
                    unsafe_allow_html=True)

    _gsec("04", "Trend Template: what 8/8 means")
    st.caption("The score counts how many of these rules pass for a stock on the latest scan date.")
    tt_rules = [
        "Price is above both the 150-day and 200-day averages.",
        "The 150-day average is above the 200-day average.",
        "The 200-day average is rising versus about one month ago.",
        "The 50-day average is above both the 150-day and 200-day averages.",
        "Price is above the 50-day average.",
        "Price is at least 30% above its 52-week closing low.",
        "Price is within 25% of its 52-week closing high.",
        f"RS Rating is at least {m.MIN_RS_TT}.",
    ]
    tt_left, tt_right = st.columns(2)
    for i, rule in enumerate(tt_rules):
        with (tt_left if i < 4 else tt_right):
            st.markdown(f'<div class="guide-step"><b><span class="gok">✓ {i + 1}</span></b><p>{rule}</p></div>',
                        unsafe_allow_html=True)

    _gsec("05", "Setup tabs at a glance")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown(f"""<div class="guide-card"><h4>VCP setups</h4><p>Switch between <b>Setups</b> and
        <b>Recent breakouts</b> inside the tab. Auto-marked charts show <b>Base pivot</b> and <b>VCP pivot</b>
        separately. A pivot is a level to watch; wait for chart confirmation rather than treating proximity as a signal.</p></div>
        <div class="guide-card"><h4>Entry candidates</h4><p>A ranked shortlist combining RS, Trend Template, sector
        strength, a fresh pivot/breakout, volume and extension risk. Use <b>Strict</b>, <b>Balanced</b>,
        <b>Relaxed</b> or <b>Minervini Pro</b> to control selectivity; Balanced is the default.
        Minervini Pro adds the stricter X-post rules without changing the other presets.
        Confirm the chart and risk level before acting.</p></div>
        <div class="guide-card"><h4>Master List</h4><p>One clean list built from every screen. Duplicate symbols are
        removed; <b>In filters</b> shows where each stock came from. The <b>Confluence Score</b> rewards quality plus
        multiple confirmations, with tiers <b>A ≥ 85</b>, <b>B 70–84</b> and <b>C &lt; 70</b>. Use it as a shortlist
        map, not as an automatic buy signal.</p></div>
        <div class="guide-card"><h4>Stage 1 bases</h4><p>Stocks around a flat 150-day average with a sideways base.
        These are early watch-list candidates; the scanner does not call a base a confirmed uptrend.</p></div>""",
                    unsafe_allow_html=True)
    with s2:
        st.markdown(f"""<div class="guide-card"><h4>Breakouts</h4><p>Recent close above the prior
        {m.BREAKOUT_LOOKBACK}-session high, with volume at least {m.BREAKOUT_VOL_X}× the 50-day average and
        other range/base checks. Review the candle, volume and nearby resistance yourself.</p></div>
        <div class="guide-card"><h4>RS blue dot</h4><p>The RS line reaches a 52-week high while the stock price
        remains more than 2% below its own 52-week high. It highlights relative strength leading price; it is
        a watch signal, not a forecast.</p></div>""",
                    unsafe_allow_html=True)

    _gsec("06", "Learn from a live example")
    st.caption("This small table uses the current scan data to illustrate how the columns fit together. It is an example for learning, not a recommendation.")
    guide_cols = [c for c in ["Symbol", "Trend_State", "RS_Rating", "RS_Excess_3M_%", "RS_Excess_6M_%",
                              "TT_Score", "Volume_Pressure_20D", "Stage"] if c in result.columns]
    guide_example = result.sort_values(["RS_Rating", "Weighted_Return_%"], ascending=False).head(5)
    if not guide_example.empty:
        ui.table(guide_example, guide_cols, ("RS_Rating", -1), font, "Compact",
                 search_keys=["Symbol", "Company Name"])
    else:
        st.info("A live example will appear when scan results are available.")

    _gsec("07", "Filters, details and charts")
    f1, f2 = st.columns(2)
    with f1:
        st.markdown("""<div class="guide-card"><h4>Keep the first pass broad</h4>
        <p>Start with the symbol/company search, sector filter and a modest minimum RS. Then narrow to liquid
        stocks or raise the RS threshold if the list is still large. Use <b>Custom screen builder</b> inside the
        <b>Filters</b> button to add up to three numeric conditions. Filters affect stock-list screens; the
        Breadth & sectors calculations use the liquid universe independently.</p></div>""", unsafe_allow_html=True)
    with f2:
        st.markdown("""<div class="guide-card"><h4>Open details, then the chart</h4>
        <p>Use the small <b>ⓘ</b> button beside a symbol for the in-app summary. Click the symbol itself to open
        its KLine chart, then use the subtle pencil button for optional drawings. Switch between <b>List</b> and
        <b>Strength map</b> to compare current RS signals; the map is not a historical price chart. Sort tables by
        clicking a heading and download them as CSV.</p></div>""",
                    unsafe_allow_html=True)

    _gsec("08", "Know the limits")
    st.markdown("""<div class="guide-good"><b>Best practice:</b> treat this app as a discovery and comparison tool.
    Confirm signals on the chart, consider liquidity and downside risk, and use your own rules. Scores, pattern
    labels and market context are based on historical data; they can be delayed, incomplete or wrong and do not
    predict future returns. Optional drawings stay in your browser only and never change scan results.</div>""",
                unsafe_allow_html=True)
    st.caption(f"Data as of {as_of:%d %b %Y}. RS ratings require sufficient price history; calculated scan coverage is {len(result)} stocks.")

with st.expander("Notes & limitations"):
    st.markdown(
        f"- **Data:** calculated once every weekday evening (about 5 pm IST, after the market closes) and saved "
        f"to the app's `data/` folder. The app reads those bundled CSV files first; it only uses a remote dataset "
        f"when `MARKETPULSE_DATA_URL` is configured, and never calls Yahoo from the browser.\n"
        f"- **Universe:** the Nifty Total Market list from NSE (Nifty 500 + Nifty Microcap 250, about 750 stocks). "
        f"Placeholder `DUMMY…` rows are ignored; a few REIT units are included as NSE lists them.\n"
        f"- **RS Rating** ranks every rated stock in this universe (1-99). Stocks with less than 12 months of "
        f"price history, or with no Yahoo Finance data, are not rated.\n"
        f"- **Momentum context:** 3- and 6-month relative returns compare each stock with the Nifty 500. "
        f"**RS Δ vs benchmark** in the chart header compares stock and benchmark returns over each listed lookback; "
        f"it is not a true RS rating recalculated by timeframe. "
        f"The 20-day up/down volume ratio compares volume on rising and falling sessions; ≥1.25 is "
        f"up-volume dominant and ≤0.80 is down-volume dominant. This is not delivery or participant-flow data.\n"
        f"- **Trend status and extension labels are screening heuristics, not forecasts.** Strong trend requires "
        f"Stage 2, TT score ≥6/8, RS ≥80, and positive, improving 3-month relative strength. Developing uses "
        f"Stage 2, TT ≥5/8, RS ≥70, and positive 3-month relative strength. Weakening marks Stage 4, or "
        f"negative 3-month relative strength combined with TT ≤3 or down-volume dominance. Extended means price is at least "
        f"{m.EXTENSION_WARN_PCT:.0f}% above its 50-day SMA. Market breadth is Supportive at ≥60% above both "
        f"the 50- and 200-day SMAs, Weak when fewer than 40% are above either, and Mixed otherwise.\n"
        f"- **Liquid** = {LIQ_TEXT} (close × volume). The *Liquid stocks only* switch filters the stock lists; "
        f"breadth and sector figures always use liquid stocks.\n"
        f"- **Sectors** are NSE's 22 sectors, taken from the NSE index constituent list.\n"
        f"- **Market cap** = shares outstanding (Yahoo Finance, cached for a week) × the latest close, in ₹ crore. "
        f"Yahoo's share counts are occasionally stale or off for small companies, so treat borderline cases with care.\n"
        f"- 52-week high/low use closing prices, not intraday extremes.\n"
        f"- **Stages** use the 150-day SMA (about the 30-week average): Stage 2 = price above a rising average, "
        f"Stage 4 = below a falling one; Stage 1/3 = flat average after a decline/advance.\n"
        f"- **VCP, bases and breakouts are rule-based approximations** computed on daily closes/highs/lows. "
        f"They will flag some patterns a human would reject and miss others, so always confirm on the chart.\n"
        f"- **Drawing tools** are optional browser-side overlays saved per symbol and timeframe. Delete removes the "
        f"last drawing and Clear all removes every drawing for that symbol/timeframe only; they never affect scan "
        f"data, screens or other charts.\n"
        f"- RS Line is measured against the Nifty 500 index (Yahoo Finance); Yahoo data can have gaps.\n"
        f"- Educational tool, not investment advice."
    )

with st.expander("Disclaimer & data sources"):
    st.markdown("""
    <style>
    .policy-wrap{border:1px solid var(--mp-line);border-radius:14px;background:var(--mp-surface);
      padding:18px 20px;box-shadow:0 6px 18px var(--mp-shadow);margin:2px 0 12px}
    .policy-kicker{text-transform:uppercase;letter-spacing:.12em;font-size:.7rem;font-weight:800;
      color:var(--mp-accent);margin-bottom:8px}
    .policy-wrap h4{margin:0 0 9px;font-size:1.05rem;letter-spacing:-.01em}
    .policy-wrap p,.policy-wrap li{margin:0 0 9px;color:var(--mp-muted);line-height:1.62;font-size:.92rem}
    .policy-wrap a{color:var(--mp-accent);text-decoration:none;font-weight:700}
    .policy-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:11px;margin:13px 0}
    .policy-item{border:1px solid var(--mp-line);border-radius:12px;padding:13px 14px;
      background:color-mix(in srgb,var(--mp-accent) 5%,var(--mp-surface2))}
    .policy-item b{display:block;margin-bottom:4px;color:var(--mp-text);font-size:.9rem}
    .policy-item span{color:var(--mp-muted);font-size:.88rem;line-height:1.55}
    .policy-note{border-left:3px solid var(--mp-accent);padding:11px 14px;border-radius:0 10px 10px 0;
      background:color-mix(in srgb,var(--mp-accent) 8%,var(--mp-surface));color:var(--mp-text);line-height:1.62;font-size:.92rem}
    @media(max-width:700px){.policy-wrap{padding:15px 16px}.policy-wrap h4{font-size:.98rem}
      .policy-wrap p,.policy-wrap li,.policy-note{font-size:.89rem}}
    </style>
    <div class="policy-wrap">
      <div class="policy-kicker">Website policy</div>
      <h4>Track-750 — stock screening, charting and market analytics for Indian equities</h4>
      <p>This website is operated by <a href="mailto:momd.shakeel@gmail.com">momd.shakeel@gmail.com</a>
      and is hosted at <a href="https://track-750-refined.streamlit.app/">track-750-refined.streamlit.app</a>.</p>
      <p>Track-750 is for education and research only. It is not investment advice, a research report, or a
      recommendation to buy, sell or hold any security or fund. We are not registered with SEBI as an investment
      adviser or research analyst.</p>
      <div class="policy-grid">
        <div class="policy-item"><b>Charts</b><span>Technical charts are built with KLineChart, used under the Apache License 2.0.</span></div>
        <div class="policy-item"><b>Prices</b><span>Daily price data is provided by Yahoo Finance. This is not a live market feed.</span></div>
        <div class="policy-item"><b>Universe &amp; sectors</b><span>NSE Nifty Total Market constituent list and NSE basic-industry classification.</span></div>
        <div class="policy-item"><b>Index history</b><span>niftyindices.com index history is used for benchmark context where available.</span></div>
      </div>
      <div class="policy-note"><b>Data &amp; performance notice:</b> data is end-of-day, updated after each market close,
      and is not live. It may be delayed or contain errors, so verify prices and corporate actions with the exchange
      or another official source before acting. Rankings, screens and backtests are mechanical outputs of rules applied
      to historical data. Past and backtested performance does not guarantee future results, and backtests carry known
      limitations such as missing delisted companies, idealised fills, and no taxes or costs.</div>
      <p style="margin-top:12px"><b>Markets carry risk of loss.</b> Do your own research and consult a SEBI-registered
      investment adviser before making investment decisions.</p>
    </div>
    """, unsafe_allow_html=True)
