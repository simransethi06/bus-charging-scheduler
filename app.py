"""
app.py — Exponent Energy · Bus Charging Scheduler
Killer UI: electric bus hero, dark/light mode, all plotly errors fixed
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from pathlib import Path

from scheduler.runner import run_scenario, get_all_scenarios
from scheduler.models import ScheduleResult, BusTimeline, ChargeEvent, Direction

st.set_page_config(
    page_title="Exponent Energy · Charging Scheduler",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

def palette(dark):
    if dark:
        return dict(
            bg="#060A12", bg2="#0A1020", bg3="#0E1628", bg4="#121E34",
            card="#0D1828", border="#1C2E4A", border2="#243A5E",
            text="#EEF2FF", text2="#7A8FAE", text3="#3D5070",
            accent="#FFD000", accent2="#FF8C00",
            blue="#1E7FFF", green="#00D97E", red="#FF4757",
            purple="#A855F7", teal="#06B6D4", orange="#F97316",
            plot_bg="#0A1020", grid="#1C2E4A",
        )
    else:
        return dict(
            bg="#F5F7FF", bg2="#FFFFFF", bg3="#EBF0FF", bg4="#E0E8FF",
            card="#FFFFFF", border="#C8D5F0", border2="#AABDE0",
            text="#0A1628", text2="#3A5070", text3="#8AA0C0",
            accent="#D4A500", accent2="#E06000",
            blue="#1155CC", green="#15803D", red="#CC2222",
            purple="#7E22CE", teal="#0E7490", orange="#C2410C",
            plot_bg="#FFFFFF", grid="#DDE8FF",
        )

P = palette(st.session_state.dark_mode)
DARK = st.session_state.dark_mode

OP_COLORS = {"kpn": P["blue"], "freshbus": P["green"], "flixbus": P["purple"]}
STN_COLORS = {"A": P["accent"], "B": P["blue"], "C": P["purple"], "D": P["teal"]}

# ─── Electric bus SVG (side-profile, scalable) ────────────────────────────────
BUS_SVG = """
<svg viewBox="0 0 320 100" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
  <defs>
    <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1E3A5F"/>
      <stop offset="100%" stop-color="#0A1E35"/>
    </linearGradient>
    <linearGradient id="windowGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#7FAAFF" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#1E5FBF" stop-opacity="0.3"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <!-- body -->
  <rect x="10" y="28" width="285" height="52" rx="8" fill="url(#bodyGrad)" stroke="#1E4080" stroke-width="1"/>
  <!-- accent stripe -->
  <rect x="10" y="42" width="285" height="4" fill="#FFD000" opacity="0.9"/>
  <!-- windows -->
  <rect x="30" y="33" width="28" height="18" rx="3" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <rect x="65" y="33" width="28" height="18" rx="3" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <rect x="100" y="33" width="28" height="18" rx="3" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <rect x="135" y="33" width="28" height="18" rx="3" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <rect x="170" y="33" width="28" height="18" rx="3" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <rect x="205" y="33" width="28" height="18" rx="3" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <!-- front -->
  <rect x="268" y="30" width="27" height="46" rx="6" fill="#0D2040" stroke="#1E4080" stroke-width="1"/>
  <rect x="270" y="34" width="22" height="14" rx="2" fill="url(#windowGrad)" stroke="#4080CC" stroke-width="0.5"/>
  <!-- headlight -->
  <ellipse cx="289" cy="55" rx="4" ry="3" fill="#FFD000" opacity="0.9" filter="url(#glow)"/>
  <!-- wheels -->
  <circle cx="60" cy="80" r="14" fill="#111" stroke="#333" stroke-width="2"/>
  <circle cx="60" cy="80" r="8" fill="#222" stroke="#FFD000" stroke-width="1.5"/>
  <circle cx="60" cy="80" r="3" fill="#FFD000"/>
  <circle cx="230" cy="80" r="14" fill="#111" stroke="#333" stroke-width="2"/>
  <circle cx="230" cy="80" r="8" fill="#222" stroke="#FFD000" stroke-width="1.5"/>
  <circle cx="230" cy="80" r="3" fill="#FFD000"/>
  <!-- undercarriage -->
  <rect x="25" y="72" width="250" height="8" rx="2" fill="#0A1828"/>
  <!-- e^pack label -->
  <text x="140" y="60" font-family="monospace" font-size="7" fill="#FFD000" opacity="0.7" text-anchor="middle">e^pack · 320kWh · 15min charge</text>
  <!-- charge port -->
  <rect x="12" y="48" width="8" height="10" rx="2" fill="#FFD000" opacity="0.8"/>
  <text x="16" y="56" font-family="monospace" font-size="5" fill="#000" text-anchor="middle">⚡</text>
</svg>
"""

LIGHTNING_BG = """
<svg viewBox="0 0 1200 600" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice" style="position:absolute;top:0;left:0;width:100%;height:100%;opacity:0.04;">
  <polygon points="600,50 680,250 620,250 700,550 540,300 610,300" fill="#FFD000"/>
  <polygon points="200,80 260,220 220,220 280,450 170,260 230,260" fill="#FFD000" opacity="0.5"/>
  <polygon points="950,100 1010,240 970,240 1030,440 920,270 980,270" fill="#FFD000" opacity="0.5"/>
