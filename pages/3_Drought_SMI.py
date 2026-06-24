# -*- coding: utf-8 -*-

from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data_sources import (
    DEFAULT_STOCKS,
    STOCKS,
    SMI_BANDS,
    SMI_BAND_COLORS,
    SMI_BAND_LABELS,
    SMI_SOURCES,
    SWAP_SM_DEPTHS,
    add_smi_bands,
    load_time_series,
    selected_max_date,
    selected_min_date,
    smi_band,
)

st.set_page_config(
    page_title="Dürremonitor (SMI)",
    page_icon=":material/water_drop:",
    layout="wide",
)

st.title("Dürremonitor (SMI)")
st.write(
    "Bodenfeuchteindex (SMI) nach [UFZ-Dürreklassifizierung](https://www.ufz.de/index.php?de=37937). "
    "Der SMI liegt zwischen 0 (sehr trocken) "
    "und 1 (sehr feucht) und wird in Dürrekategorien eingeteilt. Die Kacheln zeigen den "
    "aktuellen Status je Standort; darunter der zeitliche Verlauf mit hinterlegten "
    "Dürrebändern. Optional kann die SWAP-Bodenfeuchte verschiedener Tiefen auf einer "
    "zweiten Achse überlagert werden. "
    "Die Berechnung des SMI erfolgt angelehnt an Samaniego et al., 2013 und Zink et al., 2016 unter Nutzung des 14-tägigen Mitttels der Bodenfeuchte (Boeing et al., 2022). "
    "Über Density Kernel Funktionen wird die aktuelle Bodenfeuchte in Relation zu den langjährigen SWAP Simulationen gesetzt und in die Dürreklassen eingeordnet, wobei die historische Verteilungen für jeden Tga im Har aus den "
    "dem 14-tägige Gleitende Mittel der Bodenfeuchte über die Referenzperiode von 1994 bis 2024 berücksichtigt berechnet wird."
    "Die Einordnung der aktuellen Bodenfeuchte basiert auf den langjährigen SWAP Bodenfeuchten Simulationen mit einer derzeitigen Referenzperiode von 1994 bis 2024 und wird analog zum UFZ Monitor Klassifiziert (Kumar et al., 2013; Marx et al., o.J.)"
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


# --- Source selection --------------------------------------------------------
source_name = st.selectbox("SMI-Quelle", options=list(SMI_SOURCES.keys()))

try:
    smi = load_time_series(SMI_SOURCES[source_name])
except Exception:
    st.warning(
        "SMI-Daten sind derzeit nicht verfügbar "
        "(Datei evtl. noch nicht im Online-Verzeichnis)."
    )
    st.stop()

available = [s for s in STOCKS if s in smi.columns]
if not available:
    st.warning("Keine Standorte in den SMI-Daten gefunden.")
    st.stop()

# --- Status badges: traffic light for every station, driest first ------------
latest_value = {}
latest_date = {}
for s in available:
    series = smi[s].dropna()
    if series.empty:
        latest_value[s] = None
        latest_date[s] = None
    else:
        latest_value[s] = float(series.iloc[-1])
        latest_date[s] = series.index[-1]

order = sorted(
    available,
    key=lambda s: (
        latest_value[s] is None,
        latest_value[s] if latest_value[s] is not None else 1.0,
    ),
)

st.subheader("Aktueller Status")
PER_ROW = 6
for row_start in range(0, len(order), PER_ROW):
    cols = st.columns(PER_ROW, gap="medium")
    for j, station in enumerate(order[row_start : row_start + PER_ROW]):
        value = latest_value[station]
        _, label, color = smi_band(value)
        text_color = _text_on(color)
        value_str = "–" if value is None else f"{value:.2f}"
        date_str = (
            ""
            if latest_date[station] is None
            else latest_date[station].date().isoformat()
        )
        cols[j].markdown(
            f"""
<div style="background:{color};color:{text_color};border-radius:10px;margin:4px 0;
            padding:10px 6px;text-align:center;line-height:1.25;">
  <div style="font-weight:700;font-size:1.05rem;">{station}</div>
  <div style="font-size:1.3rem;font-weight:700;">{value_str}</div>
  <div style="font-size:0.78rem;">{label}</div>
  <div style="font-size:0.68rem;opacity:0.85;">{date_str}</div>
</div>
""",
            unsafe_allow_html=True,
        )

# Band legend (driest -> wettest).
legend_chips = "".join(
    f'<span style="background:{SMI_BAND_COLORS[key]};color:{_text_on(SMI_BAND_COLORS[key])};'
    f"padding:2px 8px;border-radius:4px;margin:2px 4px 2px 0;display:inline-block;"
    f'font-size:0.78rem;">{SMI_BAND_LABELS[key]}</span>'
    for _, _, key in SMI_BANDS
)
st.markdown(legend_chips, unsafe_allow_html=True)

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
    swap_depths = st.multiselect(
        "SWAP-Bodenfeuchte",
        options=list(SWAP_SM_DEPTHS.keys()),
        default=[],
        placeholder="Wähle Tiefen",
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

has_secondary = bool(swap_depths)
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

# Optional SWAP soil-moisture overlays on the secondary axis.
for depth_label in swap_depths:
    try:
        swap_sm = load_time_series(SWAP_SM_DEPTHS[depth_label])
    except Exception:
        st.warning(f"SWAP-Bodenfeuchte ({depth_label}) nicht verfügbar.")
        continue
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
                name=f"{station} · SWAP {depth_label}",
                legendgroup=station,
                line=dict(color=STATION_COLORS.get(station, "#444444"), dash="dot"),
                opacity=0.8,
            ),
            secondary_y=True,
        )

fig.update_yaxes(title_text="SMI (0–1)", range=[0, 1], secondary_y=False)
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
        - Marx, A., Samaniego, L., Kumar, R., Thober, S., Mai, J., & Zink, M. (o. J.). Der Dürremonitor – Aktuelle Information zur Bodenfeuchte in Deutschland.
        - Samaniego, L., Kumar, R., & Zink, M. (2013). Implications of Parameter Uncertainty on Soil Moisture Drought Analysis in Germany. Journal of Hydrometeorology, 14(1), 47–68. https://doi.org/10.1175/JHM-D-12-075.1
        - Zink, M., Samaniego, L., Kumar, R., Thober, S., Mai, J., Schäfer, D., & Marx, A. (2016). The German drought monitor. Environmental Research Letters, 11(7), 074002. https://doi.org/10.1088/1748-9326/11/7/074002

        """
    )
