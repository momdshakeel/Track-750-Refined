"""
Temporary fundamentals popup for MarketPulse 750.

Rollback: delete this file and remove the clearly marked FUNDAMENTALS PANEL blocks in app.py.

Design rules:
- The launcher is a native Streamlit button placed just outside the chart iframe.
- Data is fetched only after the launcher is clicked.
- Data lives only in st.session_state; no CSV, JSON, cache folder, or repository file is written.
- The popup is a self-contained iframe with a close button, Escape support and backdrop close.
- Chart construction, drawing tools and existing screens are not changed.
"""
from __future__ import annotations

import html as _html
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

_CACHE_KEY = "mp_fundamentals_cache"
_REQUEST_KEY = "mp_fundamentals_request"
_CACHE_TTL_SECONDS = 15 * 60
_HELP_TEXT = "Fundamentals snapshot"
_MODAL_MARKER = "MPF_MODAL"

_LAUNCHER_CSS = """<style>
/* Only the fundamentals launcher: scoped by its Streamlit key prefix. */
[class*="st-key-mpf_open_"]{display:flex!important;justify-content:flex-end!important;margin:0!important}
[class*="st-key-mpf_open_"] button[data-testid="stBaseButton-tertiary"]{
  width:30px!important;height:30px!important;min-width:30px!important;padding:0!important;
  border-radius:50%!important;border:1px solid var(--mp-line,rgba(128,128,128,.35))!important;
  background:transparent!important;color:var(--mp-text,#64748b)!important;
  font-size:0!important;line-height:1!important;box-shadow:none!important;
}
[class*="st-key-mpf_open_"] button[data-testid="stBaseButton-tertiary"]:hover{
  background:var(--mp-accent,#2563eb)!important;color:#fff!important;
  border-color:var(--mp-accent,#2563eb)!important;
}
[class*="st-key-mpf_open_"] button[data-testid="stBaseButton-tertiary"] span[data-testid="stIconMaterial"]{
  font-size:16px!important;line-height:1!important;
}
</style>"""

_MODAL_IFRAME_CSS = """<style>
/* Scope only the fundamentals popup iframe created by components.html. */
body:has(iframe[srcdoc*="MPF_MODAL"]) iframe[srcdoc*="MPF_MODAL"]{
  position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;
  border:0!important;z-index:2147483647!important;background:transparent!important;
}
</style>"""


# ---------------------------- public API ----------------------------

def _queue_request(symbol: str) -> None:
    st.session_state[_REQUEST_KEY] = {"symbol": symbol, "nonce": str(time.time_ns())}


def render_launcher(symbol: str, context: str = "chart") -> None:
    """Render a tiny native button; clicking it only records a one-shot request."""
    st.markdown(_LAUNCHER_CSS, unsafe_allow_html=True)
    sym = str(symbol or "").strip().upper()
    key = "mpf_open_" + re.sub(r"\W+", "_", f"{context}_{sym}")
    left, right = st.columns([1, 0.12], gap="small", vertical_alignment="center")
    with right:
        st.button(
            "Fundamentals snapshot",
            icon=":material/bar_chart:",
            help=_HELP_TEXT,
            key=key,
            type="tertiary",
            on_click=_queue_request,
            args=(sym,),
        )


def render_if_requested(symbol: str, company: str = "") -> None:
    """Fetch once on click and render the temporary popup. No disk writes."""
    request = st.session_state.pop(_REQUEST_KEY, None)
    if not request or str(request.get("symbol", "")).upper() != str(symbol or "").strip().upper():
        return

    sym = str(symbol).strip().upper()
    with st.spinner("Loading fundamentals snapshot…"):
        payload = _get_session_payload(sym, company)

    import streamlit.components.v1 as components  # local import; not needed on normal load

    document = _modal_html(payload)
    st.markdown(_MODAL_IFRAME_CSS, unsafe_allow_html=True)
    components.html(document, height=100, scrolling=False)


# ---------------------------- session cache ----------------------------

def _get_session_payload(symbol: str, company: str = "") -> Dict[str, Any]:
    cache = st.session_state.setdefault(_CACHE_KEY, {})
    cached = cache.get(symbol)
    now = time.time()
    if (cached and now - float(cached.get("ts", 0)) < _CACHE_TTL_SECONDS
            and isinstance(cached.get("data"), dict)
            and not cached["data"].get("error")):
        payload = dict(cached["data"])
        if company:
            payload["company"] = str(company)
        payload["from_session_cache"] = True
        return payload

    payload = _fetch_fundamentals(symbol, company)
    payload["from_session_cache"] = False
    cache[symbol] = {"ts": now, "data": payload}
    return payload