</svg>
"""

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {{
  --bg:{P['bg']}; --bg2:{P['bg2']}; --bg3:{P['bg3']}; --bg4:{P['bg4']};
  --card:{P['card']}; --border:{P['border']}; --border2:{P['border2']};
  --text:{P['text']}; --text2:{P['text2']}; --text3:{P['text3']};
  --accent:{P['accent']}; --accent2:{P['accent2']};
  --blue:{P['blue']}; --green:{P['green']}; --red:{P['red']};
  --purple:{P['purple']}; --teal:{P['teal']};
}}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {{
  background: var(--bg) !important; color: var(--text) !important;
  font-family: 'Space Grotesk', sans-serif !important;
}}
[data-testid="stSidebar"] {{
  background: var(--bg2) !important;
  border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] * {{ color: var(--text2) !important; }}
[data-testid="stSidebar"] label {{ color: var(--text) !important; font-weight:600 !important; }}
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display:none !important; }}

h1,h2,h3,h4 {{ font-family:'Bebas Neue',sans-serif !important; color:var(--text) !important; letter-spacing:0.04em; }}

/* tabs */
[data-testid="stTabs"] [role="tab"] {{
  font-family:'JetBrains Mono',monospace !important; font-size:11px !important;
  color:var(--text3) !important; border-bottom:2px solid transparent !important;
  padding:10px 18px !important; text-transform:uppercase; letter-spacing:0.1em;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
  color:var(--accent) !important; border-bottom-color:var(--accent) !important;
}}
[data-testid="stTabs"] [role="tablist"] {{
  border-bottom:1px solid var(--border) !important; background:transparent !important;
  gap:4px !important;
}}

/* selectbox */
[data-testid="stSelectbox"] > div > div {{
  background:var(--bg3) !important; border-color:var(--border) !important; color:var(--text) !important;
}}
[data-baseweb="select"] span {{ color:var(--text) !important; }}

/* dataframe */
[data-testid="stDataFrame"] {{ border-radius:10px !important; overflow:hidden !important; }}

/* slider thumb */
[data-testid="stSlider"] [role="slider"] {{ background:var(--accent) !important; border-color:var(--accent) !important; }}

/* ── HERO ── */
.hero {{
  position:relative; overflow:hidden;
  background: linear-gradient(135deg, {'#020810' if DARK else '#E8F0FF'} 0%, {'#060F20' if DARK else '#D0DFFF'} 50%, {'#030C18' if DARK else '#C8D8FF'} 100%);
  border:1px solid var(--border); border-radius:16px;
  padding:0; margin-bottom:24px; min-height:180px;
}}
.hero-content {{
  position:relative; z-index:2;
  padding:28px 32px;
  display:flex; justify-content:space-between; align-items:center;
}}
.hero-left {{ flex:1; }}
.hero-badge {{
  display:inline-flex; align-items:center; gap:6px;
  background:{'#FFD00015' if DARK else '#D4A50015'}; border:1px solid {'#FFD00030' if DARK else '#D4A50030'};
  border-radius:20px; padding:4px 12px;
  font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--accent);
  text-transform:uppercase; letter-spacing:0.12em; margin-bottom:12px;
}}
.hero-title {{
  font-family:'Bebas Neue',sans-serif; font-size:52px; line-height:0.9;
  color:var(--text); letter-spacing:0.02em; margin-bottom:8px;
}}
.hero-title span {{ color:var(--accent); }}
.hero-sub {{
  font-family:'JetBrains Mono',monospace; font-size:11px;
  color:var(--text3); text-transform:uppercase; letter-spacing:0.12em;
}}
.hero-bus {{
  width:360px; flex-shrink:0; position:relative; z-index:2;
  filter:{'drop-shadow(0 0 20px rgba(255,208,0,0.15))' if DARK else 'drop-shadow(0 4px 12px rgba(0,0,0,0.1))'};
}}
.hero-stats {{
  display:flex; gap:24px; margin-top:20px; flex-wrap:wrap;
}}
.hero-stat-item {{
  font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--text3);
}}
.hero-stat-item b {{ color:var(--accent); font-size:14px; display:block; margin-bottom:2px; }}

/* ── SCENARIO CARD ── */
.sc-card {{
  background:var(--card); border:1px solid var(--border);
  border-left:4px solid var(--accent);
  border-radius:12px; padding:18px 22px; margin-bottom:20px;
  display:flex; justify-content:space-between; align-items:flex-start;
}}
.sc-name {{ font-family:'Bebas Neue',sans-serif; font-size:26px; color:var(--text); letter-spacing:0.04em; }}
.sc-desc {{ font-size:13px; color:var(--text2); margin-top:4px; line-height:1.5; }}
.tag {{ display:inline-block; padding:2px 9px; border-radius:4px; background:var(--bg3); border:1px solid var(--border); font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--text3); margin:4px 3px 0 0; text-transform:uppercase; letter-spacing:0.08em; }}
.valid-badge {{ display:inline-block; padding:4px 12px; border-radius:6px; font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; letter-spacing:0.08em; }}

/* ── KPI ── */
.kpi-row {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:22px; }}
.kpi {{
  flex:1; min-width:120px;
  background:var(--card); border:1px solid var(--border); border-radius:10px;
  padding:14px 16px; position:relative; overflow:hidden;
  transition: border-color 0.2s;
}}
.kpi:hover {{ border-color:var(--border2); }}
.kpi::before {{
  content:''; position:absolute; top:0; left:0; right:0; height:3px;
  background:var(--kc, var(--accent));
}}
.kpi-lbl {{ font-family:'JetBrains Mono',monospace; font-size:9px; text-transform:uppercase; letter-spacing:0.12em; color:var(--text3); margin-bottom:6px; }}
.kpi-val {{ font-family:'Bebas Neue',sans-serif; font-size:32px; line-height:1; color:var(--text); }}
.kpi-unit {{ font-family:'Space Grotesk',sans-serif; font-size:12px; font-weight:400; color:var(--text2); margin-left:2px; }}
.kpi-sub {{ font-size:10px; color:var(--text3); margin-top:3px; }}

/* ── SECTION LABEL ── */
.sl {{
  font-family:'JetBrains Mono',monospace; font-size:9px; text-transform:uppercase;
  letter-spacing:0.18em; color:var(--text3);
  display:flex; align-items:center; gap:8px;
  margin:24px 0 14px; padding-bottom:8px;
  border-bottom:1px solid var(--border);
}}
.sl em {{ color:var(--accent); font-style:normal; }}

/* ── ROUTE STRIP ── */
.rstrip {{
  background:var(--card); border:1px solid var(--border);
  border-radius:12px; padding:22px 28px;
  display:flex; align-items:center; overflow-x:auto;
  gap:0; position:relative;
}}
.rnode {{ display:flex; flex-direction:column; align-items:center; gap:5px; flex-shrink:0; }}
.rcircle {{
  width:46px; height:46px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  font-family:'Bebas Neue',sans-serif; font-size:14px; letter-spacing:0.05em;
}}
.rterm {{ background:{'#1E7FFF15' if DARK else '#1155CC10'}; border:2px solid var(--blue); color:var(--blue); }}
.rstn  {{ border:2px solid; }}
.rname {{ font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--text3); text-align:center; max-width:52px; }}
.rline {{ flex:1; min-width:40px; position:relative; display:flex; align-items:center; }}
.rline-inner {{ height:2px; width:100%; background:linear-gradient(90deg, var(--border), var(--border2)); }}
.rdist {{ font-family:'JetBrains Mono',monospace; font-size:8px; color:var(--text3); position:absolute; top:-13px; white-space:nowrap; left:50%; transform:translateX(-50%); }}

/* ── BUS ROW ── */
.bus-row {{
  background:var(--card); border:1px solid var(--border);
  border-radius:10px; padding:14px 16px; margin-bottom:8px;
  display:flex; align-items:flex-start; gap:16px;
}}
.bus-row:hover {{ border-color:var(--border2); }}
.bus-id {{ font-family:'JetBrains Mono',monospace; font-size:13px; font-weight:700; color:var(--blue); }}
.op-pill {{ display:inline-block; padding:2px 8px; border-radius:4px; font-family:'JetBrains Mono',monospace; font-size:9px; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; }}
.wait-chip {{ padding:2px 8px; border-radius:4px; font-family:'JetBrains Mono',monospace; font-size:9px; font-weight:600; }}
.mini-lbl {{ font-size:9px; color:var(--text3); text-transform:uppercase; letter-spacing:0.08em; margin-bottom:2px; }}
.mini-val {{ font-family:'JetBrains Mono',monospace; font-size:13px; }}

/* ── STATION CARD ── */
.sq-card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; overflow:hidden; margin-bottom:14px; }}
.sq-hd {{ padding:14px 16px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }}
.sq-row {{ display:flex; align-items:center; gap:12px; padding:10px 16px; border-bottom:1px solid var(--border); }}
.sq-row:last-child {{ border-bottom:none; }}

/* ── violation ── */
.vbox {{
  background:{'#200808' if DARK else '#FFF0F0'}; border:1px solid {'#5C1A1A' if DARK else '#FFBBBB'};
  border-radius:8px; padding:12px 16px; margin-bottom:16px;
  font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--red);
}}

/* ── charge bar mini ── */
.cbar-wrap {{ height:3px; background:var(--bg3); border-radius:2px; overflow:hidden; margin-top:4px; }}
.cbar {{ height:3px; border-radius:2px; }}
</style>
""", unsafe_allow_html=True)


