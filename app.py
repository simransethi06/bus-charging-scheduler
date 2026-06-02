"""
app.py — Bus Charging Scheduler · Streamlit UI
"""
import streamlit as st
import pandas as pd
import json
import math
from pathlib import Path
from datetime import datetime, timedelta

from scheduler.runner import run_scenario, get_all_scenarios
from scheduler.models import ScheduleResult, BusTimeline, ChargeEvent

# ────────────────────────────────────────────
#  Page config
# ────────────────────────────────────────────
st.set_page_config(
    page_title="BusGrid Scheduler",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────
#  Global CSS — dark industrial theme
# ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── reset ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #0a0c0f !important;
    color: #e2e8f0;
    font-family: 'DM Sans', sans-serif;
}

[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid #1e2736;
}

[data-testid="stSidebar"] * { color: #c9d1d9 !important; }

/* ── headings ── */
h1, h2, h3 { font-family: 'Space Mono', monospace !important; letter-spacing: -0.02em; }

/* ── hide streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ── metric cards ── */
.metric-row { display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }
.metric-card {
    background: #111827;
    border: 1px solid #1f2d3d;
    border-radius: 10px;
    padding: 18px 22px;
    flex: 1;
    min-width: 140px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent, #3b82f6);
}
.metric-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6b7280;
    margin-bottom: 6px;
    font-family: 'Space Mono', monospace;
}
.metric-value {
    font-size: 26px;
    font-weight: 700;
    font-family: 'Space Mono', monospace;
    color: #f1f5f9;
    line-height: 1;
}
.metric-sub {
    font-size: 11px;
    color: #4b5563;
    margin-top: 4px;
}