# ---------------------------- Yahoo fetch (lazy) ----------------------------

_REVENUE_KEYS = ("Total Revenue", "Revenue", "Revenues", "Sales Revenue", "Sales")
_EPS_KEYS = ("EPS", "Basic EPS", "Diluted EPS", "Normalized EPS", "EPS - Basic")
_OP_KEYS = ("Operating Income", "Operating Income Or Loss", "Operating Profit", "Operating Income (Loss)")
_OPM_KEYS = ("Operating Margin", "Operating Margin %", "Operating Profit Margin")


def _fetch_fundamentals(symbol: str, company: str = "") -> Dict[str, Any]:
    sym = str(symbol or "").strip().upper()
    yahoo_symbol = sym if sym.endswith((".NS", ".BO")) else sym + ".NS"
    try:
        import yfinance as yf  # imported only on click, so normal app load stays fast
    except Exception as exc:  # pragma: no cover - environment dependent
        return _error_payload(sym, company, yahoo_symbol, f"yfinance is unavailable: {exc}")

    try:
        ticker = yf.Ticker(yahoo_symbol)
        quarterly_df = _statement(ticker, "quarterly")
        annual_df = _statement(ticker, "yearly")
    except Exception as exc:
        return _error_payload(sym, company, yahoo_symbol, str(exc))

    quarterly = _rows_from_statement(quarterly_df, annual=False)
    annual = _rows_from_statement(annual_df, annual=True)
    if not quarterly and not annual:
        return _error_payload(
            sym, company, yahoo_symbol,
            "Yahoo Finance did not return usable income-statement data for this symbol.",
        )

    return {
        "symbol": sym,
        "company": str(company or ""),
        "yahoo_symbol": yahoo_symbol,
        "quarterly": quarterly,
        "annual": annual,
        "as_of": datetime.now().strftime("%d %b %Y"),
        "error": "",
    }


def _error_payload(symbol: str, company: str, yahoo_symbol: str, message: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "company": str(company or ""),
        "yahoo_symbol": yahoo_symbol,
        "quarterly": [],
        "annual": [],
        "as_of": datetime.now().strftime("%d %b %Y"),
        "error": str(message or "Data unavailable"),
    }


def _statement(ticker: Any, freq: str) -> Optional[pd.DataFrame]:
    """New yfinance uses get_income_stmt(freq=...); older versions use financials props."""
    candidates = (
        ("get_income_stmt", {"freq": freq}),
        ("get_financials", {}),
    ) if freq == "yearly" else (
        ("get_income_stmt", {"freq": freq}),
        ("get_quarterly_financials", {}),
    )
    for name, kwargs in candidates:
        fn = getattr(ticker, name, None)
        if not callable(fn):
            continue
        try:
            frame = fn(**kwargs)
        except TypeError:
            try:
                frame = fn()
            except Exception:
                frame = None
        except Exception:
            frame = None
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame

    prop = "quarterly_financials" if freq == "quarterly" else "financials"
    try:
        frame = getattr(ticker, prop)
    except Exception:
        frame = None
    return frame if isinstance(frame, pd.DataFrame) and not frame.empty else None