# ─── helpers ──────────────────────────────────────────────────────────────────
def fmt(m):
    h, mm = int(m // 60) % 24, int(m % 60)
    return f"{h:02d}:{mm:02d}"

def dur(m):
    if m < 1: return "0m"
    h, mm = int(m // 60), int(m % 60)
    return f"{h}h {mm:02d}m" if h else f"{mm}m"

def op_pill(op):
    c = OP_COLORS.get(op, P["text3"])
    return f'<span class="op-pill" style="background:{c}20;color:{c};border:1px solid {c}40;">{op.upper()}</span>'

def wait_chip(w):
    if w < 1:    c, t = P["green"], "✓ no wait"
    elif w < 20: c, t = P["accent"], f"⏱ +{dur(w)}"
    elif w < 50: c, t = P["accent2"], f"⚠ +{dur(w)}"
    else:        c, t = P["red"], f"✗ +{dur(w)}"
    return f'<span class="wait-chip" style="background:{c}20;color:{c};border:1px solid {c}40;">{t}</span>'

def pcolor(p): return f"rgba({int(p[1:3],16)},{int(p[3:5],16)},{int(p[5:7],16)},0)"


# ─── load ──────────────────────────────────────────────────────────────────────
scenarios_dir = Path(__file__).parent / "scenarios"
all_scenarios = get_all_scenarios(scenarios_dir)


# ─── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:14px 0 18px;border-bottom:1px solid {P['border']};margin-bottom:16px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <svg width="30" height="30" viewBox="0 0 28 28">
          <polygon points="17,1 25,1 9,13 19,13 3,27 9,15 1,15 17,1" fill="{P['accent']}"/>
        </svg>
        <div>
          <div style="font-family:'Bebas Neue',sans-serif;font-size:18px;color:{P['text']};letter-spacing:0.04em;">EXPONENT</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:8px;color:{P['text3']};letter-spacing:0.14em;text-transform:uppercase;">Energy · Scheduler</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("☀️ Light Mode" if DARK else "🌙 Dark Mode", use_container_width=True):
        st.session_state.dark_mode = not DARK
        st.rerun()

    st.markdown(f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:9px;text-transform:uppercase;letter-spacing:0.12em;color:{P["text3"]};margin:16px 0 6px;">Scenario</div>', unsafe_allow_html=True)
    labels = [s[2] for s in all_scenarios]
    idx = st.selectbox("Scenario", range(len(all_scenarios)), format_func=lambda i: labels[i], label_visibility="collapsed")
    sel_path = all_scenarios[idx][0]
    sdata = json.loads(Path(sel_path).read_text())
    dw = sdata["weights"]

    st.markdown(f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:9px;text-transform:uppercase;letter-spacing:0.12em;color:{P["text3"]};margin:16px 0 4px;">⚡ Weight Tuning</div>', unsafe_allow_html=True)
    st.caption("Live re-runs scheduler on change.")
    w_i = st.slider("🧍 Individual",   0.0, 3.0, float(dw["individual"]), 0.1)
    w_o = st.slider("🏢 Operator",     0.0, 3.0, float(dw["operator"]),   0.1)
    w_g = st.slider("🌐 Overall",      0.0, 3.0, float(dw["overall"]),    0.1)

    st.markdown("---")
    phy = sdata["world"]["physics"]
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{P['text3']};line-height:2.2;">
      <span style="color:{P['accent']};">e^pack</span> &nbsp; {phy['battery_range_km']} km range<br>
      <span style="color:{P['accent']};">e^pump</span> &nbsp; {phy['charge_duration_min']} min charge<br>
      <span style="color:{P['accent']};">speed</span> &nbsp; {phy['speed_kmph']} km/h
    </div>
    """, unsafe_allow_html=True)


# ─── run ───────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def run(path, wi, wo, wg):
    return run_scenario(path, weight_overrides={"individual": wi, "operator": wo, "overall": wg})

with st.spinner("⚡ Computing schedule…"):
    result: ScheduleResult = run(str(sel_path), w_i, w_o, w_g)

smeta = sdata["meta"]
buses_raw = sdata["buses"]
N = len(result.bus_timelines)
waits = [t.total_wait_min for t in result.bus_timelines]
trips = [t.total_trip_min for t in result.bus_timelines]
avg_w = sum(waits) / max(N, 1)
max_w = max(waits) if waits else 0
avg_t = sum(trips) / max(N, 1)
zero_w = sum(1 for w in waits if w < 1)
tot_ev = sum(len(t.charge_events) for t in result.bus_timelines)


# ─── HERO ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  {LIGHTNING_BG}
  <div class="hero-content">
    <div class="hero-left">
      <div class="hero-badge">⚡ Exponent Energy · Internal Tool</div>
      <div class="hero-title">ELECTRIC BUS<br><span>CHARGING</span><br>SCHEDULER</div>
      <div class="hero-sub">Bengaluru ↔ Kochi · 540 km · 4 e^pump Stations</div>
      <div class="hero-stats">
        <div class="hero-stat-item"><b>15 min</b>e^pump charge</div>
        <div class="hero-stat-item"><b>1 MW</b>charging power</div>
        <div class="hero-stat-item"><b>320 kWh</b>e^pack size</div>
        <div class="hero-stat-item"><b>3000</b>battery cycles</div>
      </div>
    </div>
    <div class="hero-bus">{BUS_SVG}</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─── SCENARIO CARD ─────────────────────────────────────────────────────────────
vc = P["green"] if result.is_valid else P["red"]
vl = "✓ Valid" if result.is_valid else "✗ Violations"
tags = "".join(f'<span class="tag">{t}</span>' for t in smeta.get("tags", []))

st.markdown(f"""
<div class="sc-card">
  <div style="flex:1;">
    <div class="sc-name">{smeta['name']}</div>
    <div class="sc-desc">{smeta['description']}</div>
    <div style="margin-top:8px;">
      {tags}
      <span class="tag" style="color:{P['accent']};border-color:{P['accent']}40;">w_ind={w_i:.1f} · w_op={w_o:.1f} · w_all={w_g:.1f}</span>
      <span class="valid-badge" style="background:{vc}15;color:{vc};border:1px solid {vc}40;">{vl}</span>
    </div>
  </div>
  <div style="text-align:right;padding-left:20px;flex-shrink:0;">
    <div style="font-family:'Bebas Neue',sans-serif;font-size:48px;color:{P['accent']};line-height:1;">{N}</div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{P['text3']};text-transform:uppercase;">buses</div>
  </div>
</div>
""", unsafe_allow_html=True)

if not result.is_valid:
    st.markdown(f'<div class="vbox">⚠ VIOLATIONS<br>' + "<br>".join(f"▶ {v}" for v in result.violations) + "</div>", unsafe_allow_html=True)


# ─── KPI ROW ───────────────────────────────────────────────────────────────────
kpis = [
    ("Avg Wait",      f"{avg_w:.0f}",      "min", "per bus at charger",        P["accent"]),
    ("Max Wait",      f"{max_w:.0f}",      "min", "worst-case single bus",     P["red"]),
    ("Zero-Wait",     f"{zero_w}",         "",    "buses with instant charge",  P["green"]),
    ("Avg Trip",      f"{avg_t/60:.1f}",   "h",   "departure → destination",   P["blue"]),
    ("Charge Events", f"{tot_ev}",         "",    "total charging stops",       P["purple"]),
    ("Scenarios",     f"{len(all_scenarios)}", "", "loaded & testable",         P["teal"]),
]
html = '<div class="kpi-row">'
for lbl, val, unit, sub, color in kpis:
    html += f'<div class="kpi" style="--kc:{color};"><div class="kpi-lbl">{lbl}</div><div class="kpi-val">{val}<span class="kpi-unit">{unit}</span></div><div class="kpi-sub">{sub}</div></div>'
html += "</div>"
st.markdown(html, unsafe_allow_html=True)


# ─── TABS ──────────────────────────────────────────────────────────────────────
t1, t2, t3, t4, t5, t6 = st.tabs(["⚡ Route Map", "📊 Gantt", "🚌 Bus Timetable", "🔌 Station Queues", "🏢 Operators", "📋 Raw Data"])


# ══════════════════════════════════════════════════════════════
#  TAB 1 — ROUTE MAP
# ══════════════════════════════════════════════════════════════
with t1:
    st.markdown('<div class="sl"><em>■</em> Route Overview — Bengaluru → Kochi</div>', unsafe_allow_html=True)

    segs = sdata["world"]["route"]["segments"]
    stops = [segs[0]["from"]] + [s["to"] for s in segs]
    stn_ids = {s["id"] for s in sdata["world"]["stations"]}
    stop_names = {"BLR": "Bengaluru", "KCH": "Kochi",
                  "A": "e^pump A", "B": "e^pump B", "C": "e^pump C", "D": "e^pump D"}

    rhtml = '<div class="rstrip">'
    for i, sid in enumerate(stops):
        is_stn = sid in stn_ids
        col = STN_COLORS.get(sid, P["blue"])
        cls = "rstn" if is_stn else "rterm"
        style = f"background:{col}15;border-color:{col};color:{col};" if is_stn else ""
        rhtml += f'<div class="rnode"><div class="rcircle {cls}" style="{style}">{sid}</div><div class="rname">{stop_names.get(sid, sid)}</div></div>'
        if i < len(stops) - 1:
            dist = segs[i]["distance_km"]
            rhtml += f'<div class="rline"><div class="rline-inner"></div><span class="rdist">{dist}km</span></div>'
    rhtml += "</div>"
    st.markdown(rhtml, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown('<div class="sl"><em>■</em> e^pump Station Load</div>', unsafe_allow_html=True)
        sorder = ["A", "B", "C", "D"]
        scounts = {}; swaits = {}
        for s in sorder:
            slog = result.station_logs.get(s)
            evs = slog.events if slog else []
            scounts[s] = len(evs)
            swaits[s] = (sum(e.wait_min for e in evs) / len(evs)) if evs else 0

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=sorder, y=[scounts[s] for s in sorder], name="Buses Served",
            marker_color=[STN_COLORS[s] for s in sorder], marker_line_width=0,
        ))
        fig.add_trace(go.Scatter(
            x=sorder, y=[swaits[s] for s in sorder], name="Avg Wait (min)",
            yaxis="y2", mode="lines+markers",
            line=dict(color=P["red"], width=2, dash="dot"),
            marker=dict(size=8, color=P["red"]),
        ))
        fig.update_layout(
            plot_bgcolor=P["plot_bg"], paper_bgcolor=P["plot_bg"],
            font=dict(family="JetBrains Mono", size=11, color=P["text2"]),
            xaxis=dict(gridcolor=P["grid"]),
            yaxis=dict(gridcolor=P["grid"], title="Buses Served"),
            yaxis2=dict(title="Avg Wait (min)", overlaying="y", side="right", gridcolor=pcolor(P["grid"])),
            legend=dict(bgcolor=pcolor(P["bg"]), font=dict(size=10)),
            margin=dict(l=20, r=20, t=20, b=20), height=280, barmode="group",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<div class="sl"><em>■</em> Direction Split</div>', unsafe_allow_html=True)
        blr_kch = sum(1 for tl in result.bus_timelines if tl.bus.direction == Direction.BLR_KCH)
        fig2 = go.Figure(go.Pie(
            labels=["BLR → KCH", "KCH → BLR"],
            values=[blr_kch, N - blr_kch],
            hole=0.62,
            marker=dict(colors=[P["accent"], P["blue"]], line=dict(color=P["bg"], width=3)),
            textinfo="label+percent",
            textfont=dict(family="JetBrains Mono", size=10, color=P["text"]),
        ))
        fig2.update_layout(
            plot_bgcolor=P["plot_bg"], paper_bgcolor=P["plot_bg"],
            showlegend=False, margin=dict(l=10, r=10, t=10, b=10), height=200,
            annotations=[dict(text=f"<b>{N}</b><br>buses", x=0.5, y=0.5,
                              font=dict(size=14, color=P["text"], family="Bebas Neue"), showarrow=False)]
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown('<div class="sl"><em>■</em> Station Utilization</div>', unsafe_allow_html=True)
        for s in sorder:
            col = STN_COLORS[s]; pct = int(scounts[s] / max(N, 1) * 100)
            st.markdown(f"""
            <div style="margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{col};">e^pump {s}</span>
                <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{P['text3']};">{scounts[s]} buses · {swaits[s]:.0f}m avg</span>
              </div>
              <div style="height:4px;background:{P['border']};border-radius:2px;">
                <div style="height:4px;width:{pct}%;background:{col};border-radius:2px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  TAB 2 — GANTT
# ══════════════════════════════════════════════════════════════
with t2:
    st.markdown('<div class="sl"><em>■</em> Bus Journey Timeline — Drive / Wait / Charge</div>', unsafe_allow_html=True)

    seg_list = sdata["world"]["route"]["segments"]
    all_stops_fwd = [seg_list[0]["from"]] + [s["to"] for s in seg_list]
    speed = sdata["world"]["physics"]["speed_kmph"]

    buses_sorted_gantt = sorted(result.bus_timelines, key=lambda t: t.departure_time_min)
    bus_ids = [tl.bus.id for tl in buses_sorted_gantt]
    y_map = {b: i for i, b in enumerate(bus_ids)}

    fig_g = go.Figure()
    drive_col = "#1C2E4A" if DARK else "#D8E4F8"

    for tl in buses_sorted_gantt:
        bus = tl.bus
        if bus.direction == Direction.BLR_KCH:
            stops_list = all_stops_fwd; dists = [s["distance_km"] for s in seg_list]
        else:
            stops_list = list(reversed(all_stops_fwd)); dists = list(reversed([s["distance_km"] for s in seg_list]))

        t_cur = tl.departure_time_min
        charge_lookup = {ev.station_id: ev for ev in tl.charge_events}
        y = y_map[bus.id]

        for i in range(len(stops_list) - 1):
            frm, to = stops_list[i], stops_list[i + 1]
            travel = (dists[i] / speed) * 60
            # Drive
            fig_g.add_shape(type="rect", x0=t_cur, x1=t_cur + travel,
                            y0=y - 0.35, y1=y + 0.35, fillcolor=drive_col, opacity=0.5, line_width=0)
            t_cur += travel

            if to in charge_lookup:
                ev = charge_lookup[to]
                if ev.wait_min > 0.5:
                    fig_g.add_shape(type="rect", x0=ev.arrive_time_min, x1=ev.charge_start_min,
                                    y0=y - 0.35, y1=y + 0.35, fillcolor=P["red"], opacity=0.75, line_width=0)
                sc = STN_COLORS.get(to, P["accent"])
                fig_g.add_shape(type="rect", x0=ev.charge_start_min, x1=ev.charge_end_min,
                                y0=y - 0.35, y1=y + 0.35, fillcolor=sc, opacity=1.0, line_width=0)
                t_cur = ev.charge_end_min

    # Legend traces
    for lbl, col, op in [("Drive", drive_col, 0.5), ("Wait", P["red"], 0.75),
                          ("Charge A", STN_COLORS["A"], 1), ("Charge B", STN_COLORS["B"], 1),
                          ("Charge C", STN_COLORS["C"], 1), ("Charge D", STN_COLORS["D"], 1)]:
        fig_g.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=lbl,
                                   marker=dict(size=10, color=col, symbol="square", opacity=op), showlegend=True))

    all_t = []
    for tl in result.bus_timelines:
        all_t.append(tl.departure_time_min)
        all_t.append(tl.arrival_time_min)
    t_lo, t_hi = min(all_t) - 10, max(all_t) + 10
    ticks = list(range(int(t_lo // 30) * 30, int(t_hi // 30 + 2) * 30, 30))

    fig_g.update_layout(
        plot_bgcolor=P["plot_bg"], paper_bgcolor=P["plot_bg"],
        font=dict(family="JetBrains Mono", size=10, color=P["text2"]),
        xaxis=dict(gridcolor=P["grid"], range=[t_lo, t_hi],
                   tickvals=ticks, ticktext=[fmt(v) for v in ticks], title="Time"),
        yaxis=dict(gridcolor=pcolor(P["grid"]), tickmode="array",
                   tickvals=list(range(len(bus_ids))), ticktext=bus_ids, title=""),
        height=max(350, len(bus_ids) * 22 + 80),
        margin=dict(l=110, r=20, t=40, b=40),
        legend=dict(bgcolor=pcolor(P["bg"]), font=dict(size=10, family="JetBrains Mono"),
                    orientation="h", x=0, y=1.05),
        showlegend=True,
    )
    st.plotly_chart(fig_g, use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  TAB 3 — BUS TIMETABLE
# ══════════════════════════════════════════════════════════════
with t3:
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        df = st.selectbox("Dir", ["All", "BLR → KCH", "KCH → BLR"], label_visibility="collapsed")
    with cf2:
        of = st.selectbox("Op", ["All"] + [o["id"].upper() for o in sdata["world"]["operators"]], label_visibility="collapsed")
    with cf3:
        sf = st.selectbox("Sort", ["Departure", "Wait ↓", "Trip ↓"], label_visibility="collapsed")

    flt = result.bus_timelines
    if df == "BLR → KCH": flt = [t for t in flt if t.bus.direction == Direction.BLR_KCH]
    elif df == "KCH → BLR": flt = [t for t in flt if t.bus.direction == Direction.KCH_BLR]
    if of != "All": flt = [t for t in flt if t.bus.operator_id.upper() == of]
    if sf == "Departure": flt = sorted(flt, key=lambda t: t.departure_time_min)
    elif sf == "Wait ↓": flt = sorted(flt, key=lambda t: -t.total_wait_min)
    else: flt = sorted(flt, key=lambda t: -t.total_trip_min)

    st.markdown(f'<div class="sl"><em>■</em> {len(flt)} Buses</div>', unsafe_allow_html=True)

    for tl in flt:
        bus = tl.bus
        dc = P["accent"] if bus.direction == Direction.BLR_KCH else P["purple"]
        ds = "BLR → KCH" if bus.direction == Direction.BLR_KCH else "KCH → BLR"
        wc = P["green"] if tl.total_wait_min < 1 else (P["accent"] if tl.total_wait_min < 30 else P["red"])

        crows = ""
        for ev in tl.charge_events:
            sc = STN_COLORS.get(ev.station_id, P["text3"])
            crows += f"""
            <div style="display:flex;align-items:center;gap:14px;padding:6px 0;border-top:1px solid {P['border']};flex-wrap:wrap;">
              <span style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:{sc};min-width:64px;">e^pump {ev.station_id}</span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{P['text2']};">arrive <b style="color:{P['text']}">{fmt(ev.arrive_time_min)}</b></span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{P['text2']};">charge <b style="color:{P['green']}">{fmt(ev.charge_start_min)}→{fmt(ev.charge_end_min)}</b></span>
              {wait_chip(ev.wait_min)}
            </div>"""
        if not crows:
            crows = f'<div style="font-size:11px;color:{P["text3"]};padding-top:6px;">No charges scheduled</div>'

        schips = "".join(
            f'<span style="background:{STN_COLORS.get(s,P["text3"])}15;color:{STN_COLORS.get(s,P["text3"])};border:1px solid {STN_COLORS.get(s,P["text3"])}40;padding:2px 8px;border-radius:4px;font-family:\'JetBrains Mono\',monospace;font-size:9px;margin-right:4px;">{s}</span>'
            for s in tl.stations_used
        ) or f'<span style="color:{P["text3"]};font-size:10px;">—</span>'

        st.markdown(f"""
        <div class="bus-row">
          <div style="min-width:105px;">
            <div class="bus-id">{bus.id}</div>
            <div style="margin-top:5px;">{op_pill(bus.operator_id)}</div>
            <div style="margin-top:5px;"><span style="background:{dc}15;color:{dc};padding:2px 7px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:9px;">{ds}</span></div>
          </div>
          <div style="flex:1;min-width:0;">
            <div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px;align-items:flex-end;">
              <div><div class="mini-lbl">Departs</div><div class="mini-val" style="color:{P['text2']};">{fmt(tl.departure_time_min)}</div></div>
              <div><div class="mini-lbl">Arrives</div><div style="font-family:'Bebas Neue',sans-serif;font-size:18px;color:{P['text']};">{fmt(tl.arrival_time_min)}</div></div>
              <div><div class="mini-lbl">Trip</div><div class="mini-val" style="color:{P['blue']};">{dur(tl.total_trip_min)}</div></div>
              <div><div class="mini-lbl">Wait</div><div class="mini-val" style="color:{wc};">{dur(tl.total_wait_min)}</div></div>
              <div style="margin-left:auto;">{schips}</div>
            </div>
            {crows}
          </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  TAB 4 — STATION QUEUES
# ══════════════════════════════════════════════════════════════
with t4:
    st.markdown('<div class="sl"><em>■</em> e^pump Charging Queues</div>', unsafe_allow_html=True)

    sorder = ["A", "B", "C", "D"]
    cols4 = st.columns(2)

    for idx, sid in enumerate(sorder):
        slog = result.station_logs.get(sid)
        evs = slog.events if slog else []
        col = STN_COLORS[sid]
        avg_wt = sum(e.wait_min for e in evs) / max(len(evs), 1)
        tot_wt = sum(e.wait_min for e in evs)

        with cols4[idx % 2]:
            st.markdown(f"""
            <div class="sq-card">
              <div class="sq-hd" style="border-top:3px solid {col};">
                <div>
                  <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;color:{col};letter-spacing:0.04em;">e^pump {sid}</div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{P['text3']};margin-top:2px;">
                    {len(evs)} buses · avg {avg_wt:.0f}m wait · total {tot_wt:.0f}m
                  </div>
                </div>
                <div style="text-align:right;">
                  <div style="font-family:'Bebas Neue',sans-serif;font-size:32px;color:{col};line-height:1;">{len(evs)}</div>
                  <div style="font-size:8px;color:{P['text3']};text-transform:uppercase;">buses</div>
                </div>
              </div>
            """, unsafe_allow_html=True)

            if not evs:
                st.markdown(f'<div style="padding:14px;font-size:11px;color:{P["text3"]};">No buses at this station</div>', unsafe_allow_html=True)
            else:
                for pos, ev in enumerate(evs, 1):
                    btl = next((t for t in result.bus_timelines if t.bus.id == ev.bus_id), None)
                    op = btl.bus.operator_id if btl else "?"
                    oc = OP_COLORS.get(op, P["text3"])
                    st.markdown(f"""
                    <div class="sq-row">
                      <div style="font-family:'Bebas Neue',sans-serif;font-size:20px;color:{col}30;min-width:24px;">{pos}</div>
                      <div style="flex:1;">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">
                          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{oc};">{ev.bus_id}</span>
                          {op_pill(op)} {wait_chip(ev.wait_min)}
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{P['text2']};">
                          arrive <b style="color:{P['text']}">{fmt(ev.arrive_time_min)}</b>
                          → charge <b style="color:{P['green']}">{fmt(ev.charge_start_min)}→{fmt(ev.charge_end_min)}</b>
                        </div>
                      </div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sl"><em>■</em> Station Timeline</div>', unsafe_allow_html=True)
    fig_st = go.Figure()
    all_t2 = []
    for sid in sorder:
        slog = result.station_logs.get(sid)
        evs = slog.events if slog else []
        col = STN_COLORS[sid]
        for ev in evs:
            all_t2 += [ev.arrive_time_min, ev.charge_end_min]
            btl = next((t for t in result.bus_timelines if t.bus.id == ev.bus_id), None)
            op = btl.bus.operator_id if btl else "?"
            fig_st.add_trace(go.Bar(
                x=[ev.charge_end_min - ev.charge_start_min], base=[ev.charge_start_min],
                y=[f"e^pump {sid}"], orientation="h", marker_color=col, marker_line_width=0,
                showlegend=False, width=0.5,
                hovertemplate=f"<b>{ev.bus_id}</b> ({op})<br>Charge: {fmt(ev.charge_start_min)}→{fmt(ev.charge_end_min)}<br>Wait: {ev.wait_min:.0f}m<extra></extra>",
            ))
            if ev.wait_min > 0.5:
                fig_st.add_trace(go.Bar(
                    x=[ev.wait_min], base=[ev.arrive_time_min],
                    y=[f"e^pump {sid}"], orientation="h", marker_color=P["red"],
                    marker_line_width=0, opacity=0.5, showlegend=False, width=0.5,
                    hovertemplate=f"<b>{ev.bus_id}</b><br>Waiting: {fmt(ev.arrive_time_min)}→{fmt(ev.charge_start_min)}<br>{ev.wait_min:.0f}m<extra></extra>",
                ))

    t_lo2 = min(all_t2) - 10 if all_t2 else 1100
    t_hi2 = max(all_t2) + 10 if all_t2 else 1400
    tv = list(range(int(t_lo2 // 30) * 30, int(t_hi2 // 30 + 2) * 30, 30))
    fig_st.update_layout(
        plot_bgcolor=P["plot_bg"], paper_bgcolor=P["plot_bg"], barmode="overlay",
        font=dict(family="JetBrains Mono", size=10, color=P["text2"]),
        xaxis=dict(range=[t_lo2, t_hi2], gridcolor=P["grid"], tickvals=tv, ticktext=[fmt(v) for v in tv]),
        yaxis=dict(gridcolor=pcolor(P["grid"])),
        height=220, margin=dict(l=80, r=20, t=10, b=40),
    )
    st.plotly_chart(fig_st, use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  TAB 5 — OPERATORS
# ══════════════════════════════════════════════════════════════
with t5:
    st.markdown('<div class="sl"><em>■</em> Operator Fleet Performance</div>', unsafe_allow_html=True)

    op_stats = {}
    for tl in result.bus_timelines:
        op = tl.bus.operator_id
        if op not in op_stats:
            op_stats[op] = {"buses": 0, "tw": 0, "mw": 0, "tt": 0, "waits": []}
        op_stats[op]["buses"] += 1
        op_stats[op]["tw"] += tl.total_wait_min
        op_stats[op]["mw"] = max(op_stats[op]["mw"], tl.total_wait_min)
        op_stats[op]["tt"] += tl.total_trip_min
        op_stats[op]["waits"].append(tl.total_wait_min)
    for op, s in op_stats.items():
        s["avg_w"] = s["tw"] / max(s["buses"], 1)
        s["avg_t"] = s["tt"] / max(s["buses"], 1)

    ops = sorted(op_stats.keys())
    oc5 = st.columns(len(ops))
    for i, op in enumerate(ops):
        s = op_stats[op]; col = OP_COLORS.get(op, P["text3"])
        wc = P["green"] if s["avg_w"] < 10 else (P["accent"] if s["avg_w"] < 30 else P["red"])
        with oc5[i]:
            st.markdown(f"""
            <div style="background:{P['card']};border:1px solid {P['border']};border-top:4px solid {col};border-radius:12px;padding:18px;margin-bottom:16px;">
              <div style="font-family:'Bebas Neue',sans-serif;font-size:22px;color:{col};letter-spacing:0.04em;">{op.upper()}</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
                <div><div style="font-family:'JetBrains Mono',monospace;font-size:8px;text-transform:uppercase;letter-spacing:0.1em;color:{P['text3']};">Buses</div>
                  <div style="font-family:'Bebas Neue',sans-serif;font-size:28px;color:{P['text']};">{s['buses']}</div></div>
                <div><div style="font-family:'JetBrains Mono',monospace;font-size:8px;text-transform:uppercase;letter-spacing:0.1em;color:{P['text3']};">Avg Wait</div>
                  <div style="font-family:'Bebas Neue',sans-serif;font-size:28px;color:{wc};">{s['avg_w']:.0f}<span style="font-size:14px;">m</span></div></div>
                <div><div style="font-family:'JetBrains Mono',monospace;font-size:8px;text-transform:uppercase;letter-spacing:0.1em;color:{P['text3']};">Max Wait</div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:{P['text2']};">{s['mw']:.0f}m</div></div>
                <div><div style="font-family:'JetBrains Mono',monospace;font-size:8px;text-transform:uppercase;letter-spacing:0.1em;color:{P['text3']};">Avg Trip</div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:{P['text2']};">{s['avg_t']/60:.1f}h</div></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    ca, cb = st.columns(2)
    with ca:
        st.markdown('<div class="sl"><em>■</em> Average Wait per Operator</div>', unsafe_allow_html=True)
        fig5a = go.Figure(go.Bar(
            x=ops, y=[op_stats[o]["avg_w"] for o in ops],
            marker_color=[OP_COLORS.get(o, P["text3"]) for o in ops], marker_line_width=0,
            text=[f"{op_stats[o]['avg_w']:.1f}m" for o in ops], textposition="outside",
            textfont=dict(family="JetBrains Mono", size=11, color=P["text2"]),
        ))
        fig5a.update_layout(
            plot_bgcolor=P["plot_bg"], paper_bgcolor=P["plot_bg"],
            font=dict(family="JetBrains Mono", size=11, color=P["text2"]),
            xaxis=dict(gridcolor=pcolor(P["grid"])),
            yaxis=dict(gridcolor=P["grid"], title="Avg Wait (min)"),
            margin=dict(l=20, r=20, t=20, b=20), height=260, showlegend=False,
        )
        st.plotly_chart(fig5a, use_container_width=True)

    with cb:
        st.markdown('<div class="sl"><em>■</em> Wait Distribution</div>', unsafe_allow_html=True)
        fig5b = go.Figure()
        for op in ops:
            fig5b.add_trace(go.Box(
                y=op_stats[op]["waits"], name=op.upper(),
                marker_color=OP_COLORS.get(op, P["text3"]),
                line=dict(color=OP_COLORS.get(op, P["text3"])),
                fillcolor="rgba(0,0,0,0)", boxmean="sd",
            ))
        fig5b.update_layout(
            plot_bgcolor=P["plot_bg"], paper_bgcolor=P["plot_bg"],
            font=dict(family="JetBrains Mono", size=11, color=P["text2"]),
            xaxis=dict(gridcolor=pcolor(P["grid"])),
            yaxis=dict(gridcolor=P["grid"], title="Wait (min)"),
            margin=dict(l=20, r=20, t=20, b=20), height=260, showlegend=False,
        )
        st.plotly_chart(fig5b, use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  TAB 6 — RAW DATA
# ══════════════════════════════════════════════════════════════
with t6:
    st.markdown('<div class="sl"><em>■</em> Bus Manifest</div>', unsafe_allow_html=True)
    rows = [{"Bus ID": b["id"], "Operator": b["operator"].upper(),
             "Direction": "→ Kochi" if b["direction"] == "BLR->KCH" else "→ Bengaluru",
             "Departure": b["departure"]} for b in buses_raw]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 height=min(500, len(rows) * 35 + 40))

    st.markdown('<div class="sl"><em>■</em> Scenario Config</div>', unsafe_allow_html=True)
    st.code(json.dumps({k: v for k, v in sdata.items() if k != "buses"}, indent=2), language="json")

    full_json = json.dumps(sdata, indent=2)
    st.download_button("⬇ Download Scenario JSON", data=full_json,
                       file_name=f"{smeta['id']}.json", mime="application/json")