/* ── section header ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 28px 0 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1e2736;
}
.section-header h3 {
    margin: 0;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #94a3b8;
    font-family: 'Space Mono', monospace;
}
.section-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #3b82f6;
    flex-shrink: 0;
}

/* ── bus card ── */
.bus-card {
    background: #111827;
    border: 1px solid #1f2d3d;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.bus-card:hover { border-color: #3b82f6; }
.bus-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.bus-id {
    font-family: 'Space Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    color: #60a5fa;
}
.operator-badge {
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-family: 'Space Mono', monospace;
}
.op-kpn      { background: #1e3a5f; color: #60a5fa; border: 1px solid #2563eb33; }
.op-freshbus { background: #1a3d2b; color: #4ade80; border: 1px solid #16a34a33; }
.op-flixbus  { background: #3b1f5e; color: #c084fc; border: 1px solid #7c3aed33; }
.op-default  { background: #1f2937; color: #9ca3af; border: 1px solid #37415133; }

/* ── timeline strip ── */
.timeline-strip {
    display: flex;
    align-items: center;
    gap: 0;
    overflow: hidden;
    border-radius: 6px;
    height: 28px;
    font-size: 10px;
}
.tl-seg {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Mono', monospace;
    font-size: 9px;
    white-space: nowrap;
    overflow: hidden;
}
.tl-drive { background: #1e3a5f; color: #93c5fd; }
.tl-wait  { background: #3b1f1f; color: #f87171; }
.tl-charge{ background: #1a3d2b; color: #4ade80; }

/* ── station queue ── */
.queue-entry {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: #0d1117;
    border: 1px solid #1f2d3d;
    border-radius: 8px;
    margin-bottom: 6px;
}
.queue-number {
    font-family: 'Space Mono', monospace;
    font-size: 18px;
    font-weight: 700;
    color: #374151;
    min-width: 28px;
    text-align: right;
}
.queue-bus-id {
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    color: #60a5fa;
    font-weight: 700;
}
.queue-time {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #6b7280;
    margin-left: auto;
}
.queue-wait-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-family: 'Space Mono', monospace;
}
.wait-zero { background: #1a3d2b; color: #4ade80; }
.wait-low  { background: #1e3a2b; color: #86efac; }
.wait-mid  { background: #3b2f1a; color: #fbbf24; }
.wait-high { background: #3b1f1f; color: #f87171; }

/* ── scenario badge ── */
.scenario-pill {
    display: inline-flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}
.tag-pill {
    background: #1e2736;
    color: #64748b;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 10px;
    font-family: 'Space Mono', monospace;
    border: 1px solid #263347;
}

/* ── violation banner ── */
.violation-banner {
    background: #3b1f1f;
    border: 1px solid #7f1d1d;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
}
.violation-banner b { color: #f87171; font-family: 'Space Mono', monospace; }

/* ── hero header ── */
.hero {
    padding: 32px 0 24px;
    border-bottom: 1px solid #1e2736;
    margin-bottom: 24px;
}
.hero-label {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #3b82f6;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-bottom: 8px;
}
.hero-title {
    font-family: 'Space Mono', monospace;
    font-size: 36px;
    font-weight: 700;
    color: #f1f5f9;
    line-height: 1.1;
    margin: 0 0 8px;
}
.hero-sub {
    color: #6b7280;
    font-size: 14px;
    max-width: 540px;
}

/* ── route map ── */
.route-map {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 20px;
    background: #111827;
    border: 1px solid #1f2d3d;
    border-radius: 10px;
    overflow-x: auto;
}
.stop-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}
.stop-circle {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    font-weight: 700;
}
.stop-terminal { background: #1e3a5f; border: 2px solid #3b82f6; color: #60a5fa; }
.stop-station  { background: #1a3d2b; border: 2px solid #16a34a; color: #4ade80; }
.stop-label { font-size: 9px; color: #6b7280; font-family: 'Space Mono', monospace; text-align: center; }
.route-line {
    height: 2px;
    flex: 1;
    min-width: 40px;
    background: linear-gradient(90deg, #1f2d3d, #2d3f54);
    position: relative;
}
.route-dist {
    font-size: 9px;
    color: #4b5563;
    text-align: center;
    position: absolute;
    top: -14px;
    left: 50%;
    transform: translateX(-50%);
    white-space: nowrap;
    font-family: 'Space Mono', monospace;
}

/* ── weight sliders ── */
[data-testid="stSlider"] > div > div { background: #1e2736 !important; }
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #3b82f6 !important;
    border-color: #3b82f6 !important;
}

/* ── tables ── */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
thead { background: #111827 !important; }

/* ── direction chips ── */
.dir-blr { color: #f59e0b; font-size: 11px; font-family: 'Space Mono', monospace; }
.dir-kbl { color: #a78bfa; font-size: 11px; font-family: 'Space Mono', monospace; }

/* ── validity badge ── */
.valid-badge   { background: #1a3d2b; color: #4ade80; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-family: 'Space Mono', monospace; border: 1px solid #16a34a44; }
.invalid-badge { background: #3b1f1f; color: #f87171; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-family: 'Space Mono', monospace; border: 1px solid #7f1d1d44; }
</style>
""", unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────

def fmt_time(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


def fmt_duration(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def operator_badge(op: str) -> str:
    cls = f"op-{op.lower()}" if op.lower() in ["kpn", "freshbus", "flixbus"] else "op-default"
    return f'<span class="operator-badge {cls}">{op}</span>'


def wait_badge(wait_min: float) -> str:
    if wait_min < 1:
        cls, label = "wait-zero", "No wait"
    elif wait_min < 15:
        cls, label = "wait-low", f"+{fmt_duration(wait_min)}"
    elif wait_min < 35:
        cls, label = "wait-mid", f"+{fmt_duration(wait_min)}"
    else:
        cls, label = "wait-high", f"+{fmt_duration(wait_min)}"
    return f'<span class="queue-wait-badge {cls}">{label}</span>'


STATION_COLOR = {
    "A": "#f59e0b",
    "B": "#3b82f6",
    "C": "#a855f7",
    "D": "#10b981",
}

OP_COLOR = {
    "kpn":      "#3b82f6",
    "freshbus": "#22c55e",
    "flixbus":  "#a855f7",
}


# ────────────────────────────────────────────
#  Sidebar
# ────────────────────────────────────────────

scenarios_dir = Path(__file__).parent / "scenarios"
all_scenarios = get_all_scenarios(scenarios_dir)

with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 20px;">
        <div style="font-family: 'Space Mono', monospace; font-size: 11px; color: #3b82f6; 
                    text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 4px;">
            BusGrid
        </div>
        <div style="font-family: 'Space Mono', monospace; font-size: 18px; font-weight: 700; color: #f1f5f9;">
            Charging Scheduler
        </div>
        <div style="font-size: 11px; color: #4b5563; margin-top: 4px;">
            Bengaluru ↔ Kochi · 540 km
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Scenario")
    scenario_labels = [s[2] for s in all_scenarios]
    selected_idx = st.selectbox(
        "Select scenario",
        range(len(all_scenarios)),
        format_func=lambda i: scenario_labels[i],
        label_visibility="collapsed",
    )
    selected_path = all_scenarios[selected_idx][0]

    st.markdown("---")
    st.markdown("### Weight Tuning")
    st.caption("Adjust soft-rule weights. Changes re-run the scheduler instantly.")

    # Load defaults from scenario
    scenario_data = json.loads(Path(selected_path).read_text())
    def_w = scenario_data["weights"]

    w_individual = st.slider("Individual (bus wait)", 0.0, 3.0, float(def_w["individual"]), 0.1)
    w_operator   = st.slider("Operator (fleet equity)", 0.0, 3.0, float(def_w["operator"]),   0.1)
    w_overall    = st.slider("Overall (throughput)", 0.0, 3.0, float(def_w["overall"]),   0.1)

    st.markdown("---")
    st.markdown("### Physics")
    meta_world = scenario_data["world"]["physics"]
    st.markdown(f"""
    <div style="font-family: 'Space Mono', monospace; font-size: 10px; color: #4b5563; line-height: 2;">
        Range: <span style="color:#94a3b8">{meta_world['battery_range_km']} km</span><br>
        Charge: <span style="color:#94a3b8">{meta_world['charge_duration_min']} min</span><br>
        Speed: <span style="color:#94a3b8">{meta_world['speed_kmph']} km/h</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("v1.0 · BusGrid Scheduler")


# ────────────────────────────────────────────
#  Run scheduler
# ────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def cached_run(path_str: str, wi: float, wo: float, wg: float):
    return run_scenario(
        path_str,
        weight_overrides={"individual": wi, "operator": wo, "overall": wg}
    )

with st.spinner("Running scheduler…"):
    result: ScheduleResult = cached_run(
        str(selected_path), w_individual, w_operator, w_overall
    )

s_meta = scenario_data["meta"]


# ────────────────────────────────────────────
#  Hero header
# ────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <div class="hero-label">Electric Bus Charging Scheduler</div>
    <div class="hero-title">{s_meta['name']}</div>
    <div class="hero-sub">{s_meta['description']}</div>
    <div style="margin-top: 14px;" class="scenario-pill">
        {''.join(f'<span class="tag-pill">#{t}</span>' for t in s_meta.get('tags', []))}
        <span class="{'valid-badge' if result.is_valid else 'invalid-badge'}">
            {'✓ Valid Schedule' if result.is_valid else '✗ Violations Found'}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

if not result.is_valid:
    viols = "<br>".join(f"• {v}" for v in result.violations)
    st.markdown(f"""
    <div class="violation-banner">
        <b>⚠ Schedule Violations</b><br>
        <span style="font-size:12px;color:#fca5a5;">{viols}</span>
    </div>
    """, unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Top metrics
# ────────────────────────────────────────────
total_buses = len(result.bus_timelines)
total_waits = [tl.total_wait_min for tl in result.bus_timelines]
avg_wait = sum(total_waits) / max(len(total_waits), 1)
max_wait = max(total_waits) if total_waits else 0
total_trip_times = [tl.total_trip_min for tl in result.bus_timelines]
avg_trip = sum(total_trip_times) / max(len(total_trip_times), 1)

# Count buses with zero wait
no_wait = sum(1 for w in total_waits if w < 1)

st.markdown(f"""
<div class="metric-row">
    <div class="metric-card" style="--accent: #3b82f6;">
        <div class="metric-label">Total Buses</div>
        <div class="metric-value">{total_buses}</div>
        <div class="metric-sub">across all operators</div>
    </div>
    <div class="metric-card" style="--accent: #22c55e;">
        <div class="metric-label">Avg Wait</div>
        <div class="metric-value">{avg_wait:.0f}<span style="font-size:14px">m</span></div>
        <div class="metric-sub">per bus at chargers</div>
    </div>
    <div class="metric-card" style="--accent: #f59e0b;">
        <div class="metric-label">Max Wait</div>
        <div class="metric-value">{max_wait:.0f}<span style="font-size:14px">m</span></div>
        <div class="metric-sub">worst single bus</div>
    </div>
    <div class="metric-card" style="--accent: #a855f7;">
        <div class="metric-label">Avg Trip Time</div>
        <div class="metric-value">{avg_trip/60:.1f}<span style="font-size:14px">h</span></div>
        <div class="metric-sub">departure to arrival</div>
    </div>
    <div class="metric-card" style="--accent: #10b981;">
        <div class="metric-label">Zero-Wait</div>
        <div class="metric-value">{no_wait}</div>
        <div class="metric-sub">buses with no queue</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Route map
# ────────────────────────────────────────────
segs = scenario_data["world"]["route"]["segments"]
stops_display = []
for seg in segs:
    stops_display.append(seg["from"])
stops_display.append(segs[-1]["to"])

station_ids_set = {s["id"] for s in scenario_data["world"]["stations"]}

def stop_html(stop_id, label=None):
    is_station = stop_id in station_ids_set
    cls = "stop-station" if is_station else "stop-terminal"
    display = label or stop_id
    color = STATION_COLOR.get(stop_id, "#3b82f6")
    style = f"background: {color}22; border-color: {color};" if is_station else ""
    return f"""
    <div class="stop-node">
        <div class="stop-circle {cls}" style="{style}">{stop_id}</div>
        <div class="stop-label">{display}</div>
    </div>
    """

stop_labels = {
    "BLR": "Bengaluru", "KCH": "Kochi",
    "A": "Stn A", "B": "Stn B", "C": "Stn C", "D": "Stn D"
}

route_html = '<div class="route-map">'
for i, stop_id in enumerate(stops_display):
    route_html += stop_html(stop_id, stop_labels.get(stop_id, stop_id))
    if i < len(stops_display) - 1:
        dist = segs[i]["distance_km"]
        route_html += f"""
        <div class="route-line">
            <span class="route-dist">{dist}km</span>
        </div>
        """
route_html += '</div>'

st.markdown("""
<div class="section-header">
    <div class="section-dot"></div>
    <h3>Route Overview</h3>
</div>
""", unsafe_allow_html=True)
st.markdown(route_html, unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Scenario data table
# ────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <div class="section-dot" style="background:#22c55e;"></div>
    <h3>Scenario Input — Bus Manifest</h3>
</div>
""", unsafe_allow_html=True)

bus_rows = []
for b in scenario_data["buses"]:
    dir_str = "→ Kochi" if b["direction"] == "BLR->KCH" else "→ Bengaluru"
    bus_rows.append({
        "Bus ID": b["id"],
        "Operator": b["operator"].upper(),
        "Direction": dir_str,
        "Departure": b["departure"],
    })
bus_df = pd.DataFrame(bus_rows)

col1, col2 = st.columns([3, 2])
with col1:
    st.dataframe(
        bus_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Bus ID": st.column_config.TextColumn(width="medium"),
            "Operator": st.column_config.TextColumn(width="small"),
            "Direction": st.column_config.TextColumn(width="medium"),
            "Departure": st.column_config.TextColumn(width="small"),
        }
    )
with col2:
    # Operator breakdown
    op_counts = bus_df["Operator"].value_counts()
    st.markdown("""
    <div style="background:#111827;border:1px solid #1f2d3d;border-radius:10px;padding:16px;">
        <div style="font-family:'Space Mono',monospace;font-size:11px;text-transform:uppercase;
                    letter-spacing:0.1em;color:#6b7280;margin-bottom:12px;">Operator Breakdown</div>
    """, unsafe_allow_html=True)
    for op, count in op_counts.items():
        pct = count / len(bus_df) * 100
        color = OP_COLOR.get(op.lower(), "#6b7280")
        st.markdown(f"""
        <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-family:'Space Mono',monospace;font-size:11px;color:{color};">{op}</span>
                <span style="font-family:'Space Mono',monospace;font-size:11px;color:#4b5563;">{count} buses</span>
            </div>
            <div style="height:4px;background:#1f2d3d;border-radius:2px;">
                <div style="height:4px;width:{pct}%;background:{color};border-radius:2px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Per-bus timetable
# ────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <div class="section-dot" style="background:#f59e0b;"></div>
    <h3>Per-Bus Timetable</h3>
</div>
""", unsafe_allow_html=True)

# Filter controls
col_f1, col_f2 = st.columns([2, 2])
with col_f1:
    dir_filter = st.selectbox(
        "Direction",
        ["All", "Bengaluru → Kochi", "Kochi → Bengaluru"],
        label_visibility="collapsed",
    )
with col_f2:
    op_filter = st.selectbox(
        "Operator",
        ["All Operators", "KPN", "Freshbus", "Flixbus"],
        label_visibility="collapsed",
    )

def passes_filter(tl: BusTimeline) -> bool:
    if dir_filter == "Bengaluru → Kochi" and tl.bus.direction.value != "BLR->KCH":
        return False
    if dir_filter == "Kochi → Bengaluru" and tl.bus.direction.value != "KCH->BLR":
        return False
    if op_filter != "All Operators" and tl.bus.operator_id.lower() != op_filter.lower():
        return False
    return True

filtered = [tl for tl in result.bus_timelines if passes_filter(tl)]
filtered.sort(key=lambda tl: tl.departure_time_min)

# Compute timeline extents for proportional bars
all_times = []
for tl in filtered:
    all_times.append(tl.departure_time_min)
    all_times.append(tl.arrival_time_min)
t_min = min(all_times) if all_times else 0
t_max = max(all_times) if all_times else 1
t_span = max(t_max - t_min, 1)

for tl in filtered:
    op = tl.bus.operator_id
    op_color = OP_COLOR.get(op, "#6b7280")
    dir_label = "BLR → KCH" if tl.bus.direction.value == "BLR->KCH" else "KCH → BLR"
    dir_color = "#f59e0b" if tl.bus.direction.value == "BLR->KCH" else "#a78bfa"

    # Build charge stop summary
    stations_used = tl.stations_used
    stop_html_parts = []
    for s_id in stations_used:
        c = STATION_COLOR.get(s_id, "#6b7280")
        stop_html_parts.append(
            f'<span style="background:{c}22;color:{c};border:1px solid {c}44;'
            f'padding:1px 8px;border-radius:4px;font-family:\'Space Mono\',monospace;'
            f'font-size:10px;">Stn {s_id}</span>'
        )
    stops_html = " ".join(stop_html_parts) if stop_html_parts else \
        '<span style="color:#4b5563;font-size:10px;">—</span>'

    charge_details = []
    for ev in tl.charge_events:
        c = STATION_COLOR.get(ev.station_id, "#6b7280")
        wait_str = f"+{fmt_duration(ev.wait_min)}" if ev.wait_min >= 1 else "no wait"
        charge_details.append(
            f'<div style="font-size:11px;color:#94a3b8;padding:4px 0;'
            f'border-bottom:1px solid #1e2736;">'
            f'<span style="color:{c};font-family:\'Space Mono\',monospace;font-weight:700;">Stn {ev.station_id}</span>'
            f' &nbsp; arrive <span style="color:#f1f5f9">{fmt_time(ev.arrive_time_min)}</span>'
            f' &nbsp; charge <span style="color:#4ade80">{fmt_time(ev.charge_start_min)} → {fmt_time(ev.charge_end_min)}</span>'
            f' &nbsp; <span style="color:{("#f87171" if ev.wait_min > 20 else "#fbbf24") if ev.wait_min > 0 else "#4ade80"}">'
            f'{wait_str}</span></div>'
        )
    charge_html = "\n".join(charge_details) if charge_details else \
        '<div style="font-size:11px;color:#4b5563;">No charge events</div>'

    st.markdown(f"""
    <div class="bus-card">
        <div class="bus-card-header">
            <div style="display:flex;align-items:center;gap:12px;">
                <span class="bus-id">{tl.bus.id}</span>
                {operator_badge(op)}
                <span style="font-size:11px;color:{dir_color};font-family:'Space Mono',monospace;">{dir_label}</span>
            </div>
            <div style="display:flex;gap:16px;align-items:center;">
                <div style="text-align:right;">
                    <div style="font-size:9px;color:#4b5563;text-transform:uppercase;letter-spacing:0.08em;">Departs</div>
                    <div style="font-family:'Space Mono',monospace;font-size:12px;color:#94a3b8;">{fmt_time(tl.departure_time_min)}</div>
                </div>
                <div style="color:#374151;font-size:16px;">→</div>
                <div style="text-align:right;">
                    <div style="font-size:9px;color:#4b5563;text-transform:uppercase;letter-spacing:0.08em;">Arrives</div>
                    <div style="font-family:'Space Mono',monospace;font-size:13px;color:#f1f5f9;font-weight:700;">{fmt_time(tl.arrival_time_min)}</div>
                </div>
                <div style="background:#1f2d3d;border-radius:6px;padding:6px 12px;text-align:center;">
                    <div style="font-size:9px;color:#4b5563;text-transform:uppercase;">Trip</div>
                    <div style="font-family:'Space Mono',monospace;font-size:12px;color:#60a5fa;">{fmt_duration(tl.total_trip_min)}</div>
                </div>
                <div style="background:{'#3b1f1f' if tl.total_wait_min > 20 else '#1a3d2b'};border-radius:6px;padding:6px 12px;text-align:center;">
                    <div style="font-size:9px;color:#4b5563;text-transform:uppercase;">Wait</div>
                    <div style="font-family:'Space Mono',monospace;font-size:12px;color:{'#f87171' if tl.total_wait_min > 20 else '#4ade80'};">{fmt_duration(tl.total_wait_min)}</div>
                </div>
            </div>
        </div>
        <div style="margin-bottom:10px;">{stops_html}</div>
        <div style="border-top:1px solid #1e2736;padding-top:10px;">{charge_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Per-station view
# ────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <div class="section-dot" style="background:#a855f7;"></div>
    <h3>Per-Station Queue</h3>
</div>
""", unsafe_allow_html=True)

station_order = ["A", "B", "C", "D"]
station_cols = st.columns(4)

for col_idx, station_id in enumerate(station_order):
    slog = result.station_logs.get(station_id)
    s_color = STATION_COLOR.get(station_id, "#6b7280")

    with station_cols[col_idx]:
        events = slog.events if slog else []
        total_wait_at_station = sum(e.wait_min for e in events)
        utilisation_start = events[0].charge_start_min if events else 0
        utilisation_end   = events[-1].charge_end_min  if events else 0

        st.markdown(f"""
        <div style="background:#111827;border:1px solid #1f2d3d;border-radius:10px;
                    padding:16px;margin-bottom:12px;border-top:3px solid {s_color};">
            <div style="font-family:'Space Mono',monospace;font-size:22px;font-weight:700;
                        color:{s_color};">Station {station_id}</div>
            <div style="font-size:11px;color:#4b5563;margin-top:2px;">
                {len(events)} buses · {fmt_duration(total_wait_at_station)} total wait
            </div>
            {f'<div style="font-size:10px;color:#374151;margin-top:6px;font-family:\'Space Mono\',monospace;">{fmt_time(utilisation_start)} – {fmt_time(utilisation_end)}</div>' if events else ''}
        </div>
        """, unsafe_allow_html=True)

        if not events:
            st.markdown('<div style="font-size:12px;color:#374151;padding:8px;">No buses charged here</div>',
                        unsafe_allow_html=True)
            continue

        for pos, ev in enumerate(events, 1):
            # Find this bus's operator
            bus_obj = next((b for b in result.bus_timelines if b.bus.id == ev.bus_id), None)
            op_id = bus_obj.bus.operator_id if bus_obj else "unknown"
            op_color = OP_COLOR.get(op_id, "#6b7280")

            st.markdown(f"""
            <div class="queue-entry">
                <div class="queue-number">{pos}</div>
                <div style="flex:1;min-width:0;">
                    <div class="queue-bus-id" style="color:{op_color};">{ev.bus_id}</div>
                    <div style="font-size:10px;color:#4b5563;font-family:'Space Mono',monospace;">
                        {fmt_time(ev.charge_start_min)} → {fmt_time(ev.charge_end_min)}
                    </div>
                </div>
                {wait_badge(ev.wait_min)}
            </div>
            """, unsafe_allow_html=True)


# ────────────────────────────────────────────
#  Weight explanation footer
# ────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="background:#0d1117;border:1px solid #1e2736;border-radius:10px;padding:20px;margin-top:16px;">
    <div style="font-family:'Space Mono',monospace;font-size:11px;text-transform:uppercase;
                letter-spacing:0.1em;color:#374151;margin-bottom:12px;">Active Weights</div>
    <div style="display:flex;gap:24px;flex-wrap:wrap;">
""", unsafe_allow_html=True)

weight_descs = {
    "Individual": (w_individual, "Penalises long waits for a single bus. High → every bus gets treated fairly."),
    "Operator":   (w_operator,   "Penalises operator-level imbalance. High → KPN/Freshbus/Flixbus get equitable throughput."),
    "Overall":    (w_overall,    "Penalises total network delay. High → earliest-arriving bus always wins."),
}
for label, (val, desc) in weight_descs.items():
    bar_w = int(val / 3.0 * 100)
    st.markdown(f"""
    <div style="flex:1;min-width:180px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
            <span style="font-family:'Space Mono',monospace;font-size:11px;color:#94a3b8;">{label}</span>
            <span style="font-family:'Space Mono',monospace;font-size:11px;color:#3b82f6;">{val:.1f}</span>
        </div>
        <div style="height:3px;background:#1f2d3d;border-radius:2px;margin-bottom:6px;">
            <div style="height:3px;width:{bar_w}%;background:#3b82f6;border-radius:2px;"></div>
        </div>
        <div style="font-size:11px;color:#4b5563;">{desc}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)