def _rows_from_statement(frame: Optional[pd.DataFrame], annual: bool) -> List[Dict[str, Any]]:
    if frame is None or frame.empty:
        return []

    rev_idx = _pick_index(frame, _REVENUE_KEYS)
    eps_idx = _pick_index(frame, _EPS_KEYS)
    op_idx = _pick_index(frame, _OP_KEYS)
    opm_idx = _pick_index(frame, _OPM_KEYS)
    if rev_idx is None and eps_idx is None and op_idx is None and opm_idx is None:
        return []

    periods = _sorted_periods(frame)
    rows: List[Dict[str, Any]] = []
    for i, col in enumerate(periods):
        revenue = _crore(_number(_value(frame, rev_idx, col))) if rev_idx is not None else None
        eps = _number(_value(frame, eps_idx, col)) if eps_idx is not None else None

        opm = None
        if opm_idx is not None:
            direct_margin = _number(_value(frame, opm_idx, col))
            if direct_margin is not None and abs(direct_margin) <= 100:
                opm = direct_margin
        if opm is None:
            raw_revenue = _number(_value(frame, rev_idx, col)) if rev_idx is not None else None
            raw_op = _number(_value(frame, op_idx, col)) if op_idx is not None else None
            if raw_revenue not in (None, 0) and raw_op is not None:
                opm = raw_op / raw_revenue * 100.0

        prev_col = periods[i - 1] if i > 0 else None
        yoy_col = _yoy_period(periods, i, annual)

        prev_revenue = _crore(_number(_value(frame, rev_idx, prev_col))) if (rev_idx is not None and prev_col is not None) else None
        prev_eps = _number(_value(frame, eps_idx, prev_col)) if (eps_idx is not None and prev_col is not None) else None
        prev_opm = _opm_for(frame, rev_idx, op_idx, opm_idx, prev_col)

        yoy_revenue = _crore(_number(_value(frame, rev_idx, yoy_col))) if (rev_idx is not None and yoy_col is not None) else None
        yoy_eps = _number(_value(frame, eps_idx, yoy_col)) if (eps_idx is not None and yoy_col is not None) else None
        yoy_opm = _opm_for(frame, rev_idx, op_idx, opm_idx, yoy_col)

        rows.append({
            "period": _period_label(col, annual),
            "revenue": revenue,
            "eps": eps,
            "opm": opm,
            "revQoq": _growth(revenue, prev_revenue) if not annual else None,
            "revYoy": _growth(revenue, yoy_revenue),
            "epsQoq": _growth(eps, prev_eps) if not annual else None,
            "epsYoy": _growth(eps, yoy_eps),
            "opmQoq": _delta(opm, prev_opm) if not annual else None,
            "opmYoy": _delta(opm, yoy_opm),
        })
    return rows


def _opm_for(frame: pd.DataFrame, rev_idx: Any, op_idx: Any, opm_idx: Any, col: Any) -> Optional[float]:
    if col is None:
        return None
    if opm_idx is not None:
        direct = _number(_value(frame, opm_idx, col))
        if direct is not None and abs(direct) <= 100:
            return direct
    raw_revenue = _number(_value(frame, rev_idx, col)) if rev_idx is not None else None
    raw_op = _number(_value(frame, op_idx, col)) if op_idx is not None else None
    if raw_revenue not in (None, 0) and raw_op is not None:
        return raw_op / raw_revenue * 100.0
    return None


def _sorted_periods(frame: pd.DataFrame) -> List[Any]:
    columns = list(frame.columns)
    def key(col: Any):
        try:
            return pd.to_datetime(col)
        except Exception:
            return pd.Timestamp.min
    try:
        return sorted(columns, key=key, reverse=True)
    except Exception:
        return columns


def _yoy_period(periods: List[Any], index: int, annual: bool) -> Optional[Any]:
    if index + 1 >= len(periods):
        return None
    current = _as_period(periods[index])
    if current is not None:
        for j in range(index + 1, len(periods)):
            other = _as_period(periods[j])
            if other is None:
                continue
            if annual and other.year == current.year - 1:
                return periods[j]
            if not annual and other.year == current.year - 1 and other.month == current.month:
                return periods[j]
    fallback = index + 1 if annual else index + 4
    return periods[fallback] if fallback < len(periods) else None


def _as_period(value: Any):
    try:
        return pd.to_datetime(value).to_period("M")
    except Exception:
        return None


def _period_label(value: Any, annual: bool) -> str:
    try:
        stamp = pd.to_datetime(value)
        return str(stamp.year) if annual else stamp.strftime("%b %Y")
    except Exception:
        return str(value)[:14]


def _pick_index(frame: pd.DataFrame, keys: tuple) -> Any:
    exact = {}
    for idx in frame.index:
        exact[_normalise(idx)] = idx
    for key in keys:
        found = exact.get(_normalise(key))
        if found is not None:
            return found
    for idx in frame.index:
        name = _normalise(idx)
        if "growth" in name:
            continue
        if any(_normalise(key) in name for key in keys):
            return idx
    return None


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _value(frame: pd.DataFrame, idx: Any, col: Any) -> Any:
    if idx is None or col is None:
        return None
    try:
        return frame.at[idx, col]
    except Exception:
        return None


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number


def _crore(value: Optional[float]) -> Optional[float]:
    return None if value is None else value / 10_000_000.0


def _growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def _delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    return current - previous


# ---------------------------- popup markup ----------------------------

