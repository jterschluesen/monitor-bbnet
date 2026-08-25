# -*- coding: utf-8 -*-

from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from data_sources import (
    DEFAULT_SMI_DEPTH,
    FULL_RANGE_LABEL,
    STOCKS,
    SMI_BANDS,
    SMI_BAND_COLORS,
    SMI_BAND_LABELS,
    SMI_DEPTHS,
    SMI_POOL_HALFWIDTH_DAYS,
    SMI_REFERENCE_PERIOD,
    SMI_SWAP_DEPTH,
    SWAP_SM_DEPTHS,
    URL_LOCATIONS,
    PLOT_CONFIG,
    add_smi_bands,
    construction_warning,
    get_shared_stations,
    glossary_expander,
    load_locations,
    load_smi,
    load_smi_steps,
    load_time_series,
    moisture_label,
    selected_max_date,
    selected_min_date,
    smi_band,
    smi_censoring,
    station_label,
    station_labeller,
    to_plot_unit,
)

st.set_page_config(
    page_title="Bodenfeuchteindex",
    page_icon=":material/water_drop:",
    layout="wide",
)

construction_warning()

st.title("Klimatischer Bodenfeuchteindex")
st.write(
    f"Der klimatische Bodenfeuchteindex ordnet die **aktuelle Bodenfeuchte** aus dem "
    f"Bodenwasserhaushaltsmodell [SWAP](https://www.swap.alterra.nl/) in die historische "
    f"Verteilung am selben Kalendertag ein. Er liegt zwischen 0 (sehr trocken) und 1 "
    f"(sehr nass). Die Kacheln zeigen den aktuellen Status je Standort für drei "
    f"Tiefen ({', '.join(SMI_DEPTHS)}). Im darunter liegenden Diagramm findet sich der zeitliche "
    f"Verlauf des Indexes und optional der modellierte Bodenfeuchte. "
    f"Die Klassifikation des Indexes folgt dem Schema der Dürreklassifizierung des "
    f"Helmholtz-Zentrums für Umweltforschung "
    f"([UFZ](https://www.ufz.de/index.php?de=37937), Kumar et al., 2013; Marx et al., o. J.), wobei "
    f"die nasse Seite ist mit denselben Grenzen gespiegelt wurde und "
    f"in Blautönen dargestellt ist. Der Bereich zwischen 0,30 und 0,70 gilt als „normal“.\n\n"
    f"Die Grundlage der Berechnung bildet die **empirische Verteilungsfunktion "
    f"(Weibull-Plotting-Positions)** der Referenzperiode {SMI_REFERENCE_PERIOD} aus der "
    f"Modellsimulation. Jeder Kalendertag hat seine eigene Verteilung, welche aus dem Pool "
    f"aller Bodenfeuchtewerte im Fenster von ±{SMI_POOL_HALFWIDTH_DAYS} Tagen um dieses "
    f"Datum über den Referenzzeitraum gebildet wird. Die Datengrundlage und Berechnung unterscheidet sich "
    f"somit von der des Dürremonitors des UFZ (Samaniego et al., 2013; Zink et al., 2016). "
    f"Der Index beschreibt die empirische Unterschreitungswahrscheinlichkeit der aktuellen "
    f"Bodenfeuchte und stellt eine Einordnung in die historische Verteilung dar.\n\n"
    f"Da die empirische Verteilung durch minimal und maximal gemessene Werte nach unten und oben begrenzt ist, kann der Index für Bodenfeuchtewerte außerhalb dieser Grenzen nicht aufgelöst werden. "
    f"Liegt die aktuelle Bodenfeuchte auf oder unter der untersten bzw. auf oder über der obersten Stufe der Verteilungsfunktion, "
    f"ist dieser unter „Aktueller Status“ **gestrichelt umrandet** und zeigt extreme Bedingungen an."
)

# Stable colour-vision-deficiency-safe colour per station (CARTO "Safe").
STATION_COLORS = {
    s: px.colors.qualitative.Safe[i % len(px.colors.qualitative.Safe)]
    for i, s in enumerate(STOCKS)
}


