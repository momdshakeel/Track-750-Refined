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
/* Readable captions / info notes under charts and tables, in both themes */
.stCaption,[data-testid="stCaptionContainer"],.stCaption p,[data-testid="stCaptionContainer"] p{
 color:var(--mp-text)!important;font-weight:600!important;font-size:.82rem!important;line-height:1.45!important;opacity:1!important}
div[data-testid="stAlert"] p,div[data-testid="stAlert"] [data-testid="stMarkdownContainer"]{
 color:var(--mp-text)!important;font-weight:600!important;opacity:1!important}
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
background:linear-gradient(115deg,var(--mp-hero-a) 0%,var(--mp-surface) 58%,var(--mp-hero-b) 100%);
box-shadow:0 10px 28px var(--mp-shadow)}
.hero:after{content:"";position:absolute;right:-40px;top:-70px;width:240px;height:240px;border-radius:50%;
background:radial-gradient(circle,var(--mp-glow),transparent 68%);pointer-events:none}
.eyebrow{font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:var(--mp-accent);font-weight:800}
.title{font-size:clamp(1.5rem,2.4vw,2.05rem);font-weight:800;line-height:1.08;margin:.2rem 0 .3rem;
background:linear-gradient(90deg,var(--mp-accent),var(--mp-accent2));-webkit-background-clip:text;
background-clip:text;color:transparent!important;-webkit-text-fill-color:transparent;letter-spacing:-.035em}
.sub{color:var(--mp-muted);font-size:.8rem;max-width:1000px;line-height:1.35}
.chips{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-start;position:relative;z-index:1}
.chip{border:1px solid var(--mp-line);background:var(--mp-surface);border-radius:999px;padding:4px 10px;
font-size:.68rem;white-space:nowrap;color:var(--mp-muted);box-shadow:0 2px 8px var(--mp-shadow)}
.chip b{color:var(--mp-text);font-weight:700}