def _modal_html(payload: Dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    symbol = _html.escape(str(payload.get("symbol", "")))
    company = _html.escape(str(payload.get("company", "")))
    return _MODAL_TEMPLATE.replace("__DATA__", data_json).replace("__SYMBOL__", symbol).replace("__COMPANY__", company)


_MODAL_TEMPLATE = r"""<!--MPF_MODAL--><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#fff;--fg:#1f2937;--line:rgba(100,116,139,.30);--soft:rgba(148,163,184,.14);
  --good:#16a34a;--bad:#dc2626;--warn:#d97706;--muted:#64748b;--accent:#2563eb}
html.dark{--good:#34d399;--bad:#f87171;--warn:#fbbf24;--muted:#94a3b8;--accent:#60a5fa}
*{box-sizing:border-box}
html,body{margin:0;padding:0;width:100%;height:100%;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--fg)}
#mpf-overlay{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;padding:18px;z-index:10}
#mpf-backdrop{position:absolute;inset:0;background:rgba(15,23,42,.52)}
#mpf-panel{position:relative;width:min(980px,100%);max-height:88vh;overflow:auto;background:var(--bg);color:var(--fg);
  border:1px solid var(--line);border-radius:14px;box-shadow:0 24px 70px rgba(0,0,0,.35);padding:18px 20px 16px}
#mpf-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
#mpf-head h2{margin:0;font-size:1.15rem;font-weight:800;letter-spacing:.01em}
#mpf-head h2 span{color:var(--muted);font-weight:700;font-size:.82rem}
#mpf-head p{margin:3px 0 0;font-size:.78rem;color:var(--muted);font-weight:600}
#mpf-close{flex:none;width:32px;height:32px;border-radius:50%;border:1px solid var(--line);background:transparent;
  color:var(--fg);font-size:1.15rem;line-height:1;cursor:pointer}
#mpf-close:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
#mpf-controls{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center;margin:0 0 10px}
.grp{display:flex;align-items:center;gap:6px}
.grp>span{font-size:.70rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.seg{display:inline-flex;gap:2px;padding:2px;border:1px solid var(--line);border-radius:999px;background:var(--soft)}
.seg button{border:0;background:transparent;color:var(--muted);border-radius:999px;padding:5px 10px;
  font:700 .75rem/1.2 inherit;cursor:pointer}
.seg button.on{background:var(--bg);color:var(--fg);box-shadow:0 1px 4px rgba(0,0,0,.16)}
#mpf-meta{font-size:.72rem;color:var(--muted);font-weight:600;margin:0 0 8px}
#mpf-table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px}
table{width:100%;border-collapse:collapse;font-size:.78rem;font-variant-numeric:tabular-nums}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:right}
th{position:sticky;top:0;background:var(--bg);font-weight:800;font-size:.71rem;color:var(--muted);z-index:1}
th:first-child,td:first-child{text-align:left;font-weight:800}
tbody tr:hover{background:var(--soft)}
tbody tr:last-child td{border-bottom:0}
.pos{color:var(--good);font-weight:800}.neg{color:var(--bad);font-weight:800}.mut{color:var(--muted);font-weight:700}
.badge{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:20px;padding:0 6px;
  border-radius:999px;font-weight:800;font-size:.74rem}
.badge.good{background:rgba(22,163,74,.16);color:var(--good)}
.badge.bad{background:rgba(220,38,38,.14);color:var(--bad)}
.badge.warn{background:rgba(217,119,6,.16);color:var(--warn)}
.badge.na{background:var(--soft);color:var(--muted)}
.empty{padding:22px 14px;text-align:center;color:var(--muted);font-weight:600;font-size:.84rem}
#mpf-foot{margin:9px 0 0;font-size:.70rem;line-height:1.4;color:var(--muted);font-weight:600}
@media(max-width:640px){
  #mpf-overlay{padding:8px}#mpf-panel{padding:14px 12px;max-height:94vh}
  #mpf-head h2{font-size:1rem}.grp>span{display:none}
  th,td{padding:6px 7px;font-size:.72rem}
}
</style></head><body>
<div id="mpf-overlay" role="dialog" aria-modal="true" aria-label="Fundamentals snapshot">
  <div id="mpf-backdrop"></div>
  <section id="mpf-panel">
    <div id="mpf-head">
      <div><h2>Fundamental snapshot · __SYMBOL__ <span>__COMPANY__</span></h2>
      <p>Quick QoQ / YoY check · EPS, revenue, margin and a simple signal count</p></div>
      <button id="mpf-close" type="button" aria-label="Close fundamentals">×</button>
    </div>
    <div id="mpf-controls">
      <div class="grp"><span>Period</span><div class="seg" id="seg-mode">
        <button type="button" data-group="mode" data-value="quarterly" class="on">Quarterly</button>
        <button type="button" data-group="mode" data-value="annual">Annual</button>
      </div></div>
      <div class="grp"><span>View</span><div class="seg" id="seg-view">
        <button type="button" data-group="view" data-value="qoq">QoQ</button>
        <button type="button" data-group="view" data-value="yoy">YoY</button>
        <button type="button" data-group="view" data-value="both" class="on">Both</button>
      </div></div>
      <div class="grp"><span>Window</span><div class="seg" id="seg-window">
        <button type="button" data-group="window" data-value="4" class="on">Last 4</button>
        <button type="button" data-group="window" data-value="8">Last 8</button>
      </div></div>
    </div>
    <div id="mpf-meta"></div>
    <div id="mpf-table-wrap"></div>
    <p id="mpf-foot">Source: Yahoo Finance via yfinance · unofficial data, may be delayed or incomplete. Missing values show —. Score is a simple count of positive signals, not a rating or recommendation. Data is temporary and session-only.</p>
  </section>
</div>
<script>
const DATA=__DATA__;
const state={mode:'quarterly',view:'both',window:4};
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));

function applyTheme(){
  let bg='#ffffff',fg='#1f2937';
  try{
    const app=parent.document.querySelector('.stApp');
    if(app){const cs=parent.getComputedStyle(app);
      if(cs.backgroundColor && cs.backgroundColor!=='rgba(0, 0, 0, 0)')bg=cs.backgroundColor;
      if(cs.color)fg=cs.color;}
  }catch(e){}
  const nums=s=>(String(s).match(/[\d.]+/g)||[]).map(Number);
  const b=nums(bg),f=nums(fg);
  if(b.length<3||f.length<3){const dark=matchMedia('(prefers-color-scheme: dark)').matches;
    bg=dark?'#0e1117':'#ffffff';fg=dark?'#fafafa':'#1f2937';}
  const bb=nums(bg),ff=nums(fg);
  const dark=(0.299*bb[0]+0.587*bb[1]+0.114*bb[2])<128;
  document.documentElement.style.setProperty('--bg',bg);
  document.documentElement.style.setProperty('--fg',fg);
  document.documentElement.classList.toggle('dark',dark);
}
function closeModal(){
  try{const f=window.frameElement;if(f)f.style.display='none';}catch(e){}
  try{const f=parent.document.getElementById('mpf-modal-frame');if(f)f.style.display='none';}catch(e){}
  try{parent.document.querySelectorAll('iframe[srcdoc*="MPF_MODAL"]').forEach(f=>{if(f!==window.frameElement)f.style.display='none';});}catch(e){}
  const o=$('#mpf-overlay');if(o)o.style.display='none';
}
try{if(window.frameElement){window.frameElement.style.display='block';window.frameElement.style.position='fixed';
  window.frameElement.style.inset='0';window.frameElement.style.width='100vw';window.frameElement.style.height='100vh';
  window.frameElement.style.zIndex='2147483647';}}catch(e){}

function fmtNum(v,d=1){return v==null||isNaN(v)?'—':Number(v).toFixed(d)}
function pct(v){if(v==null||isNaN(v))return '<span class="mut">—</span>';
  const c=v>0?'pos':(v<0?'neg':'mut');return '<span class="'+c+'">'+(v>0?'+':'')+Number(v).toFixed(1)+'%</span>'}
function pp(v){if(v==null||isNaN(v))return '<span class="mut">—</span>';
  const c=v>0?'pos':(v<0?'neg':'mut');return '<span class="'+c+'">'+(v>0?'+':'')+Number(v).toFixed(1)+' pp</span>'}
function badge(kind,text){return '<span class="badge '+kind+'">'+text+'</span>'}
function pairs(){return state.mode==='annual'?[['revYoy','epsYoy']]:[['revQoq','epsQoq'],['revYoy','epsYoy']]}
function bothState(r){
  const ps=pairs();let good=0,bad=0,mixed=0,valid=0;
  ps.forEach(p=>{const a=r[p[0]],b=r[p[1]];
    if(a!=null&&b!=null)valid++;
    if(a!=null&&b!=null&&a>0&&b>0)good++;
    else if(a!=null&&b!=null&&a<0&&b<0)bad++;
    else mixed++;});
  if(!valid)return badge('na','—');
  if(good===ps.length)return badge('good','✓');
  if(bad===ps.length)return badge('bad','✕');
  return badge('warn','~');
}
function score(r){
  const keys=state.mode==='annual'?['revYoy','epsYoy','opmYoy']:
    (state.view==='qoq'?['revQoq','epsQoq','opmQoq']:
     state.view==='yoy'?['revYoy','epsYoy','opmYoy']:
     ['revQoq','epsQoq','revYoy','epsYoy','opmQoq','opmYoy']);
  const usable=keys.filter(k=>r[k]!=null);
  if(!usable.length)return badge('na','—');
  const hit=usable.filter(k=>r[k]>0).length;
  const kind=hit===usable.length?'good':(hit===0?'bad':'warn');
  return badge(kind,hit+'/'+usable.length);
}
function columns(){
  const c=[{k:'period',t:'Period',f:v=>esc(v)},
           {k:'revenue',t:'Revenue ₹ Cr',f:v=>fmtNum(v,1)}];
  const incQ=state.mode!=='annual'&&(state.view==='qoq'||state.view==='both');
  const incY=state.mode==='annual'||state.view==='yoy'||state.view==='both';
  if(incQ)c.push({k:'revQoq',t:'Revenue QoQ %',f:pct});
  if(incY)c.push({k:'revYoy',t:'Revenue YoY %',f:pct});
  c.push({k:'eps',t:'EPS ₹',f:v=>fmtNum(v,2)});
  if(incQ)c.push({k:'epsQoq',t:'EPS QoQ %',f:pct});
  if(incY)c.push({k:'epsYoy',t:'EPS YoY %',f:pct});
  c.push({k:'opm',t:'OPM %',f:v=>fmtNum(v,1)});
  if(incQ)c.push({k:'opmQoq',t:'OPM Δ QoQ',f:pp});
  if(incY)c.push({k:'opmYoy',t:'OPM Δ YoY',f:pp});
  c.push({k:'both',t:'Both',f:bothState,raw:true},
         {k:'score',t:'Score',f:score,raw:true});
  return c;
}
function syncControls(){
  ['mode','view','window'].forEach(g=>{
    document.querySelectorAll('button[data-group="'+g+'"]').forEach(b=>{
      b.classList.toggle('on',String(b.dataset.value)===String(state[g]));
    });});
  document.querySelectorAll('button[data-group="window"]').forEach(b=>{
    b.textContent=state.mode==='annual'?('Last '+b.dataset.value+' yrs'):('Last '+b.dataset.value);
  });
}
function renderTable(){
  if(DATA.error){$('#mpf-table-wrap').innerHTML='<div class="empty">'+esc(DATA.error)+'</div>';return;}
  let rows=(DATA[state.mode]||[]).slice(0,state.window);
  if(!rows.length){$('#mpf-table-wrap').innerHTML='<div class="empty">No usable periods returned by Yahoo Finance for this view.</div>';return;}
  const cols=columns();
  let h='<table><thead><tr>'+cols.map(c=>'<th title="'+esc(c.t)+'">'+esc(c.t)+'</th>').join('')+'</tr></thead><tbody>';
  rows.forEach(r=>{h+='<tr>'+cols.map(c=>'<td>'+(c.raw?c.f(r):c.f(r[c.k]))+'</td>').join('')+'</tr>';});
  h+='</tbody></table>';
  $('#mpf-table-wrap').innerHTML=h;
  const label=state.mode==='annual'?'annual periods':'quarters';
  $('#mpf-meta').textContent=(DATA.yahoo_symbol||DATA.symbol)+' · '+label+' newest first · fetched '+esc(DATA.as_of||'')+
    (DATA.from_session_cache?' · session cache':' · fetched on click');
}
document.getElementById('mpf-controls').addEventListener('click',e=>{
  const b=e.target.closest('button[data-group]');if(!b)return;
  state[b.dataset.group]=b.dataset.group==='window'?parseInt(b.dataset.value,10):b.dataset.value;
  if(state.mode==='annual'&&state.view==='qoq')state.view='yoy';
  syncControls();renderTable();
});
$('#mpf-close').addEventListener('click',closeModal);
$('#mpf-backdrop').addEventListener('click',closeModal);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
applyTheme();syncControls();renderTable();
</script></body></html>"""
