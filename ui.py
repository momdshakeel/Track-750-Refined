"""Look & feel for the NSE 500 scanner: fonts, global CSS, hero, KPI cards and
sortable, responsive HTML tables that follow Streamlit's light/dark theme."""
import json
import hashlib
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_TABLE_COMPONENT = components.declare_component(
    "marketpulse_result_table", path=str(Path(__file__).with_name("table_component"))
)

# ---------------------------------------------------------------- fonts
FONTS = {
    "Inter": "Inter",
    "Poppins": "Poppins",
    "DM Sans": "DM Sans",
    "Manrope": "Manrope",
    "IBM Plex Sans": "IBM Plex Sans",
    "Space Grotesk": "Space Grotesk",
    "Source Sans 3": "Source Sans 3",
    "System default": None,
}
_FALLBACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"


def font_url(name: str) -> str:
    fam = FONTS.get(name)
    if not fam:
        return ""
    return (f"https://fonts.googleapis.com/css2?family={fam.replace(' ', '+')}"
            f":wght@400;500;600;700&display=swap")


def font_family(name: str) -> str:
    fam = FONTS.get(name)
    return f"'{fam}', {_FALLBACK}" if fam else _FALLBACK


# ---------------------------------------------------------------- page CSS
# Two complete in-app palettes. The selected one is written into the stylesheet on
# every rerun, so the theme toggle needs no JavaScript and works in embedded charts/
# tables too (they read the computed .stApp background and text colour).
_THEMES = {
    "light": dict(
        BG="#f4f7fc", SURFACE="#ffffff", SURFACE2="#eef3fa", TEXT="#101c30",
        MUTED="#60728d", LINE="#d9e3f0", ACCENT="#0284c7", ACCENT2="#7c3aed",
        GOOD="#059669", BAD="#e11d48", SHADOW="rgba(16,28,48,.09)",
        GLOW="rgba(2,132,199,.11)", HEROA="#e2f4ff", HEROB="#efe9ff"),
    "dark": dict(
        BG="#0a1120", SURFACE="#111c2e", SURFACE2="#18273e", TEXT="#e8f0ff",
        MUTED="#96a9c6", LINE="#2a3d5c", ACCENT="#22d3ee", ACCENT2="#a78bfa",
        GOOD="#34d399", BAD="#fb7185", SHADOW="rgba(0,0,0,.38)",
        GLOW="rgba(34,211,238,.13)", HEROA="#102b40", HEROB="#251d46"),
}

_PAGE_CSS = """
<style>
__IMPORT__
:root{
 --ui-font:__FAMILY__;
 --mp-bg:__BG__;--mp-surface:__SURFACE__;--mp-surface2:__SURFACE2__;
 --mp-text:__TEXT__;--mp-muted:__MUTED__;--mp-line:__LINE__;
 --mp-accent:__ACCENT__;--mp-accent2:__ACCENT2__;
 --mp-good:__GOOD__;--mp-bad:__BAD__;--mp-shadow:__SHADOW__;
 --mp-glow:__GLOW__;--mp-hero-a:__HEROA__;--mp-hero-b:__HEROB__;
 --accent:var(--mp-accent);--accent2:var(--mp-accent2);
 --line:var(--mp-line);--soft:var(--mp-surface2);
 --brand:var(--mp-accent);--muted:var(--mp-muted);
 color-scheme:__SCHEME__;
}
.stApp,[data-testid="stAppViewContainer"],header[data-testid="stHeader"]{
 background:var(--mp-bg)!important;color:var(--mp-text)!important}
section[data-testid="stSidebar"]{background:var(--mp-surface)!important;color:var(--mp-text)!important;
 border-right:1px solid var(--mp-line)!important}
.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp td,.stApp th,
[data-testid="stMarkdownContainer"],.stText,.stCaption,[data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"] p{color:var(--mp-text)}
.stApp div,.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,
.stApp input,.stApp textarea,.stApp button,.stApp a,.stApp td,.stApp th{font-family:var(--ui-font)!important}
div[data-baseweb="select"]>div,.stTextInput input,.stNumberInput input,.stTextArea textarea{
 background:var(--mp-surface)!important;color:var(--mp-text)!important;
 border:1px solid var(--mp-line)!important;border-radius:11px!important}
.stButton>button,.stDownloadButton>button{background:var(--mp-surface)!important;color:var(--mp-text)!important;
 border:1px solid var(--mp-line)!important}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--mp-accent)!important;color:var(--mp-accent)!important}
.stButton>button[kind="primary"]{background:linear-gradient(120deg,var(--mp-accent),var(--mp-accent2))!important;
 color:#fff!important;border:0!important}
.stDivider{border-color:var(--mp-line)!important}
.st-key-theme-toggle button{padding:.1rem .5rem!important;min-height:32px!important;font-size:.85rem!important}
.block-container{width:100%;padding:1.4rem clamp(.8rem,2.2vw,2rem) 3rem!important;max-width:1600px}
header[data-testid="stHeader"]{background:transparent}
footer{visibility:hidden}
[data-testid="stAppDeployButton"],.stAppDeployButton{display:none!important}
div[data-testid="stElementContainer"]:has(> div > style),.element-container:has(> style){display:none}

/* hero */
.hero{position:relative;overflow:hidden;display:flex;justify-content:space-between;align-items:center;gap:10px;
flex-wrap:wrap;margin:1px 0 11px;padding:16px 18px;border:1px solid var(--mp-line);border-radius:18px;