# Frame around an unresolvable index: the colour of the class the value is beyond,
# i.e. exceptional drought at the dry bound and exceptional wetness at the wet one.
CENSOR_FRAME_COLORS = {
    "low": SMI_BAND_COLORS["exceptional"],
    "high": SMI_BAND_COLORS["exceptional_wet"],
}


def _text_on(hex_color: str) -> str:
    """Pick black/white text for legibility on a given background hex."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.55 else "#ffffff"


locs = load_locations(URL_LOCATIONS)

# --- Load every depth; the status tiles show all of them ---------------------
smi_by_depth = {}
steps_by_depth = {}
missing_depths = []
missing_steps = []
for label, key in SMI_DEPTHS.items():
    try:
        smi_by_depth[label] = load_smi(key)
    except Exception:
        missing_depths.append(label)
        continue
    try:
        steps_by_depth[label] = load_smi_steps(key)
    except Exception:
        # Fail soft: without the bounds we simply cannot flag unresolvable values.
        steps_by_depth[label] = (pd.DataFrame(), pd.DataFrame())
        missing_steps.append(label)

if not smi_by_depth:
    st.warning(
        "Die Daten des Bodenfeuchteindex sind derzeit nicht verfügbar "
        "(Dateien evtl. noch nicht im Online-Verzeichnis)."
    )
    st.stop()

if missing_depths:
    st.warning(
        "Für folgende Tiefen liegen derzeit keine Daten vor: "
        f"{', '.join(missing_depths)}."
    )
if missing_steps:
    st.caption(
        "Die Grenzen der empirischen Verteilung fehlen für "
        f"{', '.join(missing_steps)} – nicht auflösbare Werte sind dort nicht markiert."
    )

depth_labels = list(smi_by_depth)
status_depth = (
    DEFAULT_SMI_DEPTH if DEFAULT_SMI_DEPTH in depth_labels else depth_labels[0]
)

available = [
    s for s in STOCKS if any(s in frame.columns for frame in smi_by_depth.values())
]
if not available:
    st.warning("Keine Standorte in den Daten des Bodenfeuchteindex gefunden.")
    st.stop()


def _step_at(steps: pd.DataFrame, station, when):
    """Step value for a station at a date, or None if unavailable."""
    if steps.empty or station not in steps.columns or when is None:
        return None
    series = steps[station].dropna()
    if when not in series.index:
        return None
    return float(series.loc[when])


# --- Status tiles: one per station, one row per depth, driest first ----------
# status[station][depth_label] = (value, date, censoring)
status = {}
for station in available:
    per_depth = {}
    for label in depth_labels:
        frame = smi_by_depth[label]
        if station not in frame.columns:
            per_depth[label] = (None, None, None)
            continue
        series = frame[station].dropna()
        if series.empty:
            per_depth[label] = (None, None, None)
            continue
        value = float(series.iloc[-1])
        when = series.index[-1]
        first_step, last_step = steps_by_depth.get(
            label, (pd.DataFrame(), pd.DataFrame())
        )
        per_depth[label] = (
            value,
            when,
            smi_censoring(
                value,
                _step_at(first_step, station, when),
                _step_at(last_step, station, when),
            ),
        )
    status[station] = per_depth


def _sort_key(station):
    value = status[station][status_depth][0]
    if value is None:
        # Fall back to the mean of the other depths so a missing default depth
        # does not push an otherwise very dry station to the end.
        others = [v for v, _, _ in status[station].values() if v is not None]
        if others:
            return (1, sum(others) / len(others))
        return (2, 1.0)
    return (0, value)


order = sorted(available, key=_sort_key)

st.subheader("Aktueller Status")
st.caption(
    f"Je Standort eine Kachel mit allen Tiefen; sortiert nach dem trockensten Wert "
    f"für {status_depth}."
)

grid_col, legend_col = st.columns([3, 1], gap="medium")

with grid_col:
    PER_ROW = 4
    for row_start in range(0, len(order), PER_ROW):
        cols = st.columns(PER_ROW, gap="medium")
        for j, station in enumerate(order[row_start : row_start + PER_ROW]):
            depth_rows = []
            dates = []
            for label in depth_labels:
                value, when, censor = status[station][label]
                _, band_label, color = smi_band(value)
                text_color = _text_on(color)
                if value is None:
                    value_str = "–"
                elif censor == "low":
                    value_str = f"≤ {value:.2f}"
                elif censor == "high":
                    value_str = f"≥ {value:.2f}"
                else:
                    value_str = f"{value:.2f}"
                if when is not None:
                    dates.append(when)
                # An unresolvable index is framed twice: the whole depth row in the
                # colour of the class it lies beyond (dark red at the dry bound, dark
                # blue at the wet one) plus the value itself in the text colour. The
                # pale halo keeps the row frame visible on the darkest band colours.
                if censor:
                    value_style = "border:2px dashed currentColor;border-radius:6px;padding:0 6px;"
                    row_frame = (
                        f"border:3px dashed {CENSOR_FRAME_COLORS[censor]};"
                        "box-shadow:0 0 0 2px rgba(255,255,255,0.65);"
                    )
                else:
                    value_style = "border:2px solid transparent;padding:0 6px;"
                    row_frame = "border:2px solid transparent;"
                hint = (
                    " title='Index nicht auflösbar: Bodenfeuchte am Rand der "
                    "empirischen Verteilung'"
                    if censor
                    else f" title='{band_label}'"
                )
                depth_rows.append(
                    f'<div{hint} style="background:{color};color:{text_color};'
                    f"display:flex;align-items:center;justify-content:space-between;"
                    f'gap:8px;border-radius:7px;padding:5px 8px;margin:3px 0;{row_frame}">'
                    f'<span style="font-size:0.78rem;">{label}</span>'
                    f'<span style="font-size:1.05rem;font-weight:700;{value_style}">'
                    f"{value_str}</span></div>"
                )
            date_str = max(dates).date().isoformat() if dates else "keine Daten"
            cols[j].markdown(
                f"""
