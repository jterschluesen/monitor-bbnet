# -*- coding: utf-8 -*-

from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data_sources import (
    DEFAULT_SMI_DEPTH,
    DEFAULT_STOCKS,
    STOCKS,
    SMI_BANDS,
    SMI_BAND_COLORS,
    SMI_BAND_LABELS,
    SMI_DEPTHS,
    SMI_POOL_HALFWIDTH_DAYS,
    SMI_REFERENCE_PERIOD,
    SMI_SWAP_DEPTH,
    SWAP_SM_DEPTHS,
    add_smi_bands,
    construction_warning,
    load_smi,
    load_smi_steps,
    load_time_series,
    selected_max_date,
    selected_min_date,
    smi_band,
    smi_censoring,
)

st.set_page_config(
    page_title="Bodenfeuchteindex",
    page_icon=":material/water_drop:",
    layout="wide",
)

construction_warning()

st.title("Klimatischer Bodenfeuchteindex")
st.write(
    f"Der klimatische Bodenfeuchteindex ordnet die **aktuelle Bodenfeuchte** "
    f"der SWAP-Simulationen in die historische Verteilung am selben Kalendertag ein. "
    f"Er liegt zwischen 0 (sehr trocken) und 1 (sehr nass). "
    f"Die Kacheln zeigen den aktuellen Status je Standort, während das darunter liegende Diagramm den zeitlichen Verlauf inklusive Dürre- und Nässebändern visualisiert. Optional kann die SWAP-Bodenfeuchte "
    f"derselben Tiefe auf einer zweiten Achse überlagert werden. Die Klassifikation der trockenen Seite folgt dem Schema der [UFZ-Dürreklassifizierung](https://www.ufz.de/index.php?de=37937) "
    f"(Kumar et al., 2013; Marx et al., o. J.); die nasse Seite ist mit denselben Schwellen gespiegelt (0,70/0,80/0,90/0,95/0,98). \n\n"
    f"Die Grundlage der Berechnung bildet die **empirische Verteilungsfunktion (Weibull-Plotting-Positions)** "
    f"der Referenzperiode {SMI_REFERENCE_PERIOD} aus der SWAP Simulation. Jeder Kalendertag hat seine eigene "
    f"Verteilung, welche aus dem Pool aller Bodenfeuchtewerte im Fenster von "
    f"±{SMI_POOL_HALFWIDTH_DAYS} Tagen um dieses Datum über den Referenzzeitraum gebildet wird. "
    f"Die Datengrundlage unterscheidet sich somit von der des Dürreindexes des UFZ-Dürremonitor (Samaniego et al., 2013; Zink et al., 2016). "
    f"Der Index beschreibt die empirische Unterschreitungswahrscheinlichkeit der aktuellen "
    f"Bodenfeuchte und stellt eine Einordnung in die historische Verteilung dar. Die Tiefe der gemittelten Bodenfeuchte ist wählbar "
    f"({', '.join(SMI_DEPTHS)})"
    f".\n\n"
    f"Eine empirische Verteilung ist nach unten und oben begrenzt: Liegt die aktuelle "
    f"Bodenfeuchte auf oder unter der **untersten** bzw. auf oder über der **obersten "
    f"Stufe** der Verteilungsfunktion, lässt sich der SMI nicht auflösen. Solche Standorte sind unter "
    f"„Aktueller Status“ **gestrichelt umrandet** und zeigen, dass es sich extreme Bedingungen handelt."
)

# Stable colour-vision-deficiency-safe colour per station (CARTO "Safe").
STATION_COLORS = {
    s: px.colors.qualitative.Safe[i % len(px.colors.qualitative.Safe)]
    for i, s in enumerate(STOCKS)
}


