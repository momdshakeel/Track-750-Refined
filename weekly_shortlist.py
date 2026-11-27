"""Sunday-only Weekly Shortlist job.

Reads the saved daily scan (data/latest.csv) and the shared Master List engine,
picks the strongest names, and keeps 13 Sunday snapshots in
data/weekly/weekly_shortlist.json. No Yahoo fetch and no Streamlit dependency.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

import master_engine
import nse500_rs_rating as m

DATA_DIR = "data"
OUT_DIR = os.path.join(DATA_DIR, "weekly")
OUT_FILE = os.path.join(OUT_DIR, "weekly_shortlist.json")
IST = timezone(timedelta(hours=5, minutes=30))
KEEP_SNAPSHOTS = 13          # roughly three months of Sunday lists
DEFAULT_SIZE = 20            # top 20; override with WEEKLY_SHORTLIST_SIZE=10


def _value(value):
    """Convert numpy scalars into plain JSON values."""
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def _number(value):
    if pd.isna(value):
        return None
    return round(float(value), 2)


def _integer(value):
    if pd.isna(value):
        return None
    return int(value)


def _text(value):
    if pd.isna(value):
        return ""
    return str(value)


def build_snapshot(frame, info, selection_date, size):
    """Rank the Master List and return one JSON-ready snapshot."""
    master = master_engine.build_master_list(frame)
    if master.empty:
        raise RuntimeError("Master List is empty; refusing to write an empty weekly shortlist.")

    sort_columns = [c for c in ("Confluence_Score", "RS_Rating", "Filter_Count") if c in master.columns]
    ranked = master.sort_values(sort_columns, ascending=[False] * len(sort_columns)).head(size)

    rows = []
    for _, row in ranked.iterrows():
        close = _number(row.get("Close"))
        rows.append({
            "Symbol": _text(row.get("Symbol")),
            "Company Name": _text(row.get("Company Name")),
            "Sector": _text(row.get("Sector")),
            "Confluence_Score": _integer(row.get("Confluence_Score")),
            "Tier": _text(row.get("Tier")),
            "Filter_Count": _integer(row.get("Filter_Count")),
            "In_Filters": _text(row.get("In_Filters")),
            "RS_Rating": _integer(row.get("RS_Rating")),
            "TT_Score": _integer(row.get("TT_Score")),
            "Stage": _text(row.get("Stage")),
            "Close": close,
            "Close_At_Selection": close,
            "Gain_Since_Selection_%": 0.0 if close is not None else None,
            "Selection_Date": selection_date,
        })

    return {
        "date": selection_date,
        "scan_date": _text(info.get("as_of"))[:10],
        "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
        "size": len(rows),
        "source": "Master List (11 scanner filters)",
        "rows": rows,
    }


def main():
    size = max(1, min(50, int(os.environ.get("WEEKLY_SHORTLIST_SIZE", DEFAULT_SIZE))))
    frame, info = m.load_saved_results(DATA_DIR)
    selection_date = datetime.now(IST).date().isoformat()
    snapshot = build_snapshot(frame, info, selection_date, size)

    os.makedirs(OUT_DIR, exist_ok=True)
    history = {"retention_weeks": KEEP_SNAPSHOTS, "snapshots": []}
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded.get("snapshots"), list):
                history["snapshots"] = loaded["snapshots"]
        except (OSError, ValueError, AttributeError):
            pass

    # A manual re-run on the same Sunday replaces that snapshot instead of duplicating it.
    history["snapshots"] = [item for item in history["snapshots"]
                            if str(item.get("date"))[:10] != selection_date]
    history["snapshots"].append(snapshot)
    history["snapshots"] = sorted(history["snapshots"], key=lambda s: str(s.get("date")), reverse=True)[:KEEP_SNAPSHOTS]
    history["updated_at"] = snapshot["generated_at"]

    temp_file = OUT_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(temp_file, OUT_FILE)

    top_names = ", ".join(row["Symbol"] for row in snapshot["rows"][:5]) or "none"
    print(f"Weekly shortlist {selection_date}: {len(snapshot['rows'])} names from "
          f"{snapshot['scan_date']} scan; kept {len(history['snapshots'])} snapshots.")
    print(f"Top 5: {top_names}")


if __name__ == "__main__":
    main()