<div style="border:1px solid rgba(0,0,0,0.12);border-radius:10px;margin:4px 0;
            padding:8px;line-height:1.25;">
  <div style="font-weight:700;font-size:0.95rem;text-align:center;margin-bottom:4px;">
    {station_label(station, locs)}</div>
  {"".join(depth_rows)}
  <div style="font-size:0.68rem;opacity:0.7;text-align:center;margin-top:4px;">
    Stand {date_str}</div>
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
        "margin-right:10px;flex:0 0 auto;border:3px dashed "
        f'{CENSOR_FRAME_COLORS["low"]};"></span>'
        '<span style="font-size:0.92rem;line-height:1.25;">'
        "<b>Index nicht auflösbar</b><br>"
        '<span style="opacity:0.7;">Bodenfeuchte auf oder jenseits der untersten bzw. '
        "obersten Stufe der empirischen Verteilung; der Wert ist nur eine "
        "Ober- (≤) bzw. Untergrenze (≥). Dunkelroter Rahmen: trockener als jeder Wert "
        "des Referenzzeitraums. Dunkelblauer Rahmen: nasser als jeder Wert des "
        "Referenzzeitraums.</span></span></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Jede Kachel enthält eine Zeile je Tiefe; die Farbe zeigt die Klasse dieser "
        "Tiefe. Ordinale Skala zwischen 0 (sehr trocken) und 1 (sehr nass). Dürreklassen "
        "nach der [Dürreklassifizierung des UFZ](https://www.ufz.de/index.php?de=37937), "
        "Nässeklassen an denselben Schwellen gespiegelt. Der Bereich zwischen 0,30 und "
        "0,70 gilt als „normal“."
    )

st.divider()

# --- Time series with drought bands ------------------------------------------
st.subheader("Zeitlicher Verlauf")

# Stations picked on the overview page seed this selection once.
default_sel = [s for s in get_shared_stations([]) if s in available] or available[:3]
sel_stations = st.multiselect(
    "Standorte",
    options=available,
    default=default_sel,
    format_func=station_labeller(locs),
)