def _text_on(hex_color: str) -> str:
    """Pick black/white text for legibility on a given background hex."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.55 else "#ffffff"


# --- Depth selection ---------------------------------------------------------
depth_label = st.segmented_control(
    "Tiefe",
    options=list(SMI_DEPTHS.keys()),
    default=DEFAULT_SMI_DEPTH,
    selection_mode="single",
)
depth_label = depth_label if depth_label in SMI_DEPTHS else DEFAULT_SMI_DEPTH
depth_key = SMI_DEPTHS[depth_label]

try:
    smi = load_smi(depth_key)
except Exception:
    st.warning(
        "SMI-Daten sind derzeit nicht verfügbar "
        "(Datei evtl. noch nicht im Online-Verzeichnis)."
    )
    st.stop()

try:
    first_step, last_step = load_smi_steps(depth_key)
except Exception:
    # Fail soft: without the CDF bounds we simply cannot flag unresolvable SMI.
    st.warning(
        "Die Grenzen der empirischen Verteilung sind derzeit nicht verfügbar – "
        "nicht auflösbare SMI-Werte können nicht markiert werden."
    )
    first_step = last_step = pd.DataFrame()

available = [s for s in STOCKS if s in smi.columns]
if not available:
    st.warning("Keine Standorte in den SMI-Daten gefunden.")
    st.stop()


def _step_at(steps: pd.DataFrame, station, when):
    """Step value for a station at a date, or None if unavailable."""
    if steps.empty or station not in steps.columns or when is None:
        return None
    series = steps[station].dropna()
    if when not in series.index:
        return None
    return float(series.loc[when])


# --- Status badges: traffic light for every station, driest first ------------
latest_value = {}
latest_date = {}
censoring = {}
for s in available:
    series = smi[s].dropna()
    if series.empty:
        latest_value[s] = None
        latest_date[s] = None
        censoring[s] = None
        continue
    latest_value[s] = float(series.iloc[-1])
    latest_date[s] = series.index[-1]
    censoring[s] = smi_censoring(
        latest_value[s],
        _step_at(first_step, s, latest_date[s]),
        _step_at(last_step, s, latest_date[s]),
    )

order = sorted(
    available,
    key=lambda s: (
        latest_value[s] is None,
        latest_value[s] if latest_value[s] is not None else 1.0,
    ),
)

st.subheader("Aktueller Status")

grid_col, legend_col = st.columns([3, 2.2], gap="medium")

with grid_col:
    PER_ROW = 3
    for row_start in range(0, len(order), PER_ROW):
        cols = st.columns(PER_ROW, gap="medium")
        for j, station in enumerate(order[row_start : row_start + PER_ROW]):
            value = latest_value[station]
            _, label, color = smi_band(value)
            text_color = _text_on(color)
            censor = censoring[station]
            if value is None:
                value_str = "–"
            elif censor == "low":
                value_str = f"≤ {value:.2f}"
            elif censor == "high":
                value_str = f"≥ {value:.2f}"
            else:
                value_str = f"{value:.2f}"
            # Keep the border in both cases so tiles stay the same size.
            border = f"3px dashed {text_color}" if censor else "3px solid transparent"
            hint = (
                " title='SMI nicht auflösbar: Bodenfeuchte am Rand der empirischen Verteilung'"
                if censor
                else ""
            )
            date_str = (
                ""
                if latest_date[station] is None
                else latest_date[station].date().isoformat()
            )
            cols[j].markdown(
                f"""
<div{hint} style="background:{color};color:{text_color};border-radius:10px;margin:4px 0;
            padding:10px 6px;text-align:center;line-height:1.25;border:{border};">
  <div style="font-weight:700;font-size:1.05rem;">{station}</div>
  <div style="font-size:1.3rem;font-weight:700;">{value_str}</div>
  <div style="font-size:0.78rem;">{label}</div>
  <div style="font-size:0.68rem;opacity:0.85;">{date_str}</div>
