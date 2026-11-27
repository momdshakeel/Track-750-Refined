"""Shared, Streamlit-free Master List engine.

The app and the weekly GitHub job both use this module so the 11 source tags,
weights and confluence tiers stay identical. No network calls, no file writes.
"""
import re

import numpy as np
import pandas as pd

import nse500_rs_rating as m


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


def _vcp_breakout_frame(frame):
    """Fresh VCP pivot crosses that are still trending up."""
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
    pivot_pct = num("Pct_To_Pivot")
    above_pivot = pivot_pct < 0 if pivot_pct.notna().any() else (num("Close") > num("Pivot"))
    stage2 = num("Stage_Num") == 2
    rs_up = out.get("RS_Line_Uptrend", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    above50 = num("Pct_Above_50SMA") > 0
    out = out.assign(_rs_sort=num("RS_Rating"))
    return (out[fresh & above_pivot & stage2 & rs_up & above50]
            .sort_values(["VCP_Breakout_Days_Ago", "_rs_sort"], ascending=[True, False])
            .drop(columns="_rs_sort"))


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
    is_pro = bool(cfg.get("pro", False))
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

    pro_extra = pd.Series(True, index=idx)
    vcp_legs, vcp_step = _vcp_contraction_stats(
        out.get("VCP_Contractions", pd.Series("", index=idx)))
    if is_pro:
        pro_extra &= num("Close") >= 30
        pro_extra &= num("Pct_From_52W_High") >= -25
        pro_extra &= num("Pct_Above_52W_Low") >= 100
        pro_extra &= num("TT_Score") >= 8
        if "SMA200_Rising_63D" in out.columns:
            pro_extra &= _series_flag(out["SMA200_Rising_63D"], idx)
        else:
            pro_extra &= flag("TT3_200SMA_up")
        if "High_52W_Recent_6M" in out.columns:
            pro_extra &= _series_flag(out["High_52W_Recent_6M"], idx)

    market_ok = bool(flag("Market_Trend_OK").all()) if "Market_Trend_OK" in out.columns else True
    rs, tt, sec = num("RS_Rating"), num("TT_Score"), num("Sector_Strength")
    above50, pct = num("Pct_Above_50SMA"), num("Pct_To_Pivot")
    vol_min = getattr(m, "BREAKOUT_VOL_X", 1.5)

    vcp_days = num("VCP_Breakout_Days_Ago") if "VCP_Breakout_Days_Ago" in out.columns else pd.Series(np.nan, index=idx)
    gen_days = num("Breakout_Days_Ago")
    vol_x = num("Breakout_Vol_x").fillna(num("VCP_Breakout_Vol_x"))
    vcp_fresh = vcp_days.notna() & (vcp_days <= cfg["brk"]) & (pct < 0) & (vol_x >= vol_min)
    gen_fresh = (gen_days.notna() & (gen_days <= cfg["brk"]) & flag("Vol_Breakout")
                 & (vol_x >= vol_min) & ~(pct.notna() & (pct >= 0)))
    break_days = vcp_days.where(vcp_fresh, gen_days.where(gen_fresh))
    fresh = break_days.notna()

    dry = (flag("VCP_Setup") | flag("Vol_Dry_Up") | flag("VCP") | flag("VCP_Vol_Contracting"))
    at_pivot = (pct >= 0) & (pct <= cfg["pivot"]) & dry

    quality = (flag("Liquid") & (num("Stage_Num") == 2) & (rs >= cfg["rs"]) & (tt >= cfg["tt"])
               & (sec >= cfg["sec"]) & (above50 > 0) & (above50 <= cfg["ext"]) & flag("RS_Line_Uptrend"))
    keep = quality & (fresh | at_pivot) & market_ok
    if is_pro:
        keep &= pro_extra

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
    score -= pd.Series(np.select([above50 > 15, above50 > 12, above50 > 9],
                                 [10, 6, 3], default=0), index=idx)

    if is_pro:
        score += pd.Series(np.select([vcp_legs >= 3, vcp_legs == 2], [6, 3], default=0), index=idx)
        score += pd.Series(np.select([vcp_step <= 0.5, vcp_step <= 0.7], [5, 2], default=0), index=idx)
        score += (flag("VCP_Vol_Contracting") | flag("Vol_Dry_Up")).astype(int) * 3
        score += pressure.str.contains("Up-volume", na=False).astype(int) * 2
        score += (num("Green_Days_20D") > num("Red_Days_20D")).astype(int) * 2

    close, pivot, sma50 = num("Close"), num("Pivot"), num("SMA50")
    stop = (pivot * 0.92).where(pivot > 0, sma50 * 0.95)
    if is_pro and "ATR_Stop_Distance_%" in out.columns:
        atr_stop = close * (1 - num("ATR_Stop_Distance_%") / 100)
        stop = atr_stop.where(atr_stop.notna(), stop)
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
        if is_pro:
            bits.append("Minervini Pro")
            if int(vcp_legs.loc[sym]) >= 3:
                bits.append("3 VCP legs")
            if pd.notna(vcp_step.loc[sym]) and float(vcp_step.loc[sym]) <= 0.5:
                bits.append("50% tightening")
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
    # --- DARVAS BOX START (rollback-safe: Master List tag) ---
    "Darvas Box": 10,
    # --- DARVAS BOX END ---
}