DEFAULT_HORIZON = "Letzte 14 Tage"
horizon_map = {
    FULL_RANGE_LABEL: None,
    "Letzte 7 Tage": 7,
    DEFAULT_HORIZON: 14,
    "Letzte 3 Monate": 90,
    "1 Jahr": 365,
    "3 Jahre": 3 * 365,
    # "5 Jahre": 5 * 365,
    "10 Jahre": 10 * 365,
    # "30 Jahre": 30 * 365,
}
control_cols = st.columns([1.6, 2.4, 2])
with control_cols[0]:
    depth_label = st.segmented_control(
        "Tiefe",
        options=depth_labels,
        default=status_depth,
        selection_mode="single",
    )
    depth_label = depth_label if depth_label in smi_by_depth else status_depth
    depth_key = SMI_DEPTHS[depth_label]
    smi = smi_by_depth[depth_label]
with control_cols[1]:
    horizon = st.pills(
        "Zeithorizont",
        options=list(horizon_map.keys()),
        default=DEFAULT_HORIZON,
        selection_mode="single",
        key="smi_horizon",
    )
with control_cols[2]:
    # Only the depth the index itself is derived from can be overlaid.
    swap_label = SMI_SWAP_DEPTH[depth_key]
    show_swap = st.checkbox(
        f"Bodenfeuchte aus dem Modell SWAP ({swap_label}) überlagern",
        value=False,
    )

if not sel_stations:
    st.info("Wähle mindestens einen Standort für den Verlauf.")
    st.stop()

data_min = selected_min_date(smi, sel_stations)
data_max = selected_max_date(smi, sel_stations)


def _sync_smi_dates():
    # Typing a start/end date means "own period": no horizon pill stays selected.
    st.session_state.smi_horizon = None


# Deselecting the pill leaves None: that is the own period set below.
if horizon in horizon_map:
    horizon_days = horizon_map[horizon]
    if horizon_days is None:
        default_start, default_end = data_min, data_max
    else:
        default_start = max(
            data_min, (pd.Timestamp(data_max) - timedelta(days=horizon_days)).date()
        )
        default_end = data_max
    st.session_state.smi_start = default_start
    st.session_state.smi_end = default_end
else:
    st.session_state.setdefault("smi_start", data_min)
    st.session_state.setdefault("smi_end", data_max)

# Keep the dates valid when the station selection changes the available range.
st.session_state.smi_start = min(max(st.session_state.smi_start, data_min), data_max)
st.session_state.smi_end = min(max(st.session_state.smi_end, data_min), data_max)

date_cols = st.columns([1, 1, 4])
date_cols[0].date_input(
    "Start",
    min_value=data_min,
    max_value=data_max,
    key="smi_start",
    on_change=_sync_smi_dates,
)
date_cols[1].date_input(
    "Ende",
    min_value=data_min,
    max_value=data_max,
    key="smi_end",
    on_change=_sync_smi_dates,
)
if horizon not in horizon_map:
    date_cols[2].caption("Eigener Zeitraum – über Start und Ende gesetzt.")

if st.session_state.smi_start > st.session_state.smi_end:
    st.error("Das Startdatum muss vor dem Enddatum liegen.")
    st.stop()

start = pd.Timestamp(st.session_state.smi_start)
end = pd.Timestamp(st.session_state.smi_end)

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
            name=station_label(station, locs),
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
        st.warning(f"Modellwerte SWAP ({swap_label}) sind derzeit nicht verfügbar.")
    for station in sel_stations:
        if station not in swap_sm.columns:
            continue
        series = swap_sm.loc[start:end, station]
        if series.dropna().empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=to_plot_unit(series),
                mode="lines",
                name=f"{station_label(station, locs)} · Modell SWAP {swap_label}",
                legendgroup=station,
                line=dict(color=STATION_COLORS.get(station, "#444444"), dash="dot"),
                opacity=0.8,
            ),
            secondary_y=True,
        )

fig.update_yaxes(
    title_text=f"Bodenfeuchteindex {depth_label} (0–1)", range=[0, 1], secondary_y=False
)
if has_secondary:
    fig.update_yaxes(title_text=moisture_label("Modell SWAP"), secondary_y=True)
fig.update_layout(
    legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
    margin=dict(l=40, r=20, t=20, b=80),
    height=480,
)

st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

glossary_expander()
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
