"""Session-only Trendlyne MF inflow mapping for the MF Inflow screen.

No CSV, JSON, cache folder, database or repository data file is written. The
Trendlyne rows are either fetched at runtime from the public screener API or
supplied by the user through an in-app CSV uploader; both paths keep the rows
only in the current Streamlit session.
"""
# --- MF INFLOW PANEL START (rollback-safe) ---
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

API_URL = "https://trendlyne.com/fundamentals/api/tl-all-in-one-screener-data-get/v2/"
SCREEN_PK = 31264
GROUP_TYPE = "index"
GROUP_NAME = "NFTYTOTMKT"
PAGE_SIZE = 100
CACHE_SECONDS = 15 * 60

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://trendlyne.com/fundamentals/stock-screener/31264/"
               "mutual-funds-increased-shareholding-in-past-month/index/"
               "NFTYTOTMKT/nifty-total-market/",
}

_SYMBOL_COLS = ("NSE Symbol", "NSEcode", "Symbol", "NSE symbol")
_NAME_COLS = ("Stock", "shortname", "Company Name", "Company")
_MONTH_COLS = ("Month Change %", "MF_Month_Chg_%", "month_changeP", "Month Chg %")
_STATE_KEY = "mf_inflow_month_change_frame"
_STATE_AT_KEY = "mf_inflow_month_change_fetched_at"


def _empty_result():
    return pd.DataFrame(columns=["Symbol", "Stock_Name", "MF_Month_Chg_%"])