MASTER_SOURCE_LABELS = [
    "Top Picks", "Momentum Leader", "Trend Template", "VCP Setup", "VCP Breakout",
    # --- DARVAS BOX START (rollback-safe: Master List tag) ---
    "Darvas Box",
    # --- DARVAS BOX END ---
    "Entry Candidates", "Volume Breakout", "Stage 1 Bases", "RS Blue Dot", "Minervini Pro",
]


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


def build_master_list(frame, pref_rs=None, rsi_min=50, entry_preset="Balanced"):
    """Build the same 11-tag Master List as the app, without Streamlit state."""
    if frame is None or frame.empty:
        return frame
    df = frame.copy()
    idx = df.index

    def num(col):
        return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=idx)

    def flag(col):
        return _series_flag(df[col], idx) if col in df.columns else pd.Series(False, index=idx)

    pref = int(pref_rs if pref_rs is not None else getattr(m, "PREFERRED_RS", 80))

    top = df[flag("TT_Pass") & (num("RS_Rating") >= pref)
             & flag("RS_Line_Near_High") & (num("RSI14") > rsi_min)]
    tt = df[flag("TT_Pass")]
    blue = df[flag("RS_Blue_Dot") & (num("RS_Rating") >= pref)]
    vcp = df[flag("VCP_Setup")].sort_values("Pct_To_Pivot") if "Pct_To_Pivot" in df else df[flag("VCP_Setup")]
    brk = df[flag("Vol_Breakout")]
    if {"Breakout_Days_Ago", "Breakout_Vol_x"}.issubset(df.columns):
        brk = brk.sort_values(["Breakout_Days_Ago", "Breakout_Vol_x"], ascending=[True, False])
    s1 = df[flag("Stage1_Base")]
    s1 = s1.sort_values("Base_Days", ascending=False) if "Base_Days" in df else s1

    momentum_required = ["Pct_From_52W_High", "Pct_Above_50SMA", "Base_Forming",
                         "Base_Depth_%", "Pct_To_Pivot", "RS_Line_Near_High", "Market_Trend_OK"]
    if all(field in df.columns for field in momentum_required):
        market_ok = bool(flag("Market_Trend_OK").all())
        momentum = df[
            (num("Pct_From_52W_High") >= -25)
            & (num("Pct_Above_50SMA") >= 0)
            & flag("Base_Forming")
            & (num("Base_Depth_%") <= 20)
            & (num("Pct_To_Pivot") >= 0)
            & (num("Pct_To_Pivot") <= 10.0)
            & flag("RS_Line_Near_High")
        ].copy()
        if not market_ok:
            momentum = momentum.iloc[0:0]
        momentum = momentum.sort_values(["Pct_To_Pivot", "RS_Rating"], ascending=[True, False])
    else:
        momentum = df.iloc[0:0].copy()

    darvas_columns = {"Darvas_OK", "Darvas_Box_Top", "Darvas_Box_Bottom"}
    darvas = df[flag("Darvas_OK")].copy() if darvas_columns.issubset(df.columns) else df.iloc[0:0].copy()

    sources = [
        ("Top Picks", top, CONFLUENCE_WEIGHTS["Top Picks"]),
        ("Momentum Leader", momentum, CONFLUENCE_WEIGHTS["Momentum Leader"]),
        ("Trend Template", tt, CONFLUENCE_WEIGHTS["Trend Template"]),
        ("VCP Setup", vcp, CONFLUENCE_WEIGHTS["VCP Setup"]),
        ("VCP Breakout", _vcp_breakout_frame(df), CONFLUENCE_WEIGHTS["VCP Breakout"]),
        # --- DARVAS BOX START (rollback-safe: Master List tag) ---
        ("Darvas Box", darvas, CONFLUENCE_WEIGHTS["Darvas Box"]),
        # --- DARVAS BOX END ---
        ("Entry Candidates", _entry_candidates(df, entry_preset), CONFLUENCE_WEIGHTS["Entry Candidates"]),
        ("Volume Breakout", brk, CONFLUENCE_WEIGHTS["Volume Breakout"]),
        ("Stage 1 Bases", s1, CONFLUENCE_WEIGHTS["Stage 1 Bases"]),
        ("RS Blue Dot", blue, CONFLUENCE_WEIGHTS["RS Blue Dot"]),
        ("Minervini Pro", _entry_candidates(df, "Minervini Pro"), CONFLUENCE_WEIGHTS["Minervini Pro"]),
    ]
    return _build_confluence_frame(df, sources)
# --- MASTER LIST END ---