/* KPI cards */
.kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:0}
.kpi{position:relative;overflow:hidden;border:1px solid var(--mp-line);border-radius:15px;padding:12px 13px 11px 15px;
min-width:0;background:linear-gradient(155deg,var(--mp-surface),var(--mp-surface2));
box-shadow:0 5px 16px var(--mp-shadow);transition:transform .18s ease,box-shadow .18s ease}
.kpi:hover{transform:translateY(-2px);box-shadow:0 12px 24px var(--mp-shadow)}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
background:linear-gradient(180deg,var(--mp-accent),var(--mp-accent2))}
.kpi .ic{position:absolute;right:9px;top:9px;width:27px;height:27px;border-radius:9px;background:var(--mp-glow);
display:grid;place-items:center;font-size:.92rem;line-height:1}
.kpi .l{font-size:.63rem;letter-spacing:.07em;text-transform:uppercase;color:var(--mp-muted);font-weight:750;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:28px}
.kpi .v{font-size:1.5rem;font-weight:750;line-height:1.1;margin-top:5px;color:var(--mp-text);letter-spacing:-.02em}
.kpi .s{font-size:.66rem;color:var(--mp-muted);margin-top:3px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* tabs as pills (works with old and new Streamlit tab markup) */
[role="tablist"]{gap:8px!important;overflow-x:auto;border-bottom:none!important;box-shadow:none!important;
padding:3px 2px 11px;scrollbar-width:thin;scroll-snap-type:x proximity}
@media (min-width:900px){[role="tablist"]{flex-wrap:wrap!important;overflow:visible!important}}
[role="tablist"] [role="tab"]{border-radius:12px!important;padding:8px 17px!important;height:auto!important;
white-space:nowrap;flex-shrink:0;scroll-snap-align:start;background:var(--mp-surface2)!important;
border:1px solid var(--mp-line)!important;cursor:pointer}
[role="tablist"] [role="tab"] p{font-size:.88rem;font-weight:650;margin:0}
[role="tablist"] [role="tab"][aria-selected="true"]{
 background:linear-gradient(120deg,var(--mp-accent),var(--mp-accent2))!important;border-color:transparent!important;
 box-shadow:0 6px 16px var(--mp-shadow)}
[role="tablist"] [role="tab"][aria-selected="true"] p{color:#fff!important}
.react-aria-SelectionIndicator,[data-baseweb="tab-highlight"],[data-baseweb="tab-border"]{display:none!important}

/* sidebar + widgets */
section[data-testid="stSidebar"]{border-right:1px solid var(--line)}
section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3{font-size:1rem;letter-spacing:-.01em}
.stButton>button,.stDownloadButton>button{border-radius:10px;border:1px solid var(--line);font-weight:600}
.stDownloadButton>button{background:var(--soft)}
div[data-baseweb="select"]>div,.stTextInput input{border-radius:10px!important}
.meters{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:6px 0 18px}
.meter{border:1px solid var(--line);background:var(--soft);border-radius:14px;padding:12px 15px 11px}
.meter .mh{display:flex;justify-content:space-between;align-items:baseline;font-size:.8rem;font-weight:600}
.meter .mh b{font-size:1.25rem;letter-spacing:-.01em}
.meter .mt{height:8px;border-radius:99px;background:var(--line);margin-top:8px;overflow:hidden}
.meter .mf{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.meter .mn{font-size:.72rem;opacity:.6;margin-top:6px}
.advdec{display:flex;height:14px;border-radius:99px;overflow:hidden;margin:6px 0 4px;background:var(--line)}
.advdec .a{background:#10b981}.advdec .d{background:#ef4444}
.advlbl{display:flex;justify-content:space-between;font-size:.8rem;font-weight:600;margin-bottom:14px}
.tabnote{opacity:.72;font-size:.88rem;line-height:1.5;margin:2px 0 6px;max-width:1000px;overflow-wrap:anywhere}
.tabnote b{font-weight:600}
.screen-info{display:flex;flex-direction:column;justify-content:center;min-height:72px;padding:4px 2px}
.screen-info .kicker{font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;opacity:.55;font-weight:700}
.screen-info .heading{font-size:1.05rem;font-weight:700;line-height:1.2;margin:3px 0}
.screen-info .description{font-size:.82rem;line-height:1.4;opacity:.7}
.st-key-screen-library-control{padding:8px 10px 1px;border-radius:12px;
background:linear-gradient(110deg,color-mix(in srgb,var(--accent) 10%,var(--soft)),var(--soft));
border:1px solid color-mix(in srgb,var(--accent) 26%,var(--line))}
.st-key-screen-library-control [data-baseweb="select"]>div{
background:color-mix(in srgb,var(--accent) 5%,var(--soft))!important;
border-color:color-mix(in srgb,var(--accent) 38%,var(--line))!important}
.st-key-screen-library-control [data-baseweb="select"]:hover>div{
border-color:color-mix(in srgb,var(--accent) 58%,var(--line))!important}
div[data-testid="stSelectbox"] label{font-size:.76rem!important;font-weight:700!important;letter-spacing:.02em}
div[data-testid="stSelectbox"] [data-baseweb="select"]>div{min-height:44px!important}

/* ---- dashboard chrome: header, pills, tabs, view row ---- */
[data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"]{gap:.95rem}
.mp-brand{position:relative;overflow:hidden;padding:14px 17px;border:1px solid var(--mp-line);border-radius:17px;
background:linear-gradient(120deg,var(--mp-hero-a),var(--mp-surface) 62%,var(--mp-hero-b));
box-shadow:0 8px 22px var(--mp-shadow)}
.mp-brand:after{content:"";position:absolute;right:-30px;top:-45px;width:190px;height:190px;border-radius:50%;
background:radial-gradient(circle,var(--mp-glow),transparent 68%);pointer-events:none}
.mp-brand h1{margin:0;padding:0;font-size:1.5rem;line-height:1.15;font-weight:800;letter-spacing:-.03em;
display:flex;align-items:center;gap:10px;color:var(--mp-text);position:relative;z-index:1}
.mp-brand h1 .mp-mark{width:34px;height:34px;border-radius:11px;flex:none;display:grid;place-items:center;color:#fff;
background:linear-gradient(135deg,var(--mp-accent),var(--mp-accent2));box-shadow:0 5px 14px var(--mp-shadow)}
.mp-brand .tag{font-size:.64rem;letter-spacing:.17em;text-transform:uppercase;color:var(--mp-accent);font-weight:800;
margin:4px 0 2px;position:relative;z-index:1}
.mp-brand p{margin:2px 0 0;font-size:.79rem;line-height:1.35;color:var(--mp-muted);position:relative;z-index:1}
.st-key-top_stock_search [data-baseweb="select"]>div,.st-key-top_stock_search input{border-radius:11px!important}
.st-key-top_stock_search{min-width:0}
.pillrow{display:flex;gap:7px;overflow-x:auto;scrollbar-width:none;padding:2px 0;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch}
.pillrow::-webkit-scrollbar{display:none}
.pillrow span{flex:none;white-space:nowrap;border:1px solid var(--mp-line);background:var(--mp-surface);
padding:6px 12px;border-radius:999px;font-size:.75rem;color:var(--mp-muted);box-shadow:0 2px 8px var(--mp-shadow)}
.pillrow b{color:var(--mp-text);font-weight:750}
.st-key-screen-tabs [data-testid="stElementContainer"]{width:100%!important}
.st-key-screen-tabs [role="radiogroup"]{display:flex!important;flex-wrap:nowrap!important;gap:7px!important;width:100%;overflow-x:auto;
scrollbar-width:none;padding:5px!important;border:1px solid var(--mp-line);border-radius:15px;
background:var(--mp-surface);box-shadow:0 4px 14px var(--mp-shadow)}
.st-key-screen-tabs [role="radiogroup"]::-webkit-scrollbar{display:none}
.st-key-screen-tabs button{flex:none;background:transparent!important;border:1px solid transparent!important;border-radius:10px!important;
box-shadow:none!important;padding:8px 14px!important;min-height:0!important;color:var(--mp-muted)!important;white-space:nowrap}
.st-key-screen-tabs button p{font-size:.82rem!important;font-weight:650!important;margin:0}
.st-key-screen-tabs button:hover{color:var(--mp-accent)!important;background:var(--mp-surface2)!important}
.st-key-screen-tabs button[data-testid$="Active"],.st-key-screen-tabs button[aria-checked="true"],.st-key-screen-tabs button[aria-pressed="true"]{
color:#fff!important;background:linear-gradient(120deg,var(--mp-accent),var(--mp-accent2))!important;border-color:transparent!important;
box-shadow:0 5px 14px var(--mp-shadow)}
.st-key-screen-tabs button[data-testid$="Active"] p,.st-key-screen-tabs button[aria-checked="true"] p,
.st-key-screen-tabs button[aria-pressed="true"] p{color:#fff!important}
.viewhead{line-height:1.35;position:relative}
[data-testid="stMarkdownContainer"]:has(>.viewhead),[data-testid="stMarkdownContainer"]:has(>.mp-brand){margin-bottom:0!important}
.viewhead>b{font-size:1.02rem;font-weight:750}
.viewhead .cnt{display:inline-block;margin-left:9px;padding:2px 10px;border-radius:999px;font-size:.75rem;
font-weight:750;color:var(--mp-accent);background:var(--mp-glow);border:1px solid var(--mp-line);
vertical-align:1px;white-space:nowrap}
.viewhead .vd{margin-left:8px;font-size:.82rem;color:var(--muted)}
.viewhead .vd:before{content:"· "}
.viewhead .i{display:inline-block;width:15px;height:15px;margin-left:8px;border:1px solid color-mix(in srgb,currentColor 50%,transparent);
border-radius:50%;font:italic 700 10px/13px Georgia,serif;text-align:center;vertical-align:1px;cursor:pointer;outline:0;opacity:.75}
.viewhead .i:hover,.viewhead .i:focus{opacity:1;background:color-mix(in srgb,currentColor 12%,transparent)}
.viewhead .tip{display:none;position:absolute;left:0;top:calc(100% + 8px);width:min(560px,92vw);max-height:min(72vh,560px);overflow-y:auto;padding:11px 13px;border-radius:8px;
background:#1f2937;color:#f3f4f6;font:400 .8rem/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;font-style:normal;text-align:left;
z-index:90;box-shadow:0 8px 24px rgba(0,0,0,.3);cursor:default}
.viewhead .i:hover .tip,.viewhead .i:focus .tip{display:block}
.viewhead .tip .th{display:block;font-weight:700;font-size:.84rem;color:#fff;margin-bottom:5px}
.viewhead .tip .ln{display:block;margin-top:5px}
.viewhead .tip b{color:#fff}
.st-key-view-row button{border-radius:6px!important;min-height:34px!important;padding:.15rem .65rem!important;font-size:.8rem;border:1px solid var(--line)!important;background:transparent}
.st-key-view-row button p{font-size:.8rem!important;font-weight:600}
@media (max-width:640px){
  .st-key-view-row [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.4rem}
  .st-key-view-row [data-testid="stColumn"]{min-width:0!important;flex:1 1 calc(50% - .4rem)!important;width:auto!important}
  .st-key-view-row [data-testid="stColumn"]:first-child,.st-key-view-row [data-testid="stColumn"]:nth-child(2){flex-basis:100%!important}
  .st-key-screen-tabs [role="radiogroup"]{gap:16px!important}
  .mp-brand h1{font-size:1.15rem}
  .st-key-view-row button{padding:.15rem .4rem!important}
  .st-key-view-row button p{font-size:.74rem!important}
}
@media (max-width:1100px) and (min-width:641px){.kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:900px){.sub{max-width:100%}.kpis{gap:8px}}
@media (max-width:640px){
  .screen-info{min-height:0;padding:0 2px}
  div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.5rem!important}
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]{flex:1 1 100%!important;width:auto!important;min-width:0!important}
  .st-key-view-row div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]{flex:1 1 calc(50% - .4rem)!important}
  .st-key-view-row div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child,
  .st-key-view-row div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2){flex-basis:100%!important}
  .block-container{padding-top:2.8rem!important;padding-bottom:calc(2rem + env(safe-area-inset-bottom))!important;padding-left:.7rem!important;padding-right:.7rem!important}
  .hero{align-items:flex-start;gap:7px;margin-bottom:8px;padding:10px 10px;border-radius:12px}.title{font-size:clamp(1.28rem,5.2vw,1.6rem)}
  .sub{font-size:.76rem;line-height:1.32}.chips{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%;gap:4px}
  .chip{font-size:.62rem;white-space:normal;overflow-wrap:anywhere;padding:3px 6px;text-align:center}
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-bottom:9px}
  .kpi{padding:10px 9px 9px 13px;border-radius:12px}
  .kpi .ic{width:22px;height:22px;right:7px;top:8px;font-size:.78rem}
  .kpi .l{font-size:.6rem;padding-right:22px}.kpi .v{font-size:1.3rem}.kpi .s{font-size:.62rem;line-height:1.15}
  [role="tablist"]{gap:6px!important;padding-bottom:8px}
  [role="tablist"] [role="tab"]{padding:7px 12px!important}
  [role="tablist"] [role="tab"] p{font-size:.82rem}
  [role="radiogroup"]{flex-wrap:wrap!important;gap:6px 12px!important}
  .meters{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
  .meter{padding:10px;border-radius:11px}.meter .mh{font-size:.74rem}.meter .mh b{font-size:1.05rem}
  .advlbl{gap:8px;font-size:.7rem;flex-wrap:wrap}
  .stDownloadButton>button,.stButton>button{min-height:42px}
}
@media (max-width:380px){
  .block-container{padding-left:.55rem!important;padding-right:.55rem!important}
  .kpi .v{font-size:1.16rem}.kpi .l{font-size:.57rem}.kpi .s{font-size:.6rem}
  .meter .mn{font-size:.65rem}.chip{font-size:.66rem}
}
/* --- DESKTOP FILTER STRIP SCROLL START (rollback-safe) --- */
/* Keep the screen/filter strip on one line at desktop widths too. Mobile keeps
   its hidden-scrollbar swipe; desktop gets a thin visible bar for mouse/trackpad. */
@media (min-width:641px){
  .st-key-screen-tabs [role="radiogroup"],
  .st-key-screen-tabs [role="tablist"]{
    flex-wrap:nowrap!important;
    overflow-x:auto!important;
    overflow-y:hidden!important;
    scroll-snap-type:x proximity;
    scrollbar-width:thin;
    scrollbar-color:color-mix(in srgb,var(--mp-accent) 55%,var(--mp-line)) transparent;
    -webkit-overflow-scrolling:touch;
  }
  .st-key-screen-tabs [role="radiogroup"]::-webkit-scrollbar,
  .st-key-screen-tabs [role="tablist"]::-webkit-scrollbar{display:block!important;height:6px!important}
  .st-key-screen-tabs [role="radiogroup"]::-webkit-scrollbar-track,
  .st-key-screen-tabs [role="tablist"]::-webkit-scrollbar-track{background:transparent}
  .st-key-screen-tabs [role="radiogroup"]::-webkit-scrollbar-thumb,
  .st-key-screen-tabs [role="tablist"]::-webkit-scrollbar-thumb{
    background:color-mix(in srgb,var(--mp-accent) 48%,var(--mp-line));border-radius:99px}
  .st-key-screen-tabs [role="radiogroup"]>*,
  .st-key-screen-tabs [role="tablist"]>{flex:none!important;scroll-snap-align:start}
}
/* --- DESKTOP FILTER STRIP SCROLL END --- */
</style>
"""


def active_theme() -> str:
    """Theme chosen with the in-app toggle (falls back to light on first visit)."""
    value = str(st.session_state.get("appearance_theme", "light")).lower()
    return value if value in _THEMES else "light"


def inject_css(font: str, hide_sidebar: bool = False, theme: str | None = None) -> None:
    theme = (theme or active_theme()).lower()
    palette = _THEMES.get(theme, _THEMES["light"])
    css = _PAGE_CSS.replace("__IMPORT__", f"@import url('{font_url(font)}');" if font_url(font) else "")
    css = css.replace("__FAMILY__", font_family(font))
    css = css.replace("__SCHEME__", theme)
    for key, value in palette.items():
        css = css.replace("__" + key + "__", value)
    if hide_sidebar:
        css = css.replace("</style>", "section[data-testid='stSidebar'],button[data-testid='stSidebarCollapsedControl'],div[data-testid='stSidebarCollapsedControl']{display:none!important}</style>")
    st.markdown(css, unsafe_allow_html=True)


def hero(title: str, subtitle: str, chips: list, eyebrow: str = "MarketPulse 750 · Nifty Total Market") -> None:
    """Older header card (no longer used by the main page; kept for compatibility)."""
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    st.markdown(
        f'<div class="hero"><div><div class="eyebrow">{eyebrow}</div>'
        f'<div class="title">{title}</div><div class="sub">{subtitle}</div></div>'
        f'<div class="chips">{chip_html}</div></div>', unsafe_allow_html=True)


def brand(title: str, tagline: str, description: str) -> None:
    """New hero header: pulse logo, gradient title card, eyebrow and description."""
    pulse = ('<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" '
             'stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M2 13h4l3-7 4 13 3-6h6"/></svg>')
    st.markdown(
        f'<div class="mp-brand"><h1><span class="mp-mark">{pulse}</span>{title}</h1>'
        f'<div class="tag">{tagline}</div><p>{description}</p></div>', unsafe_allow_html=True)


def pills(items: list) -> None:
    """Single row of small status pills (as-of date, update time, counts)."""
    st.markdown('<div class="pillrow">' + "".join(f"<span>{i}</span>" for i in items) + "</div>",
                unsafe_allow_html=True)


_KPI_ICONS = (
    ("top picks", "★"), ("trend template", "✅"), ("vcp", "◧"), ("volume breakout", "🚀"),
    ("breakout", "🚀"), ("stage 1", "🌱"), ("blue dot", "🔵"), ("rated", "📊"),
    ("liquid", "💧"), ("breadth", "🧭"), ("advancing", "▲"), ("declining", "▼"),
    ("rs", "⚡"), ("sector", "🏭"), ("base", "🧱"), ("momentum", "📈"),
)


def _kpi_icon(label: str) -> str:
    text = str(label).lower()
    for needle, icon in _KPI_ICONS:
        if needle in text:
            return icon
    return "◆"


def kpis(items: list) -> None:
    """Redesigned stat cards. Each item is (label, value, sub, colour, [icon])."""
    cards = []
    for item in items:
        label, value, sub = item[0], item[1], item[2]
        icon = item[4] if len(item) > 4 else _kpi_icon(label)
        cards.append(
            f'<div class="kpi"><div class="ic">{icon}</div><div class="l">{label}</div>'
            f'<div class="v">{value}</div><div class="s">{sub}</div></div>')
    st.markdown(f'<div class="kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


def meters(items: list) -> None:
    """items: (label, percent 0-100, small note)"""
    cards = "".join(
        f'<div class="meter"><div class="mh"><span>{l}</span><b>{p:.0f}%</b></div>'
        f'<div class="mt"><div class="mf" style="width:{max(0, min(100, p))}%"></div></div>'
        f'<div class="mn">{n}</div></div>' for l, p, n in items)
    st.markdown(f'<div class="meters">{cards}</div>', unsafe_allow_html=True)


def adv_dec(adv: int, dec: int, unch: int) -> None:
    total = max(adv + dec + unch, 1)
    st.markdown(
        f'<div class="advdec"><div class="a" style="width:{adv / total * 100:.1f}%"></div>'
        f'<div class="d" style="width:{dec / total * 100:.1f}%"></div></div>'
        f'<div class="advlbl"><span style="color:#10b981">▲ {adv} advancing</span>'
        f'<span style="opacity:.6">{unch} unchanged</span>'
        f'<span style="color:#ef4444">{dec} declining ▼</span></div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="tabnote">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- table columns
# type: sym txt rs chg sgn1 stage tt chk dot n0 n1 n2 pct spct bar text ago mult
# pri: 1 always shown | 2 hidden on small phones | 3 hidden on phones (tables scroll sideways otherwise)
SPEC = {
    "Symbol": dict(t="Symbol", type="sym", pri=1, left=True),
    "Trend_State": dict(t="Trend", type="text", pri=1, left=True),
    "Company Name": dict(t="Company", type="txt", pri=3, left=True),
    "Sector": dict(t="Sector", type="txt", pri=3, left=True),
    "Sector_Rank": dict(t="Sector #", type="n0", pri=3),
    "Sector_Strength": dict(t="Sector strength", type="bar", pri=3),
    "Liquid": dict(t="Liquid", type="chk", pri=2),
    "Avg_Value_Cr": dict(t="Avg value ₹ cr/day", type="cr", pri=2),
    "Market_Cap_Cr": dict(t="Mkt cap ₹ cr", type="cr0", pri=2),
    "RS_Rating": dict(t="RS", type="rs", pri=1),
    "RS_Excess_3M_%": dict(t="RS vs Nifty · 3M", type="spct", pri=2),
    "RS_Excess_6M_%": dict(t="RS vs Nifty · 6M", type="spct", pri=3),
    "RS_Improving": dict(t="RS improving", type="chk", pri=3),
    "RS_Change": dict(t="Chg", type="chg", pri=2),
    "Stage": dict(t="Stage", type="stage", pri=2, left=True),
    "TT_Score": dict(t="Trend Template", type="tt", pri=2),
    "RS_Line_New_High": dict(t="RS line high", type="chk", pri=3),
    "RS_Line_Near_High": dict(t="RS line near high", type="chk", pri=3),
    "RS_Line_Uptrend": dict(t="RS line rising", type="chk", pri=3),
    "RS_Blue_Dot": dict(t="Blue dot", type="dot", pri=3),
    "RSI14": dict(t="RSI", type="n1", pri=2),
    "Close": dict(t="Close", type="n2", pri=1),
    "Chg_1D_%": dict(t="1D change %", type="spct", pri=1),
    "Pct_From_52W_High": dict(t="From 52W high", type="pct", pri=2),
    "Pct_Above_50SMA": dict(t="Above 50 SMA", type="pct", pri=2),
    "Extension_State": dict(t="Extension", type="text", pri=3),
    "Volume_Pressure_20D": dict(t="20D volume pressure", type="text", pri=3),
    "Up_Down_Vol_Ratio_20D": dict(t="Up/down vol · 20D", type="mult", pri=3),
    "Pct_Above_52W_Low": dict(t="Above 52W low", type="pct", pri=3),
    "Weighted_Return_%": dict(t="Weighted return", type="spct", pri=3),
    "VCP": dict(t="VCP", type="chk", pri=2),
    "VCP_Contractions": dict(t="Pullbacks %", type="text", pri=2, left=True),
    "VCP_Vol_Contracting": dict(t="Vol shrinking", type="chk", pri=3),
    "Vol_Dry_Up": dict(t="Vol dry-up", type="chk", pri=3),
    "VCP_Setup": dict(t="VCP setup", type="chk", pri=2),
    "VCP_Breakout": dict(t="VCP breakout", type="chk", pri=2),
    "VCP_Breakout_Days_Ago": dict(t="VCP breakout · days ago", type="ago", pri=2),
    "VCP_Breakout_Vol_x": dict(t="VCP breakout vol", type="mult", pri=2),
    "VCP_Breakout_Return_%": dict(t="Return since VCP breakout", type="spct", pri=2),
    # --- DARVAS BOX START (rollback-safe) ---
    "Darvas_Status": dict(t="Darvas status", type="text", pri=1, left=True),
    "Darvas_Box_Top": dict(t="Box top", type="n2", pri=1),
    "Darvas_Box_Bottom": dict(t="Box bottom / stop", type="n2", pri=1),
    "Darvas_Box_Height_%": dict(t="Box height", type="pct", pri=2),
    "Darvas_Breakout_Days_Ago": dict(t="Breakout · days ago", type="ago", pri=2),
    "Darvas_Breakout_Vol_x": dict(t="Breakout vol", type="mult", pri=2),
    "Darvas_In_Box_Days": dict(t="In box days", type="n0", pri=2),
    "Darvas_Pct_To_Top": dict(t="To box top", type="pct", pri=2),
    "Darvas_Stop": dict(t="Stop", type="n2", pri=2),
    "Darvas_Top_Date": dict(t="Top date", type="text", pri=3, left=True),
    "Darvas_Bottom_Date": dict(t="Bottom date", type="text", pri=3, left=True),
    "Darvas_Breakout_Date": dict(t="Breakout date", type="text", pri=3, left=True),
    "Darvas_Reason": dict(t="Box details", type="txt", pri=3, left=True),
    "Darvas_OK": dict(t="Darvas match", type="chk", pri=3),
    # --- DARVAS BOX END ---
    "Entry_Score": dict(t="Entry score", type="bar", pri=1),
    "Entry_Type": dict(t="Entry type", type="text", pri=1, left=True),
    "Entry_Reason": dict(t="Why it scored", type="txt", pri=2, left=True),
    # --- MASTER LIST START (rollback-safe) ---
    "Confluence_Score": dict(t="Confluence", type="bar", pri=1),
    "Tier": dict(t="Tier", type="tier", pri=1),
    "Filter_Count": dict(t="# filters", type="n0", pri=1),
    "In_Filters": dict(t="In filters", type="chips", pri=2, left=True),
    # --- MASTER LIST END ---
    # --- MF INFLOW PANEL START (rollback-safe) ---
    "MF_Month_Chg_%": dict(t="MF month chg %", type="spct", pri=1),
    # --- MF INFLOW PANEL END ---
    # --- WEEKLY SHORTLIST START (rollback-safe) ---
    "Selection_Date": dict(t="Selected", type="text", pri=1, left=True),
    "Selected_Close": dict(t="Close at selection", type="n2", pri=2),
    "Gain_Since_Selection_%": dict(t="Gain since selection", type="spct", pri=1),
    "Change": dict(t="Added / Removed", type="text", pri=1, left=True),
    "Weeks_Held": dict(t="Weeks held", type="n0", pri=2),
    # --- WEEKLY SHORTLIST END ---
    "Stop_Distance_%": dict(t="Stop distance", type="pct", pri=2),
    "Pivot": dict(t="Pivot", type="n2", pri=2),
    "Pct_To_Pivot": dict(t="To pivot", type="pct", pri=1),
    "Vol_Breakout": dict(t="Breakout", type="chk", pri=2),
    "Breakout_Days_Ago": dict(t="When", type="ago", pri=2),
    "Breakout_Vol_x": dict(t="Breakout vol", type="mult", pri=2),
    "Vol_x_50d": dict(t="Vol today", type="mult", pri=3),
    "Stage1_Base": dict(t="Stage 1 base", type="chk", pri=3),
    "Base_Days": dict(t="Base length", type="days", pri=2),
    "Base_Depth_%": dict(t="Base depth", type="pct", pri=3),
    "Base_Forming": dict(t="Base forming", type="chk", pri=3),
    "Market_Above_10SMA": dict(t="Market above 10-day SMA", type="chk", pri=3),
    "Market_Above_20SMA": dict(t="Market above 20-day SMA", type="chk", pri=3),
    # industry table
    "Rank": dict(t="#", type="n0", pri=1),
    "Group": dict(t="Group", type="grp", pri=1, left=True),
    "Pct_Above_200": dict(t="Above 200 SMA", type="pct0", pri=3),
    "Pct_Stage2": dict(t="Stage 2", type="pct0", pri=3),
    "Sector_Score": dict(t="Strength", type="bar", pri=1),
    "Stocks": dict(t="Stocks", type="n0", pri=2),
    "Median_RS": dict(t="Median RS", type="n0", pri=2),
    "Avg_RS": dict(t="Avg RS", type="n1", pri=3),
    "Avg_RS_Change": dict(t="Avg chg", type="sgn1", pri=3),
    "Pct_RS80": dict(t="RS ≥ 80", type="pct0", pri=2),
    "Pct_TT_Pass": dict(t="Trend Template", type="pct0", pri=2),
    "TT_Pass_Count": dict(t="TT pass", type="n0", pri=3),
    "Blue_Dots": dict(t="Blue dots", type="n0", pri=3),
    "Avg_Weighted_Return_%": dict(t="Avg return", type="spct", pri=3),
    "Top_Stocks": dict(t="Leaders", type="text", pri=2, left=True),
}
COLS_DEFAULT = ["Symbol", "Trend_State", "Company Name", "Sector", "Sector_Rank", "RS_Rating",
                "Sector_Strength", "RS_Excess_3M_%", "RS_Excess_6M_%", "RS_Improving", "RS_Change",
                "Stage", "TT_Score",
                "Volume_Pressure_20D", "Up_Down_Vol_Ratio_20D", "Pct_Above_50SMA", "Extension_State",
                "Liquid", "Avg_Value_Cr", "Market_Cap_Cr", "RS_Line_New_High", "RS_Blue_Dot", "RSI14", "Close", "Chg_1D_%",
                "Pct_From_52W_High", "Pct_Above_52W_Low", "Weighted_Return_%"]
COLS_PATTERN = ["Symbol", "RS_Rating", "Stage", "TT_Score", "VCP", "VCP_Contractions", "Vol_Dry_Up",
                "VCP_Setup", "Pivot", "Pct_To_Pivot", "Close", "Chg_1D_%", "Vol_Breakout", "Breakout_Days_Ago",
                "Breakout_Vol_x", "Vol_x_50d", "Stage1_Base", "Base_Days", "Base_Depth_%", "Liquid",
                "Avg_Value_Cr", "Market_Cap_Cr", "Sector", "Company Name"]
COLS_VCP_BREAKOUT = ["Symbol", "RS_Rating", "Stage", "TT_Score", "VCP_Contractions", "Pivot",
                     "VCP_Breakout_Days_Ago", "VCP_Breakout_Vol_x", "VCP_Breakout_Return_%",
                     "Close", "Chg_1D_%", "Pct_Above_50SMA", "RS_Line_Uptrend", "RS_Line_Near_High",
                     "Vol_x_50d", "Liquid", "Sector", "Company Name"]
# --- DARVAS BOX START (rollback-safe) ---
COLS_DARVAS = ["Symbol", "Darvas_Status", "RS_Rating", "TT_Score", "Stage", "Darvas_Box_Top",
               "Darvas_Box_Bottom", "Darvas_Box_Height_%", "Darvas_Breakout_Vol_x",
               "Darvas_Breakout_Days_Ago", "Darvas_In_Box_Days", "Darvas_Pct_To_Top",
               "Close", "Chg_1D_%", "Pct_From_52W_High", "Sector", "Company Name", "Darvas_Reason"]
# --- DARVAS BOX END ---
COLS_ENTRY = ["Symbol", "Entry_Score", "Entry_Type", "RS_Rating", "TT_Score", "Sector_Strength",
              "Sector_Rank", "Pivot", "Pct_To_Pivot", "Breakout_Days_Ago", "Breakout_Vol_x",
              "VCP_Breakout_Days_Ago", "VCP_Breakout_Vol_x", "Pct_Above_50SMA", "Extension_State",
              "Stop_Distance_%", "RS_Change", "RS_Excess_3M_%", "RS_Improving", "Volume_Pressure_20D",
              "VCP_Contractions", "Entry_Reason", "Stage", "Close", "Chg_1D_%", "Sector", "Company Name"]
# --- MASTER LIST START (rollback-safe) ---
COLS_MASTER = ["Symbol", "Confluence_Score", "Tier", "Filter_Count", "In_Filters",
               "RS_Rating", "TT_Score", "Stage", "VCP_Contractions", "Pct_To_Pivot",
               "Pct_From_52W_High", "Pct_Above_50SMA", "Close", "Sector", "Company Name"]
# --- MASTER LIST END ---
# --- MF INFLOW PANEL START (rollback-safe) ---
COLS_MF_INFLOW = ["Symbol", "Confluence_Score", "Tier", "MF_Month_Chg_%", "Filter_Count",
                  "In_Filters", "RS_Rating", "TT_Score", "Stage", "VCP_Contractions",
                  "Pct_To_Pivot", "Pct_From_52W_High", "Pct_Above_50SMA", "Close",
                  "Sector", "Company Name"]
# --- MF INFLOW PANEL END ---
# --- WEEKLY SHORTLIST START (rollback-safe) ---
COLS_WEEKLY = ["Symbol", "Confluence_Score", "Tier", "Filter_Count", "In_Filters",
               "Change", "Selection_Date", "Weeks_Held", "Selected_Close", "Close",
               "Gain_Since_Selection_%", "RS_Rating", "TT_Score", "Stage", "Sector", "Company Name"]
# --- WEEKLY SHORTLIST END ---
COLS_SECTOR_STRENGTH = ["Rank", "Group", "Sector_Score", "Stocks", "Median_RS", "Avg_RS", "Avg_RS_Change",
                        "Pct_RS80", "Pct_TT_Pass", "Pct_Above_200", "Pct_Stage2", "TT_Pass_Count", "Blue_Dots",
                        "Avg_Weighted_Return_%", "Top_Stocks"]

# ---------------------------------------------------------------- table iframe
_TABLE_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
__IMPORT__
:root{--fg:#31333f;--bg:#fff;--accent:#6366f1;--accent2:#ec4899;--rowh:__ROWH__px;--ff:__FAMILY__;
--line:color-mix(in srgb,var(--fg) 14%,transparent);--soft:color-mix(in srgb,var(--fg) 6%,transparent);
--g:#047857;--a:#92400e;--r:#b91c1c;--b:#1d4ed8}
html.dark{--g:#34d399;--a:#fbbf24;--r:#f87171;--b:#60a5fa}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:13.5px/1.35 var(--ff)}
.wrap{height:calc(100vh - 48px);overflow:auto;border:1px solid var(--line);border-radius:14px;
overscroll-behavior:contain;scrollbar-width:thin;-webkit-overflow-scrolling:touch;touch-action:pan-x pan-y}
table{border-collapse:separate;border-spacing:0;width:100%;min-width:max-content}
th{position:sticky;top:0;z-index:3;padding:0 12px;height:42px;text-align:right;white-space:nowrap;cursor:pointer;
user-select:none;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;font-weight:700;
color:color-mix(in srgb,var(--fg) 78%,var(--bg));background:color-mix(in srgb,var(--accent) 8%,var(--bg));
border-bottom:1px solid color-mix(in srgb,var(--accent) 24%,var(--line))}
th:hover{color:var(--fg)}
th.l,td.l{text-align:left}
th .ar{display:inline-block;width:12px;color:var(--accent)}
td{height:var(--rowh);padding:0 12px;white-space:nowrap;text-align:right;border-bottom:1px solid var(--line);
font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
tbody tr:nth-child(even) td{background:color-mix(in srgb,var(--fg) 3.5%,var(--bg))}
tbody tr:hover td{background:color-mix(in srgb,var(--accent) 10%,var(--bg))}
th:first-child,td:first-child{position:sticky;left:0;z-index:2;background:var(--bg)}
th:first-child{z-index:4;background:color-mix(in srgb,var(--accent) 8%,var(--bg))}
tbody tr:nth-child(even) td:first-child{background:color-mix(in srgb,var(--fg) 3.5%,var(--bg))}
a.sym{color:var(--accent);font-weight:700;text-decoration:none}
a.sym:hover{text-decoration:underline}
.symcell{display:inline-flex;align-items:center;gap:6px}
.info-btn{position:relative;flex:none;width:20px;height:20px;padding:0;border:1px solid var(--line);border-radius:50%;
background:var(--soft);color:var(--accent);font:700 11px/18px var(--ff);cursor:pointer}
.info-btn::after{content:"";position:absolute;inset:-8px}
@media(pointer:coarse){.info-btn{width:24px;height:24px;line-height:22px}.info-btn::after{inset:-10px}}
.info-btn:hover{background:var(--accent);color:#fff}
.ell{display:inline-block;max-width:210px;overflow:hidden;text-overflow:ellipsis;vertical-align:middle;
color:color-mix(in srgb,var(--fg) 70%,var(--bg))}
.badge{display:inline-block;min-width:38px;text-align:center;padding:2px 9px;border-radius:999px;font-weight:700}
.c1{background:#059669;color:#fff}
.c2{background:color-mix(in srgb,#10b981 22%,var(--bg));color:var(--g)}
.c3{background:color-mix(in srgb,#f59e0b 24%,var(--bg));color:var(--a)}
html.dark .c3{color:#fbbf24}
.c4{background:var(--soft);color:color-mix(in srgb,var(--fg) 75%,var(--bg))}
.c5{background:color-mix(in srgb,#ef4444 18%,var(--bg));color:var(--r)}
.chipx{display:inline-block;padding:2px 10px;border-radius:8px;font-size:.78rem;font-weight:600}
.s1{background:color-mix(in srgb,#3b82f6 18%,var(--bg));color:var(--b)}
.s2{background:color-mix(in srgb,#10b981 20%,var(--bg));color:var(--g)}
.s3{background:color-mix(in srgb,#f59e0b 22%,var(--bg));color:var(--a)}
html.dark .s3{color:#fbbf24}
.s4{background:color-mix(in srgb,#ef4444 18%,var(--bg));color:var(--r)}
.s0{background:var(--soft)}
/* --- MASTER LIST START (rollback-safe) --- */
.tierbadge{display:inline-grid;place-items:center;min-width:24px;padding:2px 8px;border-radius:7px;font-weight:800;font-size:.78rem}
.ta{background:color-mix(in srgb,#10b981 20%,var(--bg));color:var(--g)}
.tb{background:color-mix(in srgb,#f59e0b 22%,var(--bg));color:var(--a)}
html.dark .tb{color:#fbbf24}
.tc{background:var(--soft);color:color-mix(in srgb,var(--fg) 70%,var(--bg))}
.chipsx{display:flex;flex-wrap:wrap;gap:4px;max-width:340px}
.chipx2{display:inline-block;padding:2px 7px;border-radius:6px;font-size:.72rem;font-weight:600;white-space:nowrap;
background:var(--soft);border:1px solid var(--line);color:color-mix(in srgb,var(--fg) 80%,var(--bg))}
.chipx2.key{background:color-mix(in srgb,var(--accent) 10%,var(--bg));border-color:color-mix(in srgb,var(--accent) 35%,var(--line));color:var(--accent)}
/* --- MASTER LIST END --- */
.seg{display:inline-flex;gap:2px;vertical-align:middle;margin-right:7px}
.seg i{width:5px;height:13px;border-radius:2px;background:var(--line)}
.seg i.on{background:var(--accent)}
.seg.full i.on{background:var(--g)}
.ttn{font-weight:600}.full+.ttn{color:var(--g)}
.up{color:var(--g);font-weight:600}.dn{color:var(--r);font-weight:600}
.faint{opacity:.55}
.ok{color:var(--g);font-weight:700}
.dotx{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--accent);
box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 25%,transparent)}
.bar{display:flex;align-items:center;gap:9px;min-width:150px}
.bar .t{flex:1;height:8px;border-radius:99px;background:var(--soft);overflow:hidden}
.bar .f{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.bar b{min-width:24px;text-align:right}
.txt{color:color-mix(in srgb,var(--fg) 85%,var(--bg))}
.empty{text-align:center;padding:36px 12px;opacity:.6}
.searchbar{display:flex;align-items:center;gap:10px;margin:0 0 8px}
.searchbar input{flex:1;min-width:0;padding:9px 12px;border:1px solid var(--line);border-radius:9px;
background:var(--bg);color:var(--fg);font:inherit;outline:none}
.searchbar input:focus{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 18%,transparent)}
.count{font-size:.82rem;opacity:.65;white-space:nowrap}
@media (max-width:620px){td,th{padding:0 8px}html,body{font-size:12.5px}}
@media (max-width:420px){.searchbar{gap:6px}.searchbar input{font-size:16px;padding:9px}.count{font-size:.72rem}}
</style></head><body>
<div class="searchbar" id="searchbar" style="display:none"><input id="search" type="search" autocomplete="off">
<span class="count" id="count"></span></div>
<div class="wrap"><table><thead id="h"></thead><tbody id="b"></tbody></table></div>
<script>
const P=__PAYLOAD__;
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fx=(v,d)=>v==null?'<span class="faint">–</span>':Number(v).toFixed(d);
const sg=(v,d,suf)=>v==null?'<span class="faint">–</span>':'<span class="'+(v>0?'up':v<0?'dn':'faint')+'">'+(v>0?'+':'')+Number(v).toFixed(d)+suf+'</span>';
let sk=P.sort[0],sd=P.sort[1];
const pc=c=>(c.pri==2?'p2':c.pri==3?'p3':'')+(c.left?' l':'');
let query='';
function cell(c,r){
  const v=r[c.k],k='<td class="'+pc(c)+'">';
  switch(c.type){
    case 'sym':return k+'<span class="symcell"><a class="sym" target="_blank" rel="noopener" href="https://www.tradingview.com/chart/?symbol=NSE%3A'+encodeURIComponent(v)+'">'+esc(v)+'</a><button class="info-btn" type="button" title="Stock details and chart" aria-label="Stock details and chart for '+esc(v)+'" data-symbol="'+esc(v)+'">i</button></span></td>';
    case 'grp':return k+'<b>'+esc(v)+'</b></td>';
    case 'cr0':return k+(v==null?'<span class="faint">–</span>':Number(v).toLocaleString('en-IN',{maximumFractionDigits:0}))+'</td>';
    case 'cr':return k+(v==null?'<span class="faint">–</span>':Number(v).toLocaleString('en-IN',{maximumFractionDigits:1}))+'</td>';
    case 'txt':return k+'<span class="ell" title="'+esc(v)+'">'+esc(v)+'</span></td>';
    case 'text':return k+(v?'<span class="txt">'+esc(v)+'</span>':'<span class="faint">–</span>')+'</td>';
    case 'rs':{if(v==null)return k+'–</td>';const q=v>=90?'c1':v>=80?'c2':v>=70?'c3':v>=50?'c4':'c5';return k+'<span class="badge '+q+'">'+v+'</span></td>';}
    case 'chg':return k+(v>0?'<span class="up">▲ '+v+'</span>':v<0?'<span class="dn">▼ '+Math.abs(v)+'</span>':'<span class="faint">0</span>')+'</td>';
    case 'sgn1':return k+sg(v,1,'')+'</td>';
    case 'spct':return k+sg(v,1,'%')+'</td>';
    case 'stage':{if(!v||v==='n/a')return k+'<span class="chipx s0">n/a</span></td>';const n=(v.match(/\d/)||[0])[0];return k+'<span class="chipx s'+n+'">'+esc(v.replace('Stage ','').replace(' · ',' · '))+'</span></td>';}
    case 'tt':{let s='';for(let i=1;i<=8;i++)s+='<i class="'+(i<=v?'on':'')+'"></i>';return k+'<span class="seg'+(v==8?' full':'')+'">'+s+'</span><span class="ttn">'+v+'/8</span></td>';}
    case 'chk':return k+(v?'<span class="ok">✓</span>':'<span class="faint">·</span>')+'</td>';
    case 'dot':return k+(v?'<span class="dotx" title="RS line at 52-week high before price"></span>':'<span class="faint">·</span>')+'</td>';
    case 'n0':return k+(v==null?'–':Math.round(v))+'</td>';
    case 'n1':return k+fx(v,1)+'</td>';
    case 'n2':return k+fx(v,2)+'</td>';
    case 'pct':return k+(v==null?'<span class="faint">–</span>':Number(v).toFixed(1)+'%')+'</td>';
    case 'pct0':return k+(v==null?'–':Math.round(v)+'%')+'</td>';
    case 'days':return k+(v?v+'d':'<span class="faint">–</span>')+'</td>';
    case 'ago':return k+(v==null?'<span class="faint">–</span>':v==0?'<span class="up">today</span>':v+'d ago')+'</td>';
    case 'mult':return k+(v==null?'<span class="faint">–</span>':Number(v).toFixed(1)+'×')+'</td>';
    case 'bar':return k+'<div class="bar"><div class="t"><div class="f" style="width:'+Math.max(0,Math.min(99,v||0))+'%"></div></div><b>'+(v==null?'–':v)+'</b></div></td>';
    /* --- MASTER LIST START (rollback-safe) --- */
    case 'tier':{const q=String(v||'').toUpperCase(),cl=q==='A'?'ta':q==='B'?'tb':'tc';return k+'<span class="tierbadge '+cl+'">'+esc(q||'–')+'</span></td>';}
    case 'chips':{const parts=String(v||'').split(' · ').filter(Boolean);return k+'<span class="chipsx">'+parts.map((p,i)=>'<span class="chipx2'+(i===0?' key':'')+'">'+esc(p)+'</span>').join('')+'</span></td>';}
    /* --- MASTER LIST END --- */
  }
  return k+esc(v)+'</td>';
}
function draw(){
  const rows=P.rows.filter((r,i)=>!query||P.searchRows[i].some(v=>String(v??'').toLocaleLowerCase().includes(query)));
  rows.sort((a,b)=>{let x=a[sk],y=b[sk];
    if(x==null&&y==null)return 0;if(x==null)return 1;if(y==null)return -1;
    if(typeof x==='string')return sd*x.localeCompare(y);
    return sd*(Number(x)-Number(y));});
  document.getElementById('h').innerHTML='<tr>'+P.cols.map(c=>'<th class="'+pc(c)+'" data-k="'+c.k+'">'+esc(c.t)+'<span class="ar">'+(c.k===sk?(sd>0?'▲':'▼'):'')+'</span></th>').join('')+'</tr>';
  document.getElementById('b').innerHTML=rows.length?rows.map(r=>'<tr>'+P.cols.map(c=>cell(c,r)).join('')+'</tr>').join('')
    :'<tr><td class="empty" colspan="'+P.cols.length+'" style="text-align:center;position:static">'+esc(query?'No rows match your search.':P.empty)+'</td></tr>';
  if(P.searchLabel){document.getElementById('searchbar').style.display='flex';
    document.getElementById('search').placeholder=P.searchLabel;
    document.getElementById('count').textContent=query?rows.length+' of '+P.rows.length+' rows':P.rows.length+' rows';}
  document.querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;
    if(k===sk)sd=-sd;else{sk=k;sd=P.cols.find(c=>c.k===k).left?1:-1;}draw();});
  document.querySelectorAll('.info-btn').forEach(btn=>btn.onclick=e=>{e.stopPropagation();window.parent.postMessage({type:'marketpulse:chart-request',symbol:btn.dataset.symbol,nonce:Date.now()},'*');});
}
if(P.searchLabel)document.getElementById('search').addEventListener('input',e=>{query=e.target.value.trim().toLocaleLowerCase();draw();});
// follow the Streamlit theme (light / dark / custom) live
function sync(){
  let bg,fg;
  try{let d=window.parent.document,w=window.parent;if(!d.querySelector('.stApp')){w=window.parent.parent;d=w.document;}const app=d.querySelector('.stApp'),cs=w.getComputedStyle(app);bg=cs.backgroundColor;fg=cs.color;}catch(e){}
  if(!bg||bg==='rgba(0, 0, 0, 0)'||!fg){const d=matchMedia('(prefers-color-scheme: dark)').matches;bg=d?'rgb(14,17,23)':'rgb(255,255,255)';fg=d?'rgb(250,250,250)':'rgb(49,51,63)';}
  const r=document.documentElement;r.style.setProperty('--bg',bg);r.style.setProperty('--fg',fg);
  const m=(bg.match(/[\d.]+/g)||[255,255,255]).map(Number);r.classList.toggle('dark',(0.299*m[0]+0.587*m[1]+0.114*m[2])<128);
}
sync();setInterval(sync,2000);draw();
</script></body></html>"""


def table(df, keys, sort, font="Inter", density="Comfortable",
          empty="No stocks match the current filters.", titles=None, search_keys=None,
          search_label="Search stock / symbol or company name", market_context=None):
    """Render a sortable, theme-aware table. `sort` = (column key, -1 desc | 1 asc)."""
    cols = [dict(SPEC[k], k=k) for k in keys if k in df.columns and k in SPEC]
    for c in cols:
        if titles and c["k"] in titles:
            c["t"] = titles[c["k"]]
    data = json.loads(df[[c["k"] for c in cols]].to_json(orient="records")) if len(df) else []
    search_rows = (df[search_keys].fillna("").astype(str).values.tolist()
                   if search_keys and len(df) else [])
    rowh = 31 if density == "Compact" else 41
    height = (120 if not data else min(len(data) * rowh + 46, 640)) + 48
    payload = json.dumps({"cols": cols, "rows": data, "searchRows": search_rows,
                          "searchLabel": search_label if search_keys else "",
                          "sort": list(sort), "empty": empty}).replace("</", "<\\/")
    html = (_TABLE_HTML
            .replace("__IMPORT__", f"@import url('{font_url(font)}');" if font_url(font) else "")
            .replace("__FAMILY__", font_family(font))
            .replace("__ROWH__", str(rowh))
            .replace("__PAYLOAD__", payload))
    identity_key = "Symbol" if "Symbol" in df.columns else (df.columns[0] if len(df.columns) else "table")
    identity = df[identity_key].head(3).fillna("").astype(str).tolist() if len(df) and identity_key in df else []
    key_source = json.dumps([keys, search_keys or [], search_label, titles or {}, identity_key, identity], sort_keys=True)
    component_key = "mp_table_" + hashlib.md5(key_source.encode("utf-8")).hexdigest()[:14]
    clicked = _TABLE_COMPONENT(html=html, height=height, key=component_key, default=None)
    if isinstance(clicked, dict) and clicked.get("symbol"):
        nonce = clicked.get("nonce")
        if nonce and nonce != st.session_state.get("_last_table_chart_click"):
            st.session_state["_last_table_chart_click"] = nonce
            st.session_state["_symbol_chart_request"] = str(clicked["symbol"])
            st.rerun()


def _embed(html: str, height: int) -> None:
    """st.iframe on current Streamlit; the older components.html call as a fallback."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height, scrolling=False)


_KLINE_SRC = "https://cdn.jsdelivr.net/npm/klinecharts@10.1.1/dist/umd/klinecharts.min.js"

_CHART_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--fg:#1f2937;--bg:#fff;--accent:#2563eb;--line:rgba(31,41,55,.16);--soft:rgba(31,41,55,.07);--up:#16a34a;--dn:#dc2626}
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden;background:var(--bg);color:var(--fg);
font:12.5px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
body{display:flex;flex-direction:column;gap:4px}
#hd{display:flex;flex-direction:column;gap:3px}
.r{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sym{font:800 24px/1.05 Georgia,"Times New Roman",serif;letter-spacing:.01em}
.co{font-size:14px;font-weight:600}
.sub{opacity:.62;font-size:12px}
.pill{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;white-space:nowrap;
color:var(--c);background:color-mix(in srgb,var(--c) 15%,transparent)}
.pill.solid{color:#fff;background:var(--c)}
.px{font:700 24px/1 system-ui,sans-serif}
.chg{font-weight:700;font-size:13px}
.up{color:var(--up)}.dn{color:var(--dn)}
.lab{font-weight:700;opacity:.8}
.rsd{font-weight:700;font-size:12px}
.rsp{display:inline-flex;align-items:baseline;flex-wrap:wrap;font-size:11.5px;opacity:.95;margin-left:6px}
.rsp b{font-weight:700}
.rsp .k{opacity:.6;margin-left:7px;margin-right:2px}
#tb{display:flex;flex-direction:column;gap:4px}
#bar,#chips{display:flex;align-items:center;gap:8px;overflow-x:auto;white-space:nowrap;scrollbar-width:none}
@media(min-width:1000px){#tb{flex-direction:row;flex-wrap:wrap;align-items:center;gap:6px 6px}#bar,#chips{display:contents}}
#bar::-webkit-scrollbar,#chips::-webkit-scrollbar{display:none}
.tools{position:absolute;left:10px;top:48px;bottom:8px;z-index:6;display:flex;flex-direction:column;align-items:flex-start;gap:5px}
.tools #tdraw{width:30px;height:30px;min-width:30px;padding:0;display:inline-flex;align-items:center;justify-content:center;
  border:0;border-radius:50%;background:color-mix(in srgb,var(--bg) 72%,transparent);color:var(--fg);opacity:.55;
  box-shadow:0 2px 9px rgba(0,0,0,.12);cursor:pointer;transition:opacity .15s,background .15s,color .15s;backdrop-filter:blur(3px)}
.tools #tdraw svg{width:15px;height:15px;display:block}
.tools #tdraw:hover,.tools #tdraw:focus-visible{opacity:1;color:var(--accent)}
.tools #tdraw.on{opacity:1;background:var(--accent);color:#fff;box-shadow:0 3px 12px rgba(37,99,235,.35)}
#toolpanel{display:none;flex:1;min-height:0;flex-direction:column;align-items:stretch;gap:1px;overflow-y:auto;white-space:nowrap;scrollbar-width:thin;scrollbar-color:var(--line) transparent;padding:5px;border:1px solid var(--line);border-radius:10px;background:color-mix(in srgb,var(--bg) 94%,transparent);box-shadow:0 8px 24px rgba(0,0,0,.18);backdrop-filter:blur(4px)}
.tools.open #toolpanel{display:flex}
.tools button{flex:none;border:1px solid var(--line);background:transparent;color:inherit;border-radius:7px;font:inherit;font-size:10px;line-height:1.15;font-weight:700;padding:2px 7px;cursor:pointer;width:150px;text-align:left}
.tools button.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.tools .tsep{width:100%;height:1px;background:var(--line);margin:2px 0;flex:none}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;flex:none}
.seg button{border:0;background:transparent;color:inherit;font:inherit;font-weight:600;padding:5px 10px;cursor:pointer;min-width:34px}
.seg button+button{border-left:1px solid var(--line)}
.seg button.on{background:var(--fg);color:var(--bg)}
#rng button.on{background:var(--soft);color:inherit;box-shadow:inset 0 -2px 0 var(--accent)}
select{flex:none;border:1px solid var(--line);border-radius:8px;background:transparent;color:inherit;font:inherit;font-weight:600;padding:5px 8px}
select option{color:#111;background:#fff}
.chip{flex:none;display:inline-flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:999px;
background:transparent;color:inherit;font:inherit;font-size:11px;padding:3px 7px;cursor:pointer;opacity:.55}
.chip i{width:10px;height:3px;border-radius:2px;background:var(--c)}
.chip i.b{height:9px;width:9px;border-radius:2px}
.chip.on{opacity:1;background:var(--soft)}
#wrap{position:relative;flex:1;min-height:240px}
#chart{position:absolute;inset:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;touch-action:none}
#lg{position:absolute;left:10px;right:auto;top:7px;z-index:3;pointer-events:none;font-size:11.5px;line-height:1.5;max-width:calc(100% - 92px);text-align:left}
#lg>div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#lg .m{opacity:.6;margin-left:6px}#lg .dt{font-weight:600;margin-right:4px}
#lg .hl{color:#2563eb;font-weight:600}
#ft{font-size:10.5px;opacity:.6;text-align:right}
.err{padding:16px;opacity:.75}
@media(max-width:1149px){.sn{display:none}}
@media(max-width:700px){#lg{font-size:10px;max-width:calc(100% - 72px)}.tools{left:6px;top:34px;bottom:6px;gap:4px}.tools #tdraw{width:26px;height:26px;min-width:26px;opacity:.62}.tools #tdraw svg{width:13px;height:13px}.tools button{width:132px;font-size:10px}}
@media(max-width:560px){.sym{font-size:20px}.px{font-size:21px}.co{font-size:13px}.sub,.asof,.long,.sn,#lg .hl,#lg .dt{display:none}.seg button{padding:5px 8px;min-width:30px}#lg{font-size:10px;max-width:calc(100% - 72px)}.tools{left:6px;top:34px;bottom:6px;gap:4px}.tools #tdraw{width:26px;height:26px;min-width:26px;opacity:.62}.tools #tdraw svg{width:13px;height:13px}.tools button{width:132px;font-size:10px}#lg .m{margin-left:4px}.r{gap:6px}#hd{gap:4px}}
</style></head><body>
<div id="hd"></div>
<div id="tb">
<div id="bar">
 <div class="seg" id="tf"><button type="button" data-t="D">D</button><button type="button" data-t="W">W</button><button type="button" data-t="M">M</button></div>
 <select id="ctype" title="Chart type"><option value="candle_solid">Candles</option><option value="candle_up_stroke">Hollow</option><option value="ohlc">OHLC bars</option><option value="hlc">HLC bars</option><option value="area">Line</option></select>
 <div class="seg"><button type="button" id="zin" title="Zoom in">+</button><button type="button" id="zout" title="Zoom out">−</button></div>
 <div class="seg" id="rng"></div>
</div>
<div id="chips">
 <button class="chip on" id="t_s10" style="--c:#2563eb" title="Simple moving average of the last 10 closes"><i></i>SMA 10</button>
 <button class="chip on" id="t_s20" style="--c:#2563eb" title="Simple moving average of the last 20 closes"><i></i>SMA 20</button>
 <button class="chip on" id="t_s50" style="--c:#2563eb" title="Simple moving average of the last 50 closes"><i></i>SMA 50</button>
 <button class="chip on" id="t_s150" style="--c:#2563eb" title="Simple moving average of the last 150 closes"><i></i>SMA 150</button>
 <button class="chip on" id="t_s200" style="--c:#2563eb" title="Simple moving average of the last 200 closes"><i></i>SMA 200</button>
 <button class="chip on" id="t_vol" style="--c:#10b981" title="Volume with its 50-day average"><i class="b"></i>Volume</button>
 <button class="chip on" id="t_rs" style="--c:#16a34a" title="Price relative to the benchmark index"><i></i>RS line</button>
 <button class="chip on" id="t_vcp" style="--c:#0891b2" title="Show the scanner VCP pivot box — final tightening leg with left/right boundaries and breakout marker"><i class="b"></i>VCP pivot box</button>
 <button class="chip on" id="t_base" style="--c:#3b82f6" title="Show base markers — detected bases, numbered oldest first"><i class="b"></i>Base markers</button>
 <button class="chip on" id="t_darvas" style="--c:#8b5cf6" title="Show Darvas boxes — automatic box top, bottom / stop and breakout marker"><i class="b"></i>Darvas boxes</button>
</div>
</div>
<div id="wrap">
<div id="tools" class="tools" title="Optional drawing tools. Right-click a drawing to delete it.">
  <button type="button" id="tdraw" title="Open or close drawing tools" aria-label="Drawing tools" aria-expanded="false"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg></button>
  <div id="toolpanel">
    <button type="button" data-tool="trend" title="Trend line — click start and end">╱ Trend line</button>
    <button type="button" data-tool="ray" title="Ray — click start and direction">⟍ Ray</button>
    <button type="button" data-tool="hline" title="Horizontal line — click once">━ Horizontal line</button>
    <button type="button" data-tool="vline" title="Vertical line — click once">│ Vertical line</button>
    <button type="button" data-tool="channel" title="Parallel channel — click two edges and width">∥ Parallel channel</button>
    <button type="button" data-tool="arrow" title="Arrow — click start and end">↗ Arrow</button>
    <button type="button" data-tool="rect" title="Rectangle — click two corners">▭ Rectangle</button>
    <span class="tsep"></span>
    <button type="button" data-tool="text" title="Text — click to place">T Text</button>
    <button type="button" data-tool="price" title="Price label — click to place">⌁ Price label</button>
    <button type="button" data-tool="callout" title="Callout — click to place">▣ Callout</button>
    <button type="button" data-tool="measure" title="Measure — click two points">% Measure</button>
    <button type="button" data-tool="daterange" title="Date range — click two dates">▤ Date range</button>
    <span class="tsep"></span>
    <button type="button" id="uundo" title="Undo (Ctrl+Z)">↶ Undo</button>
    <button type="button" id="uredo" title="Redo (Ctrl+Y)">↷ Redo</button>
    <button type="button" id="udel" title="Delete the last drawing (Delete key)">⌫ Delete</button>
    <button type="button" id="uclear" title="Clear all drawings on this symbol and timeframe">🧹 Clear all</button>
    <button type="button" id="uhide" title="Hide or show your drawings">🙈 Hide drawing</button>
  </div>
</div>
<div id="lg"></div><div id="chart"></div></div>
<div id="ft"></div>
<script src="__KLINE_SRC__"></script>
<script>
const P=__PAYLOAD__;
const I=P.info||null;
const $=id=>document.getElementById(id);
const SPANS={D:{'3M':63,'6M':126,'1Y':252,'2Y':504,'5Y':1260},W:{'3M':13,'6M':26,'1Y':52,'2Y':104,'5Y':260},M:{'3M':3,'6M':6,'1Y':12,'2Y':24,'5Y':60}};
const RLIST=['3M','6M','1Y','2Y','5Y'],PERIOD={D:'day',W:'week',M:'month'};
const MAS=[10,20,50,150,200];
const on={s10:true,s20:true,s50:true,s150:true,s200:true,vol:true,rs:true,vcp:true,base:true,darvas:true};
const DRAW_GID='mpDraw';
const TOOLS={
  trend:{name:'segment',styles:{line:{color:'#f59e0b',size:1.8}}},
  ray:{name:'rayLine',styles:{line:{color:'#f59e0b',size:1.7}}},
  hline:{name:'horizontalStraightLine',styles:{line:{color:'#f59e0b',size:1.3,style:'dashed',dashedValue:[4,3]},text:{color:'#f59e0b'}}},
  vline:{name:'verticalStraightLine',styles:{line:{color:'#8b5cf6',size:1.3,style:'dashed',dashedValue:[4,3]},text:{color:'#8b5cf6'}}},
  channel:{name:'parallelStraightLine',styles:{line:{color:'#0ea5e9',size:1.4}}},
  arrow:{name:'mpArrow'},
  rect:{name:'mpRect'},
  text:{name:'mpText'},
  price:{name:'mpPrice'},
  callout:{name:'mpCallout'},
  measure:{name:'mpMeasure'},
  daterange:{name:'mpDateRange'}
};
const NEED={segment:2,rayLine:2,horizontalStraightLine:1,verticalStraightLine:1,parallelStraightLine:3,
  mpArrow:2,mpRect:2,mpText:1,mpPrice:1,mpCallout:2,mpMeasure:2,mpDateRange:2};
const needPts=n=>NEED[n]||1;
let chart=null,tf='D',rng=RLIST.includes(P.range)?P.range:'1Y',data=P.bars,dark=false,rsBase=0,pal={};
let drawHidden=false,activeTool=null,hist=[],future=[],lastSnap='';
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=v=>v==null?'–':Number(v).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
const sgn=(v,d=1)=>(v>=0?'+':'−')+Math.abs(v).toFixed(d);

/* ---------- header ---------- */
function header(){
  if(!I){$('hd').style.display='none';return;}
  const up=I.change>=0,st=String(I.stage||''),sn=parseInt((st.match(/\d/)||[0])[0]);
  const sc={1:'#64748b',2:'#15803d',3:'#d97706',4:'#dc2626'}[sn]||'#64748b';
  let r2='<div class="r"><span class="px">'+fmt(I.price).replace(/\.00$/,'')+'</span><span class="chg '+(up?'up':'dn')+'">'+sgn(I.change,2)+'%<span class="asof">'+(I.asOf?' on '+esc(I.asOf):'')+'</span></span>';
  if(I.rs!=null)r2+='<span class="lab">RS</span><span class="pill solid" style="--c:#15803d">'+I.rs+'</span>'+(I.rsChange?'<span class="rsd '+(I.rsChange>0?'up':'dn')+'">'+(I.rsChange>0?'+':'')+I.rsChange+'</span>':'');
  if(I.ttScore!=null)r2+='<span class="pill'+(I.ttPass?' solid':'')+'" style="--c:'+(I.ttPass?'#059669':'#d97706')+'" title="Minervini Trend Template: 8 price/volume conditions. All 8 must pass.">TT '+I.ttScore+'/8'+(I.ttPass?' ✓':'')+'</span>';
  if(st)r2+='<span class="pill solid" style="--c:'+sc+'">'+esc(st)+'</span>';
  if(I.vcpPivot!=null)r2+='<span class="pill" style="--c:#0891b2" title="VCP pivot from the scan: the high of the last tightening pullback. It can be lower than the chart Base history pivot, which is the broader base high.">'+
    '<span class="long">VCP pivot </span>'+fmt(I.vcpPivot).replace(/\.00$/,'')+(I.vcpContractions?'<span class="sn"> · '+esc(I.vcpContractions)+'</span>':'')+'</span>';
  if(I.sectorStrength!=null)r2+='<span class="pill" style="--c:#7c3aed" title="Sector strength score (1-99): blended median RS, share of RS>=80 leaders and Trend Template pass rate."><span class="long">Sector strength </span>Sec '+I.sectorStrength+'</span>';
  if(I.sectorBadge)r2+='<span class="pill" style="--c:#2563eb" title="'+esc(I.sector||'')+'">'+esc(I.sectorBadge)+(I.sector?'<span class="sn"> · '+esc(I.sector)+'</span>':'')+'</span>';
  if(I.rsPeriods&&I.rsPeriods.length)r2+='<span class="rsp"><span class="lab">RS Δ<span class="long"> vs '+esc(I.benchmark||'index')+'</span></span>'+
    I.rsPeriods.map(p=>'<span class="k">'+p[0]+'</span><b class="'+(p[1]==null?'':p[1]>=0?'up':'dn')+'">'+(p[1]==null?'–':sgn(p[1],1)+'%')+'</b>').join('')+'</span>';
  r2+='</div>';
  $('hd').innerHTML=r2;
}

/* ---------- theme ---------- */
function rgb(s){const m=(s||'').match(/[\d.]+/g);return m&&m.length>=3?m.slice(0,3).map(Number):null}
function readTheme(){
  let bg,fg;
  try{let w=window.parent,d=w.document;if(!d.querySelector('.stApp')){w=w.parent;d=w.document;}
    const cs=w.getComputedStyle(d.querySelector('.stApp'));bg=cs.backgroundColor;fg=cs.color;}catch(e){}
  let b=rgb(bg),f=rgb(fg);
  if(!b||!f||bg==='rgba(0, 0, 0, 0)'){const d=matchMedia('(prefers-color-scheme: dark)').matches;b=d?[14,17,23]:[255,255,255];f=d?[250,250,250]:[31,41,55];}
  dark=(0.299*b[0]+0.587*b[1]+0.114*b[2])<128;
  const r=document.documentElement.style,a=x=>'rgba('+f.join(',')+','+x+')';
  r.setProperty('--fg','rgb('+f.join(',')+')');r.setProperty('--bg','rgb('+b.join(',')+')');
  r.setProperty('--line',a(.16));r.setProperty('--soft',a(.08));
  r.setProperty('--up',dark?'#34d399':'#16a34a');r.setProperty('--dn',dark?'#f87171':'#dc2626');
  pal={text:a(.78),grid:a(dark?.08:.06),line:a(.22),
    s10:dark?'#e5e7eb':'#111827',s20:'#d4a017',s50:'#3b82f6',s150:'#8b5cf6',s200:dark?'#f87171':'#991b1b',ema21:'#d4a017',
    up:'#22a06b',dn:'#e5484d'};
  MAS.forEach(n=>$('t_s'+n).style.setProperty('--c',pal['s'+n]));
  return pal;
}
const NARROW=()=>innerWidth<560;
function chartStyles(){
  const axis={axisLine:{color:pal.line},tickLine:{color:pal.line},tickText:{color:pal.text,size:11}};
  const tip=dark?'#475569':'#334155';
  return {grid:{horizontal:{color:pal.grid},vertical:{color:pal.grid}},
    candle:{bar:{upColor:pal.up,downColor:pal.dn,noChangeColor:'#94a3b8',upBorderColor:pal.up,downBorderColor:pal.dn,noChangeBorderColor:'#94a3b8',
                 upWickColor:pal.up,downWickColor:pal.dn,noChangeWickColor:'#94a3b8'},
            priceMark:{high:{show:false},low:{show:false},last:{upColor:pal.up,downColor:pal.dn,noChangeColor:'#94a3b8',line:{show:false}}},
            tooltip:{showRule:'none'}},
    indicator:{bars:[{style:'fill',borderStyle:'solid',borderSize:1,borderDashedValue:[2,2],upColor:'rgba(34,160,107,.55)',downColor:'rgba(229,72,77,.55)',noChangeColor:'#94a3b8'}],
               tooltip:{showRule:'always',text:{color:pal.text,size:11}},
               lastValueMark:{show:false}},
    xAxis:axis,yAxis:axis,separator:{color:pal.line},
    crosshair:{horizontal:{line:{color:pal.line},text:{backgroundColor:tip,color:'#fff'}},vertical:{line:{color:pal.line},text:{backgroundColor:tip,color:'#fff'}}}};
}

/* ---------- data ---------- */
function aggregate(kind){
  if(kind==='D')return P.bars;
  const out=[];let key0=null,cur=null;
  for(const b of P.bars){
    let key;
    if(kind==='M')key=b.date.slice(0,7);
    else{const d=new Date(b.date+'T00:00:00Z'),dow=(d.getUTCDay()+6)%7;key=new Date(d.getTime()-dow*864e5).toISOString().slice(0,10);}
    if(key!==key0){cur=Object.assign({},b);out.push(cur);key0=key;}
    else{cur.high=Math.max(cur.high,b.high);cur.low=Math.min(cur.low,b.low);cur.close=b.close;cur.volume+=b.volume;cur.rs=b.rs;cur.timestamp=b.timestamp;cur.date=b.date;}
  }
  return out;
}
function rsCalc(list){
  const w={D:252,W:52,M:12}[tf],a=data[rsBase],b0=a&&a.rs?a.rs:1;
  return list.map((k,i)=>{
    if(k.rs==null)return {rs:null,dot:null};
    const pct=(k.rs/b0-1)*100;let hi=false;
    if(i>=Math.min(w,60)){let m=-Infinity;for(let j=Math.max(0,i-w);j<=i;j++){const v=list[j].rs;if(v!=null&&v>m)m=v;}hi=k.rs>=m;}
    return {rs:pct,dot:hi?pct:null};
  });
}

/* ---------- indicators ---------- */
const BLANK=()=>({name:'',calcParamsText:'',features:[],legends:[]});
const paneOf=n=>{const i=chart.getIndicators({name:n})[0];return i&&i.paneId;};
const sizePane=(n,h)=>{const id=paneOf(n);if(id)try{chart.setPaneOptions({id,height:h});}catch(e){}};
const IND={
  vol:()=>{chart.createIndicator({name:'VOL',calcParams:[50],createTooltipDataSource:BLANK,
        styles:{lines:[{color:pal.ema21,size:1.2,style:'solid',smooth:false,dashedValue:[2,2]}]}},false);sizePane('VOL',78);},
  rs:()=>{chart.createIndicator('MP_RS_LINE',false);sizePane('MP_RS_LINE',92);}
};
const DEL={vol:'VOL',rs:'MP_RS_LINE'};
MAS.forEach(n=>{
  IND['s'+n]=()=>chart.createIndicator({id:'sma'+n,name:'MA',calcParams:[n],paneId:'candle_pane',createTooltipDataSource:BLANK,
    styles:{lines:[{color:pal['s'+n],size:n>=150?1.5:1.2,style:'solid',smooth:false,dashedValue:[2,2]}]}},true);
});
const dropInd=k=>chart.removeIndicator(DEL[k]?{name:DEL[k]}:{id:'sma'+k.slice(1)});

/* ---------- optional drawing tools (isolated from scan/chart logic) ---------- */
function drawKey(){return 'mpDrawings:'+String(P.symbol||'')+':'+String(tf);}
function hideKey(){return 'mpDrawHidden:'+String(P.symbol||'')+':'+String(tf);}
function readSaved(){try{const v=JSON.parse(localStorage.getItem(drawKey())||'[]');return Array.isArray(v)?v:[];}catch(e){return [];}}
function writeSaved(v){try{localStorage.setItem(drawKey(),JSON.stringify(v||[]));}catch(e){}}
function readHidden(){try{return localStorage.getItem(hideKey())==='1';}catch(e){return false;}}
function writeHidden(v){try{localStorage.setItem(hideKey(),v?'1':'0');}catch(e){}}
function drawOverlays(){try{return chart?(chart.getOverlays({groupId:DRAW_GID})||[]):[];}catch(e){return [];}}
function dropIncomplete(){drawOverlays().forEach(o=>{if((o.points||[]).length<needPts(o.name))try{chart.removeOverlay({id:o.id});}catch(e){}});}
function serializeDraw(){
  const out=[];
  drawOverlays().forEach(o=>{
    const pts=(o.points||[]).filter(p=>p&&typeof p.timestamp==='number').map(p=>({timestamp:p.timestamp,value:p.value,dataIndex:p.dataIndex}));
    if(pts.length<needPts(o.name))return;
    const item={name:o.name,points:pts,mode:o.mode||'normal'};
    if(o.extendData!==undefined)item.extendData=o.extendData;
    if(o.styles)item.styles=o.styles;
    out.push(item);
  });
  return out;
}
function restoreDraw(list){
  if(!chart)return;
  try{chart.removeOverlay({groupId:DRAW_GID});}catch(e){}
  (list||[]).forEach(o=>{
    try{chart.createOverlay({name:o.name,groupId:DRAW_GID,mode:o.mode||'normal',visible:!drawHidden,points:o.points,extendData:o.extendData,styles:o.styles});}catch(e){}
  });
}
function setDrawHidden(v,persist=true){
  drawHidden=!!v;
  if(persist)writeHidden(drawHidden);
  try{chart.overrideOverlay({groupId:DRAW_GID,visible:!drawHidden});}catch(e){}
  const b=$('uhide');
  if(b){b.textContent=drawHidden?'🙈 Show drawing':'🙈 Hide drawing';b.classList.toggle('on',drawHidden);}
}
function persistIfChanged(){
  const cur=serializeDraw(),k=JSON.stringify(cur);
  if(k===lastSnap)return;
  writeSaved(cur);hist.push(cur);if(hist.length>60)hist.shift();future=[];lastSnap=k;
}
function commitDraw(){setTimeout(persistIfChanged,0);}
function undoDraw(){
  if(hist.length<2)return;
  future.push(hist.pop());const s=hist[hist.length-1];restoreDraw(s);writeSaved(s);
  const cur=serializeDraw();hist[hist.length-1]=cur;lastSnap=JSON.stringify(cur);
}
function redoDraw(){
  if(!future.length)return;
  const s=future.pop();hist.push(s);restoreDraw(s);writeSaved(s);
  const cur=serializeDraw();hist[hist.length-1]=cur;lastSnap=JSON.stringify(cur);
}
function deleteDraw(){
  const list=drawOverlays();if(!list.length)return;
  try{chart.removeOverlay({id:list[list.length-1].id});}catch(e){}
  commitDraw();
}
function clearDraw(){
  const cur=serializeDraw();
  try{chart.removeOverlay({groupId:DRAW_GID});}catch(e){}
  setDrawHidden(false);writeSaved([]);
  hist.push(cur);if(hist.length>60)hist.shift();future=[];lastSnap='[]';
}
function toggleToolPanel(force){
  const open=typeof force==='boolean'?force:!$('tools').classList.contains('open');
  $('tools').classList.toggle('open',open);
  $('tdraw').classList.toggle('on',open);
  $('tdraw').setAttribute('aria-expanded',open?'true':'false');
  if(!open){dropIncomplete();setActiveTool(null);}
}
function setActiveTool(t){
  activeTool=t||null;
  document.querySelectorAll('#toolpanel [data-tool]').forEach(b=>b.classList.toggle('on',b.dataset.tool===activeTool));
  $('chart').style.cursor=activeTool?'crosshair':'default';
}
function promptText(t){
  if(t==='price'){
    let v='';try{v=window.prompt('Price label (optional)','')||'';}catch(e){v='';}
    return String(v).trim();
  }
  if(t!=='text'&&t!=='callout')return undefined;
  let v='';
  try{v=window.prompt(t==='text'?'Text label':'Callout text',t==='text'?'Label':'Callout');}catch(e){v=t==='text'?'Label':'Callout';}
  if(v==null||!String(v).trim())return null;
  return String(v).trim();
}
function startDraw(t){
  if(!chart||!TOOLS[t])return;
  if(activeTool===t){dropIncomplete();setActiveTool(null);return;}
  dropIncomplete();
  if(drawHidden)setDrawHidden(false);
  const cfg=TOOLS[t],ext=promptText(t);
  if(ext===null)return;
  const o={name:cfg.name,groupId:DRAW_GID,visible:true,
    onDrawEnd:()=>setTimeout(()=>{setActiveTool(null);commitDraw();},0)};
  if(cfg.styles)o.styles=cfg.styles;
  if(ext!==undefined&&ext!=='')o.extendData=ext;
  try{chart.createOverlay(o);setActiveTool(t);}catch(e){setActiveTool(null);}
}

/* ---------- bases ---------- */
const tsOf=s=>{const a=s.split('-').map(Number);return Date.UTC(a[0],a[1]-1,a[2])-330*60000};
function drawBases(){
  try{chart.removeOverlay({name:'mpBase'});chart.removeOverlay({name:'mpUser'});}catch(e){}
  const last=P.bars[P.bars.length-1];
  if(on.base)(P.bases||[]).forEach(b=>{
    const label=b._forming?('Pivot '+fmt(b._pivot).replace(/\.00$/,'')+' ('+sgn((last.close/b._pivot-1)*100,1)+'%)'):'';
    chart.createOverlay({name:'mpBase',lock:true,points:[{timestamp:tsOf(b._start),value:b._pivot},{timestamp:tsOf(b._end),value:b._low}],
      extendData:{n:b._n,forming:!!b._forming,label}});
  });
  if(P.start&&P.end&&P.pivot){
    const dash=c=>({line:{style:'dashed',color:c,size:1}});
    chart.createOverlay({name:'verticalStraightLine',points:[{timestamp:tsOf(P.start)}],styles:dash('#8b5cf6'),lock:true});
    chart.createOverlay({name:'verticalStraightLine',points:[{timestamp:tsOf(P.end)}],styles:dash('#8b5cf6'),lock:true});
    chart.createOverlay({name:'priceLine',points:[{timestamp:tsOf(P.end),value:P.pivot}],styles:dash('#f59e0b'),lock:true});
  }
}

/* --- VCP BOX START (rollback-safe overlay drawing) --- */
function drawVcp(){
  try{chart.removeOverlay({groupId:'mpVcp'});}catch(e){}
  if(!on.vcp||!P.vcp||!P.vcp.length||!data.length)return;
  const b=P.vcp[0],pivot=Number(b._pivot),bottom=Number(b._bottom);
  if(!Number.isFinite(pivot)||!Number.isFinite(bottom)||bottom>=pivot)return;
  const left=idxOfDate(b._left),low=idxOfDate(b._low),right=idxOfDate(b._right);
  const mark=b._breakout?idxOfDate(b._breakout):right;
  chart.createOverlay({name:'mpVcp',groupId:'mpVcp',lock:true,
    points:[{timestamp:data[left].timestamp,value:pivot},
            {timestamp:data[low].timestamp,value:bottom},
            {timestamp:data[right].timestamp,value:pivot},
            {timestamp:data[mark].timestamp,value:pivot}],
    extendData:{n:'V1',breakout:!!b._breakout,vol:b._vol,pullbacks:b._pullbacks||''}});
}
/* --- VCP BOX END --- */

/* --- DARVAS BOX START (rollback-safe overlay drawing) --- */
const idxOfDate=s=>{
  if(!s||!data.length)return Math.max(0,data.length-1);
  const t=tsOf(s);let best=0,diff=Infinity;
  for(let i=0;i<data.length;i++){const d=Math.abs(data[i].timestamp-t);if(d<diff){diff=d;best=i;}}
  return best;
};
function drawDarvas(){
  try{chart.removeOverlay({groupId:'mpDarvas'});}catch(e){}
  if(!on.darvas||!data.length)return;
  (P.darvas||[]).forEach((b,i)=>{
    const top=Number(b._top),stop=Number(b._bottom);
    if(!Number.isFinite(top)||!Number.isFinite(stop)||stop>=top)return;
    let iTop=idxOfDate(b._top_date),iBot=idxOfDate(b._bottom_date);
    let iEnd=idxOfDate(b._end_date||b._breakout_date||data[data.length-1].date);
    if(iEnd<=iTop)iEnd=Math.min(data.length-1,iTop+1);
    if(iBot<=iTop)iBot=Math.min(iEnd,iTop+1);
    let iBrk=b._breakout_date?idxOfDate(b._breakout_date):iEnd;
    iBrk=Math.max(iBot,Math.min(iEnd,iBrk));
    chart.createOverlay({name:'mpDarvas',groupId:'mpDarvas',lock:true,
      points:[{timestamp:data[iTop].timestamp,value:top},
              {timestamp:data[iBot].timestamp,value:stop},
              {timestamp:data[iEnd].timestamp,value:top},
              {timestamp:data[iBrk].timestamp,value:top}],
      extendData:{n:b._n||(i+1),breakout:!!b._breakout,vol:b._vol,status:b._status||''}});
  });
}
/* --- DARVAS BOX END --- */

/* ---------- legend (OHLC + 52-week) ---------- */
function legend(i){
  const k=data[i]||data[data.length-1],p=data[(data.indexOf(k))-1];
  const chg=p?(k.close/p.close-1)*100:0,c=chg>=0?'up':'dn';
  const d=P.bars,n=Math.min(252,d.length);let hi=-1,lo=1e18;
  for(let j=d.length-n;j<d.length;j++){if(d[j].high>hi)hi=d[j].high;if(d[j].low<lo)lo=d[j].low;}
  const cl=d[d.length-1].close;
  const dt=k.date?new Date(k.date+'T00:00:00Z').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'2-digit',timeZone:'UTC'}):'';
  $('lg').innerHTML='<div><span class="dt">'+dt+'</span><span class="m">O</span> '+fmt(k.open)+'<span class="m">H</span> '+fmt(k.high)+'<span class="m">L</span> '+fmt(k.low)+
    '<span class="m">C</span> '+fmt(k.close)+' <b class="'+c+'">'+sgn(chg,2)+'%</b></div>'+
    '<div class="hl">52w high '+fmt(hi).replace(/\.00$/,'')+' ('+sgn((cl/hi-1)*100,1)+'%) <span style="opacity:.6;font-weight:400">· low '+fmt(lo).replace(/\.00$/,'')+'</span></div>';
}

/* ---------- range / zoom ---------- */
function setRange(r){
  rng=r;document.querySelectorAll('#rng button').forEach(b=>b.classList.toggle('on',b.dataset.r===r));
  if(!chart)return;
  const n=Math.max(8,Math.min(SPANS[tf][r],data.length)),gap=NARROW()?16:48,w=Math.max(200,$('chart').clientWidth-64-gap);
  try{chart.setOffsetRightDistance(gap);}catch(e){}
  chart.setBarSpace(Math.max(1,Math.min(50,w/n)));chart.scrollToRealTime();
  const nb=Math.max(0,data.length-n);
  if(on.rs&&nb!==rsBase){rsBase=nb;try{chart.removeIndicator({name:'MP_RS_LINE'});IND.rs();}catch(e){}}else rsBase=nb;
}
function setTF(t){
  if(t===tf)return;
  writeSaved(serializeDraw());
  tf=t;data=aggregate(t);document.querySelectorAll('#tf button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
  rsBase=0;chart.setPeriod({span:1,type:PERIOD[t]});
  setTimeout(()=>{
    drawBases();drawVcp();drawDarvas();restoreDraw(readSaved());setDrawHidden(readHidden(),false);
    const cur=serializeDraw();hist=[cur];future=[];lastSnap=JSON.stringify(cur);
    setRange(rng);legend();
  },160);
}

/* ---------- start ---------- */
function start(){
  readTheme();header();
  $('ft').textContent=P.footer||'';
  if(!window.klinecharts){$('chart').innerHTML='<div class="err">Chart library did not load. Check the network and reload.</div>';return;}
  try{const f=window.frameElement;if(f){const vh=window.parent.innerHeight||0;
    if(vh){const h=Math.max(560,Math.min(Math.round(vh*(((window.parent.innerWidth)||innerWidth)<560?.95:.82)),P.height||760));f.style.height=h+'px';f.setAttribute('height',h);try{const w=f.parentElement,o=w.getBoundingClientRect().height;w.style.marginBottom=(h-o)+'px';}catch(e){}}}}catch(e){}
  const bench=(I&&I.benchmark)||'index';
  try{klinecharts.registerIndicator({name:'MP_RS_LINE',shortName:'RS',series:'normal',precision:1,
    figures:[{key:'rs',title:'',type:'line',styles:()=>({color:dark?'#4ade80':'#15803d',size:1.6})},
             {key:'dot',title:'',type:'circle',
              attrs:({coordinate})=>coordinate.current&&coordinate.current.dot!=null?{x:coordinate.current.x,y:coordinate.current.dot,r:2.8}:null,
              styles:()=>({style:'fill',color:'#2563eb',borderColor:'#2563eb'})}],
    createTooltipDataSource:()=>({name:'RS line vs '+bench+' (% since start of chart)',calcParamsText:'',features:[],legends:[]}),
    calc:rsCalc});}catch(e){}
  try{klinecharts.registerIndicator({name:'MP_HLC',shortName:'HLC',series:'price',precision:2,figures:[],calc:l=>l.map(()=>({})),
    draw:({ctx,chart:c,xAxis,yAxis})=>{
      const list=c.getDataList(),vr=c.getVisibleRange(),bs=c.getBarSpace().bar,tick=Math.max(2,Math.min(8,bs*.45));
      ctx.lineWidth=Math.max(1,Math.min(2,bs/4));ctx.lineCap='butt';
      for(let i=Math.max(0,vr.from);i<Math.min(list.length,vr.to);i++){
        const k=list[i],p=list[i-1],x=xAxis.convertToPixel(i);
        ctx.strokeStyle=(!p||k.close>=p.close)?pal.up:pal.dn;
        const yh=yAxis.convertToPixel(k.high),yl=yAxis.convertToPixel(k.low),yc=yAxis.convertToPixel(k.close);
        ctx.beginPath();ctx.moveTo(x,yh);ctx.lineTo(x,yl);ctx.moveTo(x,yc);ctx.lineTo(x+tick,yc);ctx.stroke();
      }
      return true;}});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpBase',totalStep:3,lock:true,needDefaultPointFigure:false,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,bounding,overlay})=>{
      if(!coordinates||coordinates.length<2)return [];
      const d=overlay.extendData||{},x0=coordinates[0].x,y0=coordinates[0].y,y1=coordinates[1].y;
      const x1=d.forming?bounding.width:coordinates[1].x,blue='#3b82f6';
      const out=[
        {type:'rect',attrs:{x:x0,y:y0,width:Math.max(1,x1-x0),height:Math.max(1,y1-y0)},styles:{style:'fill',color:dark?'rgba(96,165,250,.16)':'rgba(59,130,246,.10)'}},
        {type:'line',attrs:{coordinates:[{x:x0,y:y0},{x:x1,y:y0}]},styles:{style:'dashed',color:blue,size:1,dashedValue:[4,3]}},
        {type:'circle',attrs:{x:x0+13,y:y0+14,r:9},styles:{style:'fill',color:'#2563eb',borderColor:'#2563eb'}},
        {type:'text',attrs:{x:x0+13,y:y0+14,text:String(d.n),align:'center',baseline:'middle'},styles:{color:'#fff',size:11,weight:'bold',backgroundColor:'transparent',borderSize:0}}];
      if(d.forming&&d.label){const need=d.label.length*6.3+34,left=x0+need<bounding.width;
        out.push({type:'text',attrs:{x:left?x0+28:bounding.width-6,y:y0-9,text:d.label,align:left?'left':'right',baseline:'middle'},styles:{color:blue,size:11,backgroundColor:'transparent',borderSize:0}});}
      return out;
    }});}catch(e){}
  /* --- VCP BOX START (rollback-safe overlay registration) --- */
  try{klinecharts.registerOverlay({name:'mpVcp',totalStep:4,lock:true,needDefaultPointFigure:false,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,bounding,overlay})=>{
      if(!coordinates||coordinates.length<4)return [];
      const d=overlay.extendData||{},x0=coordinates[0].x,xb=coordinates[1].x,x1=coordinates[2].x,xm=coordinates[3].x;
      const yt=coordinates[0].y,yb=coordinates[1].y;
      if(![x0,xb,x1,xm,yt,yb].every(Number.isFinite))return [];
      const teal='#0891b2',gold='#f59e0b',red='#dc2626';
      const bw=(bounding&&bounding.width)||3000,ry=Math.min(yt,yb),rh=Math.max(2,Math.abs(yb-yt));
      const out=[
        {type:'rect',attrs:{x:x0,y:ry,width:Math.max(2,x1-x0),height:rh},styles:{style:'fill',color:dark?'rgba(8,145,178,.16)':'rgba(8,145,178,.09)'}},
        {type:'line',attrs:{coordinates:[{x:x0,y:yt},{x:x1,y:yt}]},styles:{style:'dashed',color:teal,size:1.4,dashedValue:[5,3]}},
        {type:'line',attrs:{coordinates:[{x:xb,y:yb},{x:x1,y:yb}]},styles:{style:'dashed',color:red,size:1.2,dashedValue:[5,3]}},
        {type:'line',attrs:{coordinates:[{x:x0,y:ry},{x:x0,y:ry+rh}]},styles:{color:teal,size:1.4}},
        {type:'line',attrs:{coordinates:[{x:x1,y:ry},{x:x1,y:ry+rh}]},styles:{style:'dashed',color:teal,size:1.2,dashedValue:[4,3]}},
        {type:'circle',attrs:{x:x0+13,y:ry+14,r:9},styles:{style:'fill',color:teal,borderColor:teal}},
        {type:'text',attrs:{x:x0+13,y:ry+14,text:'V1',align:'center',baseline:'middle'},styles:{color:'#fff',size:10,weight:'bold',backgroundColor:'transparent',borderSize:0}}];
      if(d.breakout){
        const bx=Math.max(30,Math.min(bw-30,xm));
        out.push({type:'line',attrs:{coordinates:[{x:bx,y:yt-3},{x:bx,y:yt-18}]},styles:{color:gold,size:1.7}});
        out.push({type:'text',attrs:{x:bx,y:yt-20,text:d.vol!=null?('B '+Number(d.vol).toFixed(1)+'×'):'BREAKOUT',align:'center',baseline:'bottom'},
          styles:{color:gold,size:10,weight:'bold',backgroundColor:'transparent',borderSize:0}});
      }else{
        out.push({type:'text',attrs:{x:Math.max(30,Math.min(bw-30,x1)),y:ry-8,text:'BUILDING',align:'center',baseline:'bottom'},
          styles:{color:teal,size:10,weight:'bold',backgroundColor:'transparent',borderSize:0}});
      }
      return out;
    }});}catch(e){}
  /* --- VCP BOX END --- */
  /* --- DARVAS BOX START (rollback-safe overlay registration) --- */
  try{klinecharts.registerOverlay({name:'mpDarvas',totalStep:4,lock:true,needDefaultPointFigure:false,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,bounding,overlay})=>{
      if(!coordinates||coordinates.length<4)return [];
      const d=overlay.extendData||{},x0=coordinates[0].x,xb=coordinates[1].x,x1=coordinates[2].x,xbr=coordinates[3].x;
      const yt=coordinates[0].y,yb=coordinates[1].y;
      if(![x0,xb,x1,xbr,yt,yb].every(Number.isFinite))return [];
      const up=!!d.breakout,gold='#f59e0b',red='#dc2626',purple='#8b5cf6';
      const bw=(bounding&&bounding.width)||3000,ry=Math.min(yt,yb),rh=Math.max(2,Math.abs(yb-yt));
      const fill=up?(dark?'rgba(16,185,129,.14)':'rgba(16,185,129,.08)'):(dark?'rgba(139,92,246,.14)':'rgba(139,92,246,.07)');
      const out=[
        {type:'rect',attrs:{x:x0,y:ry,width:Math.max(2,x1-x0),height:rh},styles:{style:'fill',color:fill}},
        {type:'line',attrs:{coordinates:[{x:x0,y:yt},{x:x1,y:yt}]},styles:{style:'dashed',color:gold,size:1.3,dashedValue:[5,3]}},
        {type:'line',attrs:{coordinates:[{x:xb,y:yb},{x:x1,y:yb}]},styles:{style:'dashed',color:red,size:1.3,dashedValue:[5,3]}},
        {type:'circle',attrs:{x:x0+13,y:yt+14,r:9},styles:{style:'fill',color:purple,borderColor:purple}},
        {type:'text',attrs:{x:x0+13,y:yt+14,text:'D'+String(d.n||''),align:'center',baseline:'middle'},styles:{color:'#fff',size:10,weight:'bold',backgroundColor:'transparent',borderSize:0}}];
      if(up){
        const bx=Math.max(30,Math.min(bw-30,xbr));
        out.push({type:'line',attrs:{coordinates:[{x:bx,y:yt-3},{x:bx,y:yt-18}]},styles:{color:gold,size:1.6}});
        out.push({type:'text',attrs:{x:bx,y:yt-20,text:d.vol!=null?('B '+Number(d.vol).toFixed(1)+'×'):'BREAKOUT',align:'center',baseline:'bottom'},
          styles:{color:gold,size:10,weight:'bold',backgroundColor:'transparent',borderSize:0}});
      }
      return out;
    }});}catch(e){}
  /* --- DARVAS BOX END --- */
  try{klinecharts.registerOverlay({name:'mpRect',totalStep:3,needDefaultPointFigure:true,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates})=>{
      if(!coordinates||coordinates.length<2)return [];
      const a=coordinates[0],b=coordinates[1];
      return {type:'rect',attrs:{x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.max(2,Math.abs(a.x-b.x)),height:Math.max(2,Math.abs(a.y-b.y))},
        styles:{style:'stroke',color:'#f59e0b',borderColor:'#f59e0b',size:1.6}};
    }});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpText',totalStep:2,needDefaultPointFigure:false,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,overlay})=>{
      if(!coordinates||!coordinates.length)return [];
      return {type:'text',attrs:{x:coordinates[0].x+8,y:coordinates[0].y-8,text:String(overlay.extendData||''),baseline:'bottom'},
        styles:{color:'#f59e0b',size:12,backgroundColor:'transparent',borderSize:0}};
    }});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpMeasure',totalStep:3,needDefaultPointFigure:true,needDefaultXAxisFigure:true,needDefaultYAxisFigure:true,
    createPointFigures:({coordinates,overlay})=>{
      if(!coordinates||coordinates.length<2)return [];
      const a=overlay.points[0]||{},b=overlay.points[1]||{};let txt='';
      if(typeof a.value==='number'&&typeof b.value==='number'&&a.value){
        const pct=(b.value/a.value-1)*100,bars=Math.abs((b.dataIndex||0)-(a.dataIndex||0));
        txt=(pct>=0?'+':'')+pct.toFixed(2)+'% · '+bars+' bars';
      }
      const mid={x:(coordinates[0].x+coordinates[1].x)/2,y:(coordinates[0].y+coordinates[1].y)/2};
      const out=[{type:'line',attrs:{coordinates},styles:{color:'#0ea5e9',size:1.4,style:'dashed',dashedValue:[4,3]}}];
      if(txt)out.push({type:'text',attrs:{x:mid.x,y:mid.y-8,text:txt,align:'center',baseline:'bottom'},styles:{color:'#0ea5e9',size:11,backgroundColor:'transparent',borderSize:0}});
      return out;
    }});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpArrow',totalStep:3,needDefaultPointFigure:true,needDefaultXAxisFigure:true,needDefaultYAxisFigure:true,
    createPointFigures:({coordinates})=>{
      if(!coordinates||coordinates.length<2)return [];
      const a=coordinates[0],b=coordinates[1],dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy)||1;
      if(len<4)return [];
      const ux=dx/len,uy=dy/len,base={x:b.x-ux*12,y:b.y-uy*12},px=-uy*6,py=ux*6;
      return [
        {type:'line',attrs:{coordinates:[a,{x:base.x,y:base.y}]},styles:{color:'#0ea5e9',size:1.8}},
        {type:'polygon',attrs:{coordinates:[b,{x:base.x+px,y:base.y+py},{x:base.x-px,y:base.y-py}]},
          styles:{style:'fill',color:'#0ea5e9',borderColor:'#0ea5e9',borderSize:1}}
      ];
    }});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpPrice',totalStep:2,needDefaultPointFigure:false,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,bounding,overlay})=>{
      if(!coordinates||!coordinates.length)return [];
      const y=coordinates[0].y,p=overlay.points&&overlay.points[0],val=p&&typeof p.value==='number'?fmt(p.value):'';
      const extra=String(overlay.extendData||'').trim(),text=(extra?extra+' · ':'')+val;
      const w=Math.max(58,text.length*6.4+14),x=Math.max(4,bounding.width-w-4);
      return [
        {type:'line',attrs:{coordinates:[{x:0,y},{x:bounding.width,y}]},styles:{color:'#f59e0b',size:1.2,style:'dashed',dashedValue:[4,3]}},
        {type:'rect',attrs:{x,y:y-10,width:w,height:20},styles:{style:'fill',color:dark?'rgba(245,158,11,.22)':'rgba(245,158,11,.14)',borderColor:'#f59e0b',borderSize:1}},
        {type:'text',attrs:{x:x+w/2,y,text,align:'center',baseline:'middle'},styles:{color:'#f59e0b',size:11,weight:'bold',backgroundColor:'transparent',borderSize:0}}
      ];
    }});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpCallout',totalStep:3,needDefaultPointFigure:true,needDefaultXAxisFigure:false,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,bounding,overlay})=>{
      if(!coordinates||coordinates.length<2)return [];
      const a=coordinates[0],b=coordinates[1],text=String(overlay.extendData||'Callout');
      const w=Math.max(70,Math.min(190,text.length*6.2+20)),h=34;
      const x=Math.max(3,Math.min(bounding.width-w-3,b.x-w/2)),y=Math.max(3,Math.min(bounding.height-h-3,b.y-h/2));
      return [
        {type:'line',attrs:{coordinates:[a,{x:x+w/2,y:y+h/2}]},styles:{color:'#8b5cf6',size:1.3}},
        {type:'rect',attrs:{x,y,width:w,height:h},styles:{style:'fill',color:'#8b5cf6',borderColor:'#8b5cf6',borderSize:1}},
        {type:'text',attrs:{x:x+w/2,y:y+h/2,text,align:'center',baseline:'middle'},styles:{color:'#fff',size:11,backgroundColor:'transparent',borderSize:0}}
      ];
    }});}catch(e){}
  try{klinecharts.registerOverlay({name:'mpDateRange',totalStep:3,needDefaultPointFigure:true,needDefaultXAxisFigure:true,needDefaultYAxisFigure:false,
    createPointFigures:({coordinates,bounding,overlay})=>{
      if(!coordinates||coordinates.length<2)return [];
      let x0=Math.min(coordinates[0].x,coordinates[1].x),x1=Math.max(coordinates[0].x,coordinates[1].x);
      x0=Math.max(0,x0);x1=Math.min(bounding.width,x1);
      const pts=overlay.points||[];
      const ds=i=>{const p=pts[i];return p&&typeof p.timestamp==='number'
        ?new Date(p.timestamp+330*60000).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'2-digit',timeZone:'UTC'}):'';};
      const lab=ds(0)+' → '+ds(1);
      const out=[{type:'rect',attrs:{x:x0,y:0,width:Math.max(2,x1-x0),height:bounding.height},
        styles:{style:'fill',color:dark?'rgba(14,165,233,.12)':'rgba(14,165,233,.08)'}}];
      [x0,x1].forEach(x=>out.push({type:'line',attrs:{coordinates:[{x,y:0},{x,y:bounding.height}]},
        styles:{color:'#0ea5e9',size:1.2,style:'dashed',dashedValue:[4,3]}}));
      if(lab)out.push({type:'text',attrs:{x:Math.min(bounding.width-4,Math.max(4,(x0+x1)/2)),y:14,text:lab,align:'center',baseline:'middle'},
        styles:{color:'#0ea5e9',size:10.5,backgroundColor:'transparent',borderSize:0}});
      return out;
    }});}catch(e){}
  chart=klinecharts.init('chart');chart.setTimezone('Asia/Kolkata');chart.setStyles(chartStyles());
  chart.setSymbol({ticker:P.symbol,pricePrecision:2,volumePrecision:0});chart.setPeriod({span:1,type:'day'});
  chart.setLocale('en-US');chart.setDataLoader({getBars:({callback})=>callback(data)});
  ['s10','s20','s50','s150','s200','vol','rs'].forEach(k=>IND[k]());
  chart.subscribeAction('onCrosshairChange',c=>{
    if(!c||c.x==null){legend();return;}
    let i;
    try{const r=chart.convertFromPixel({x:c.x,y:c.y},{paneId:'candle_pane'});i=r&&r.dataIndex;}catch(e){}
    legend(typeof i==='number'&&i>=0&&i<data.length?i:undefined);
  });
  $('chart').addEventListener('mouseleave',()=>legend());
  $('chart').addEventListener('mouseup',()=>setTimeout(commitDraw,40));
  $('chart').addEventListener('contextmenu',()=>setTimeout(commitDraw,60));
  setTimeout(()=>{
    drawBases();drawVcp();drawDarvas();restoreDraw(readSaved());setDrawHidden(readHidden(),false);
    const cur=serializeDraw();hist=[cur];future=[];lastSnap=JSON.stringify(cur);
    setRange(rng);legend();
  },250);
  new ResizeObserver(()=>{chart.resize();setRange(rng);}).observe($('chart'));
}
$('rng').innerHTML=RLIST.map(r=>'<button type="button" data-r="'+r+'">'+r+'</button>').join('');
$('rng').onclick=e=>{const r=e.target.dataset&&e.target.dataset.r;if(r)setRange(r);};
$('tf').onclick=e=>{const t=e.target.dataset&&e.target.dataset.t;if(t&&t!==tf)setTF(t);};
function barStyle(hide){
  const c=hide?'rgba(0,0,0,0)':null,g='#94a3b8';
  return {upColor:c||pal.up,downColor:c||pal.dn,noChangeColor:c||g,upBorderColor:c||pal.up,downBorderColor:c||pal.dn,noChangeBorderColor:c||g,
          upWickColor:c||pal.up,downWickColor:c||pal.dn,noChangeWickColor:c||g};
}
function setType(v){
  const hlc=v==='hlc';
  chart.setStyles({candle:{type:hlc?'ohlc':v,bar:barStyle(hlc)}});
  try{chart.removeIndicator({name:'MP_HLC'});}catch(e){}
  if(hlc)chart.createIndicator({name:'MP_HLC',paneId:'candle_pane',createTooltipDataSource:BLANK},true);
}
$('ctype').onchange=e=>setType(e.target.value);
$('zin').onclick=()=>{const b=chart.getBarSpace().bar;chart.setBarSpace(Math.min(50,b*1.3));document.querySelectorAll('#rng button').forEach(x=>x.classList.remove('on'));};
$('zout').onclick=()=>{const b=chart.getBarSpace().bar;chart.setBarSpace(Math.max(1,b/1.3));document.querySelectorAll('#rng button').forEach(x=>x.classList.remove('on'));};
['s10','s20','s50','s150','s200','vol','rs','vcp','base','darvas'].forEach(k=>$('t_'+k).onclick=()=>{
  on[k]=!on[k];$('t_'+k).classList.toggle('on',on[k]);
  /* --- VCP BOX START (rollback-safe toggle) --- */
  if(k==='vcp'){drawVcp();return;}
  /* --- VCP BOX END --- */
  if(k==='base'){drawBases();return;}
  /* --- DARVAS BOX START (rollback-safe toggle) --- */
  if(k==='darvas'){drawDarvas();return;}
  /* --- DARVAS BOX END --- */
  try{if(on[k])IND[k]();else dropInd(k);}catch(e){}
  setTimeout(()=>setRange(rng),30);
});
$('tools').onclick=e=>{
  const b=e.target&&e.target.closest?e.target.closest('button'):null;if(!b)return;
  if(b.id==='tdraw'){toggleToolPanel();return;}
  if(b.dataset.tool){startDraw(b.dataset.tool);return;}
  if(b.id==='uundo')undoDraw();
  else if(b.id==='uredo')redoDraw();
  else if(b.id==='udel')deleteDraw();
  else if(b.id==='uclear')clearDraw();
  else if(b.id==='uhide')setDrawHidden(!drawHidden);
};
document.addEventListener('keydown',e=>{
  const k=(e.key||'').toLowerCase();
  if((e.ctrlKey||e.metaKey)&&k==='z'){e.preventDefault();e.shiftKey?redoDraw():undoDraw();}
  else if((e.ctrlKey||e.metaKey)&&k==='y'){e.preventDefault();redoDraw();}
  else if(k==='delete'||k==='backspace'){e.preventDefault();deleteDraw();}
  else if(k==='escape'){dropIncomplete();setActiveTool(null);}
});
window.addEventListener('beforeunload',()=>writeSaved(serializeDraw()));
document.querySelectorAll('#tf button').forEach(b=>b.classList.toggle('on',b.dataset.t===tf));
document.querySelectorAll('#rng button').forEach(b=>b.classList.toggle('on',b.dataset.r===rng));
start();
</script></body></html>
"""


def chart_explorer(bars, symbol: str, base_start: str, base_end: str, pivot: float,
                   base_history=None, vcp_history=None, darvas_history=None, visible_window="1Y", height: int = 760,
                   info=None, footer: str = "") -> None:
    """Render the transient stock chart: header, D/W/M, range buttons, indicator toggles,
    numbered base boxes, the scanner VCP pivot box, Darvas boxes, volume and RS-line panes.
    Everything is drawn in the browser from the bars passed in, so switching timeframe or range
    never reruns Streamlit.

    `base_start` / `base_end` / `pivot` draw an optional manual marker (pass "" / "" / 0 to skip).
    `vcp_history` adds the scanner-style VCP box with true left/right boundaries and a breakout
    marker; `darvas_history` adds an isolated Darvas overlay. Both have their own chips and the
    base markers stay independent.
    `info` fills the header (symbol, company, price, RS, stage...); omit it to hide the header.
    """
    window = str(visible_window).upper()
    window = window if window in ("3M", "6M", "1Y", "2Y", "5Y") else "1Y"
    bases = [{k: v for k, v in row.items() if str(k).startswith("_")} for row in (base_history or [])
             if row.get("_start")]
    # --- VCP BOX START (rollback-safe payload) ---
    vcp = [{k: v for k, v in row.items() if str(k).startswith("_")}
           for row in (vcp_history or []) if row.get("_left")]
    # --- VCP BOX END ---
    # --- DARVAS BOX START (rollback-safe payload) ---
    darvas = [{k: v for k, v in row.items() if str(k).startswith("_")}
              for row in (darvas_history or []) if row.get("_top_date")]
    # --- DARVAS BOX END ---
    payload = json.dumps({"symbol": symbol, "bars": bars, "start": base_start or "", "end": base_end or "",
                          "pivot": float(pivot or 0), "bases": bases,
                          # --- VCP BOX START (rollback-safe payload) ---
                          "vcp": vcp,
                          # --- VCP BOX END ---
                          # --- DARVAS BOX START (rollback-safe payload) ---
                          "darvas": darvas,
                          # --- DARVAS BOX END ---
                          "range": window,
                          "height": int(height), "info": info, "footer": footer}).replace("</", "<\\/")
    html = _CHART_HTML.replace("__KLINE_SRC__", _KLINE_SRC).replace("__PAYLOAD__", payload)
    _embed(html, int(height))