</div>
""",
                unsafe_allow_html=True,
            )

def _legend_rows(bands):
    """Legend rows, driest -> wettest, with SMI ranges and percentile classes."""
    return "".join(
        f'<div style="display:flex;align-items:center;margin:8px 0;">'
        f'<span style="background:{SMI_BAND_COLORS[key]};width:26px;height:26px;'
        f"border-radius:5px;display:inline-block;margin-right:10px;flex:0 0 auto;"
        f'border:1px solid rgba(0,0,0,0.15);"></span>'
        f'<span style="font-size:0.92rem;line-height:1.25;">'
        f"<b>{SMI_BAND_LABELS[key]}</b><br>"
        f'<span style="opacity:0.7;">SMI {lo:.2f}–{min(hi, 1.0):.2f} · '
        f"{int(round(lo * 100))}.–{int(round(min(hi, 1.0) * 100))}. Perzentil</span>"
        f"</span></div>"
        for lo, hi, key in bands
    )


with legend_col:
    st.markdown("**Klassifizierung**")
    # Dry half (incl. the normal class) left, wet half right.
    dry_bands = [b for b in SMI_BANDS if b[0] < 0.70]
    wet_bands = [b for b in SMI_BANDS if b[0] >= 0.70]
    dry_col, wet_col = st.columns(2, gap="medium")
    dry_col.markdown(_legend_rows(dry_bands), unsafe_allow_html=True)
    wet_col.markdown(_legend_rows(wet_bands), unsafe_allow_html=True)
    st.markdown(
        '<div style="display:flex;align-items:center;margin:14px 0 4px 0;">'
        '<span style="width:26px;height:26px;border-radius:5px;display:inline-block;'
        "margin-right:10px;flex:0 0 auto;border:3px dashed currentColor;"
        'opacity:0.8;"></span>'
        '<span style="font-size:0.92rem;line-height:1.25;">'
        "<b>SMI nicht auflösbar</b><br>"
        '<span style="opacity:0.7;">Bodenfeuchte auf oder jenseits der untersten/'
        "obersten Stufe der empirischen Verteilung; der Wert ist nur eine "
        "Ober- (≤) bzw. Untergrenze (≥).</span></span></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Ordinale Skala zwischen 0 (sehr trocken) und 1 (sehr nass). Dürreklassen nach "
        "[UFZ-Dürreklassifizierung](https://www.ufz.de/index.php?de=37937), "
        "Nässeklassen an denselben Schwellen gespiegelt."
    )

st.divider()

# --- Time series with drought bands ------------------------------------------
st.subheader("Zeitlicher Verlauf")

default_sel = [s for s in DEFAULT_STOCKS if s in available] or available[:3]
sel_stations = st.multiselect("Standorte", options=available, default=default_sel)

control_cols = st.columns([3, 2])
horizon_map = {
    # "Maximum": None,
    "Letzte 7 Tage": 7,
    "Letzte 14 Tage": 14,
    "Letzte 3 Monate": 90,
    "1 Jahr": 365,
    "3 Jahre": 3 * 365,
    # "5 Jahre": 5 * 365,
    "10 Jahre": 10 * 365,
    # "30 Jahre": 30 * 365,
}
with control_cols[0]:
    horizon = st.pills(
        "Zeithorizont",
        options=list(horizon_map.keys()),
        default="Letzte 14 Tage",
        selection_mode="single",
    )
with control_cols[1]:
    # Only the depth the SMI itself is derived from can be overlaid.
    swap_label = SMI_SWAP_DEPTH[depth_key]
    show_swap = st.checkbox(
        f"SWAP-Bodenfeuchte ({swap_label}) überlagern",
        value=False,
    )

if not sel_stations:
    st.info("Wähle mindestens einen Standort für den Verlauf.")
    st.stop()

horizon = horizon if horizon in horizon_map else "Maximum"
min_date = selected_min_date(smi, sel_stations)
today = pd.Timestamp.today().normalize()
horizon_days = horizon_map[horizon]
if horizon_days is None:
    start = pd.Timestamp(min_date)
else:
    start = max(pd.Timestamp(min_date), today - timedelta(days=horizon_days))
end = pd.Timestamp(selected_max_date(smi, sel_stations))

has_secondary = bool(show_swap)
fig = make_subplots(specs=[[{"secondary_y": has_secondary}]])
add_smi_bands(fig)

for station in sel_stations:
    series = smi.loc[start:end, station] if station in smi.columns else None
    if series is None or series.dropna().empty:
        continue
    fig.add_trace(
        go.Scatter(
            x=series.index,
            y=series,
            mode="lines",
            name=station,
            legendgroup=station,
            line=dict(color=STATION_COLORS.get(station, "#444444")),
        ),
        secondary_y=False,
    )

# Optional SWAP soil-moisture overlay (same depth as the SMI) on the secondary axis.
if show_swap:
    try:
        swap_sm = load_time_series(SWAP_SM_DEPTHS[swap_label])
    except Exception:
        swap_sm = pd.DataFrame()
        st.warning(f"SWAP-Bodenfeuchte ({swap_label}) nicht verfügbar.")
    for station in sel_stations:
        if station not in swap_sm.columns:
            continue
        series = swap_sm.loc[start:end, station]
        if series.dropna().empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series,
                mode="lines",
                name=f"{station} · SWAP {swap_label}",
                legendgroup=station,
                line=dict(color=STATION_COLORS.get(station, "#444444"), dash="dot"),
                opacity=0.8,
            ),
            secondary_y=True,
        )

fig.update_yaxes(title_text=f"SMI {depth_label} (0–1)", range=[0, 1], secondary_y=False)
if has_secondary:
    fig.update_yaxes(title_text="SWAP-Bodenfeuchte (m³/m³)", secondary_y=True)
fig.update_layout(
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    margin=dict(l=40, r=20, t=20, b=80),
    height=480,
)

st.plotly_chart(fig, width="stretch")

with st.expander("Quellen", expanded=False):
    st.markdown(
        """
        - Boeing, F., Rakovec, O., Kumar, R., Samaniego, L., Schrön, M., Hildebrandt, A., Rebmann, C., Thober, S., Müller, S., Zacharias, S., Bogena, H., Schneider, K., Kiese, R., Attinger, S., & Marx, A. (2022). High-resolution drought simulations and comparison to soil moisture observations in Germany. Hydrology and Earth System Sciences, 26(19), 5137–5161. https://doi.org/10.5194/hess-26-5137-2022
        - Kumar, R., Samaniego, L., & Attinger, S. (2013). Implications of distributed hydrologic model parameterization on water fluxes at multiple scales and locations. Water Resources Research, 49(1), 360–379. https://doi.org/10.1029/2012WR012195
        - Marx, A., Samaniego, L., Kumar, R., Thober, S., Mai, J., & Zink, M. (o. J.). Der Dürremonitor – Aktuelle Information zur Bodenfeuchte in Deutschland.
        - Samaniego, L., Kumar, R., & Zink, M. (2013). Implications of Parameter Uncertainty on Soil Moisture Drought Analysis in Germany. Journal of Hydrometeorology, 14(1), 47–68. https://doi.org/10.1175/JHM-D-12-075.1
        - Zink, M., Samaniego, L., Kumar, R., Thober, S., Mai, J., Schäfer, D., & Marx, A. (2016). The German drought monitor. Environmental Research Letters, 11(7), 074002. https://doi.org/10.1088/1748-9326/11/7/074002

        """
    )