def _pick_column(frame, candidates):
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def _numeric(series):
    """Parse Trendlyne values such as '1.85%' or '1,234.5' into floats."""
    return pd.to_numeric(
        series.astype(str).str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def parse_uploaded_csv(uploaded):
    """Normalise the user's final Trendlyne CSV into symbol/month-change rows."""
    if uploaded is None:
        return _empty_result()

    raw = pd.read_csv(uploaded)
    symbol_col = _pick_column(raw, _SYMBOL_COLS)
    month_col = _pick_column(raw, _MONTH_COLS)
    name_col = _pick_column(raw, _NAME_COLS)

    if symbol_col is None and name_col is None:
        raise ValueError("The CSV needs a 'NSE Symbol' or 'Stock' column.")

    out = pd.DataFrame(index=raw.index)
    out["Symbol"] = (raw[symbol_col] if symbol_col else pd.Series("", index=raw.index)).astype(str).str.strip()
    out["Stock_Name"] = (raw[name_col] if name_col else pd.Series("", index=raw.index)).astype(str).str.strip()

    if month_col:
        out["MF_Month_Chg_%"] = _numeric(raw[month_col])
    else:
        out["MF_Month_Chg_%"] = float("nan")

    # The source query already applies MF holding change > 0. Do not re-filter on
    # its rounded display value, which can be 0.00 for a small positive change.

    out = out[(out["Symbol"].ne("")) | (out["Stock_Name"].ne(""))].copy()
    out = out[out["MF_Month_Chg_%"] > 0].copy()
    out = out.drop_duplicates(subset="Symbol" if symbol_col else "Stock_Name", keep="first")
    return out[["Symbol", "Stock_Name", "MF_Month_Chg_%"]].reset_index(drop=True)


def _fetch_page(page_number):
    response = requests.get(
        API_URL,
        params={
            "perPageCount": PAGE_SIZE,
            "groupType": GROUP_TYPE,
            "groupName": GROUP_NAME,
            "screenpk": SCREEN_PK,
            "pageNumber": page_number,
        },
        headers=_HEADERS,
        timeout=25,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(
            "Trendlyne asked for human verification. Upload the final CSV in the page instead."
        ) from error
    if str(payload.get("head", {}).get("status", "")) != "0":
        raise RuntimeError(payload.get("head", {}).get("statusDescription") or "Trendlyne query failed")
    body = payload.get("body") or {}
    headers = [item.get("unique_name") for item in body.get("tableHeaders", [])]
    rows = body.get("tableData") or []
    frame = pd.DataFrame(rows, columns=headers)
    return frame, bool(body.get("isNextPage"))


def fetch_month_change_frame():
    """Fetch all public Trendlyne rows with MF 1M > 0 and positive Month Chg %."""
    all_rows = []
    page = 0
    while True:
        frame, has_next = _fetch_page(page)
        if frame.empty:
            break
        all_rows.append(frame)
        if not has_next or page >= 25:
            break
        page += 1

    if not all_rows:
        return _empty_result()

    raw = pd.concat(all_rows, ignore_index=True)
    out = pd.DataFrame(index=raw.index)
    out["Symbol"] = (raw.get("NSEcode") if "NSEcode" in raw else pd.Series("", index=raw.index)).astype(str).str.strip()
    out["Stock_Name"] = (raw.get("shortname") if "shortname" in raw else pd.Series("", index=raw.index)).astype(str).str.strip()
    out["MF_Month_Chg_%"] = (pd.to_numeric(raw["month_changeP"], errors="coerce")
                              if "month_changeP" in raw else float("nan"))

    # Trendlyne's saved query already enforces MF holding change > 0; keep its
    # rows even when the rounded MF column displays 0.00.
    out = out[out["MF_Month_Chg_%"] > 0].copy()
    out = out[(out["Symbol"].ne("")) | (out["Stock_Name"].ne(""))].copy()
    out = out.drop_duplicates(subset="Symbol", keep="first")
    return out[["Symbol", "Stock_Name", "MF_Month_Chg_%"]].reset_index(drop=True)


def load_month_change(force_refresh=False):
    """Return session-only cached rows plus fetch time and an optional error."""
    now = datetime.now(timezone.utc)
    cached = st.session_state.get(_STATE_KEY)
    fetched_at = st.session_state.get(_STATE_AT_KEY)
    fresh = (
        cached is not None
        and fetched_at is not None
        and (now - fetched_at).total_seconds() < CACHE_SECONDS
    )
    if fresh and not force_refresh:
        return cached.copy(), fetched_at, None

    try:
        frame = fetch_month_change_frame()
        fetched_at = now
        st.session_state[_STATE_KEY] = frame
        st.session_state[_STATE_AT_KEY] = fetched_at
        return frame.copy(), fetched_at, None
    except Exception as error:  # keep the last good in-memory result if present
        message = f"Automatic Trendlyne fetch unavailable: {error}"
        if cached is not None:
            return cached.copy(), fetched_at, message
        return _empty_result(), None, message


def merge_master_with_month_change(master, inflow):
    """Keep every Master List column and append Trendlyne Month Chg % where matched."""
    column = "MF_Month_Chg_%"
    if master is None or master.empty:
        out = master.iloc[0:0].copy() if master is not None else pd.DataFrame()
        out[column] = pd.Series(dtype=float)
        return out

    out = master.copy()
    if inflow is None or inflow.empty:
        out[column] = float("nan")
        return out.iloc[0:0].copy()

    by_symbol = dict(zip(inflow["Symbol"].astype(str).str.strip().str.upper(), inflow[column]))
    by_name = dict(zip(inflow["Stock_Name"].astype(str).str.strip().str.upper(), inflow[column]))
    symbols = (out["Symbol"].astype(str).str.strip().str.upper() if "Symbol" in out.columns
               else pd.Series("", index=out.index))
    values = symbols.map(by_symbol)

    if "Company Name" in out.columns and values.isna().any():
        names = out["Company Name"].astype(str).str.strip().str.upper()
        values = values.fillna(names.map(by_name))

    out[column] = pd.to_numeric(values, errors="coerce")
    out = out[out[column].notna()].copy()
    if out.empty:
        return out
    sort_cols = [c for c in ["Confluence_Score", column, "RS_Rating"] if c in out.columns]
    return out.sort_values(sort_cols, ascending=[False] * len(sort_cols))
# --- MF INFLOW PANEL END ---
