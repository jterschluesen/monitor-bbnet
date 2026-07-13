# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_sources import (
    STOCKS,
    SWAP_SM_DEPTHS,
    construction_warning,
    URL_D86_CRNS,
    URL_LOCATIONS,
    URL_SWC_CRNS,
    URL_SWC_CRNS_old,
    URL_SWC_SWAP,
    URL_SWC_SMT,
    URL_SWC_NEPTOON_DES,
    URL_SWC_NEPTOON_UTS,
    URL_SNOW_FLAGS,
    add_calibration_marker,
    add_snow_shading,
    load_locations,
    load_snow_flags,
    load_time_series,
    snow_periods,
)

st.set_page_config(
    page_title="Einzelne Standorte",
    page_icon=":material/monitoring:",
    layout="wide",
)

construction_warning()

st.title("Messreihen einzelner Standorte")
st.write(
    "Detaillierte Darstellung je Standort mit frei wählbaren Variablen und Zeitraum. "
    "Dargestellte Daten beruhen auf Neutronenmessungen (CRNS), Bodenfeuchtemessungen (SMTs) und Modellsimulationen (SWAP). "
    "Die Eindringtiefe des CRNS hängt u.a. von der Bodenfeuchte selbst ab und ist daher dynamisch. Zur besseren Vergleichbarkeit mit dem CRNS-Signal sind die SWAP-Simulationsergebnisse ebenfalls entsprechend der Eindringtiefe des CRNS als tiefengewichteter Mittelwert dargestellt."
)

# All hues are from the Okabe-Ito colour-vision-deficiency-safe palette.
COLOR_CRNS = "#E69F00"  # orange
COLOR_CRNS_old = "#CC79A7"  # reddish purple
COLOR_SWAP = "#D55E00"  # vermillion
COLOR_NEPTOON_DES = "#56B4E9"  # sky blue
COLOR_NEPTOON_UTS = "#0072B2"  # blue
COLOR_D86 = "#009E73"  # bluish green - kept distinct from the SWC blues
SMT_GRAY_SCALE = ["#1F1F1F", "#4D4D4D", "#737373", "#A6A6A6", "#D0D0D0"]
# Purple ramp (light = shallow, dark = deep) for the fixed-depth SWAP means; kept
# off the orange/blue/green hues so they read as their own family.
SWAP_DEPTH_COLORS = {"0–30 cm": "#9E9AC8", "0–1 m": "#6A51A3", "0–2 m": "#3F007D"}
TRACE_ALPHA = 0.8

# The SWAP runs reach back to 1990, the CRNS record starts in 2021. Clip the model
# series so the long simulation history does not stretch the station plots.
SWAP_START = pd.Timestamp("2024-01-01")

# One metric per fixed SWAP depth mean, next to the CRNS-depth-weighted SWC(SWAP).
SWAP_DEPTH_METRICS = {f"SWC(SWAP {depth})": depth for depth in SWAP_SM_DEPTHS}

# Internal metric key -> readable label (legend + selector). Grouped by source.
METRIC_LABELS = {
    "SWC(CRNS)": "SWC (CRNS, general)",
    "SWC(CRNS_old)": "SWC (CRNS, general, alt)",
    "SWC(NEPTOON_DES)": "SWC (CRNS, Desilet)",
    "SWC(NEPTOON_UTS)": "SWC (CRNS, UTS)",
    "D86": "D86 (CRNS)",
    "SWC(SWAP)": "SWC (SWAP, weighted)",
    "SWC(SMT)": "SWC (SMT)",
    **{metric: f"SWC (SWAP, {depth})" for metric, depth in SWAP_DEPTH_METRICS.items()},
}

CRNS_METRICS = [
    "SWC(CRNS)",
    # "SWC(CRNS_old)",
    "SWC(NEPTOON_DES)",
    "SWC(NEPTOON_UTS)",
    "D86",
]
MODEL_METRICS = ["SWC(SWAP)"] + list(SWAP_DEPTH_METRICS)
OTHER_METRICS = ["SWC(SMT)"]


def _depth_sort_key(depth_label: str):
    number = "".join(ch for ch in depth_label if ch.isdigit())
    if number:
        return (0, int(number), depth_label)
    return (1, 0, depth_label)


def _smt_color_map(depths):
    if not depths:
        return {}
    if len(depths) == 1:
        return {depths[0]: SMT_GRAY_SCALE[2]}
    mapping = {}
    max_idx = len(depths) - 1
    for idx, depth in enumerate(depths):
        scale_idx = round(idx * (len(SMT_GRAY_SCALE) - 1) / max_idx)
        mapping[depth] = SMT_GRAY_SCALE[scale_idx]
    return mapping


def _station_series(df: pd.DataFrame, station: str, start=None, end=None):
    # Some stations are absent from some sources (e.g. WUS has no SWAP run).
    if station not in df.columns:
        return None
    series = df[station]
    if start is not None:
        series = series.loc[start:end]
    return series


def rename_smt_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        if col.startswith("MQ35_"):
            renamed[col] = "MQ_" + col[len("MQ35_") :]
        elif col.startswith("QUI_"):
            renamed[col] = "DED_" + col[len("QUI_") :]
    return df.rename(columns=renamed)


crns_full = load_time_series(URL_SWC_CRNS)
crns_full_old = load_time_series(URL_SWC_CRNS_old)
swap_full = load_time_series(URL_SWC_SWAP).loc[SWAP_START:]
d86_full = load_time_series(URL_D86_CRNS)
locs = load_locations(URL_LOCATIONS)
neptoon_des_full = load_time_series(URL_SWC_NEPTOON_DES)
neptoon_uts_full = load_time_series(URL_SWC_NEPTOON_UTS)
SMT = load_time_series(URL_SWC_SMT)
SMT = rename_smt_columns(SMT)
snow_flags = load_snow_flags(URL_SNOW_FLAGS)
snow_phase_periods = snow_periods(snow_flags)

smt_depths = sorted(
    {col.split("_SMT_", 1)[1] for col in SMT.columns if "_SMT_" in col},
    key=_depth_sort_key,
)

available_stations = [station for station in STOCKS if station in crns_full.columns]
selected_stations = available_stations

station_name_map = {}
for station in selected_stations:
    name = None
    if station in locs.index and "name" in locs.columns:
        value = locs.loc[station, "name"]
        if isinstance(value, str) and value.strip():
            name = value.strip()
    station_name_map[station] = name or station

with st.expander("Datenauswahl", expanded=True):
    col_crns, col_model, col_other = st.columns(3)
    with col_crns:
        st.markdown("**CRNS-basiert**")
        crns_sel = st.pills(
            "CRNS-basiert",
            options=CRNS_METRICS,
            format_func=lambda m: METRIC_LABELS[m],
            default=["SWC(CRNS)", "SWC(NEPTOON_UTS)", "D86"],
            selection_mode="multi",
            label_visibility="collapsed",
            key="metrics_crns",
        )
    with col_model:
        st.markdown("**Modellbasiert**")
        model_sel = st.pills(
            "Modellbasiert",
            options=MODEL_METRICS,
            format_func=lambda m: METRIC_LABELS[m],
            default=["SWC(SWAP)"],
            selection_mode="multi",
            label_visibility="collapsed",
            key="metrics_model",
        )
    with col_other:
        st.markdown("**Weitere**")
        other_sel = st.pills(
            "Weitere",
            options=OTHER_METRICS,
            format_func=lambda m: METRIC_LABELS[m],
            default=[],
            selection_mode="multi",
            label_visibility="collapsed",
            key="metrics_other",
        )
    selected_metrics = list(crns_sel) + list(model_sel) + list(other_sel)

    selected_smt_depths = []
    if "SWC(SMT)" in selected_metrics and smt_depths:
        # Default to the depth-weighted SMT series; individual depths stay selectable.
        default_smt_depths = ["weighted"] if "weighted" in smt_depths else smt_depths
        selected_smt_depths = st.multiselect(
            "SMT Tiefen",
            options=smt_depths,
            default=default_smt_depths,
            placeholder="Wähle SMT-Tiefen",
        )

if not selected_metrics:
    st.info("Wähle mindestens eine Variable.")
    st.stop()

if "SWC(SMT)" in selected_metrics:
    if not smt_depths:
        st.warning("Keine SMT-Tiefen in den Daten gefunden.")
        st.stop()
    if not selected_smt_depths:
        st.info("Wähle mindestens eine SMT-Tiefe.")
        st.stop()

smt_color_map = _smt_color_map(selected_smt_depths)

# Fixed-depth SWAP means are fetched on demand; a missing file only drops its trace.
swap_depth_frames = {}
for metric, depth in SWAP_DEPTH_METRICS.items():
    if metric not in selected_metrics:
        continue
    try:
        swap_depth_frames[metric] = load_time_series(SWAP_SM_DEPTHS[depth]).loc[
            SWAP_START:
        ]
    except Exception:
        st.warning(f"SWAP-Bodenfeuchte ({depth}) nicht verfügbar.")

metric_frames = {}
# reindex (not direct selection) so stations missing from a source - e.g. WUS,
# which has no SWAP run - yield NaN columns instead of a KeyError.
if "SWC(CRNS)" in selected_metrics:
    metric_frames["SWC(CRNS)"] = crns_full.reindex(columns=selected_stations)
if "SWC(CRNS_old)" in selected_metrics:
    metric_frames["SWC(CRNS_old)"] = crns_full_old.reindex(columns=selected_stations)
if "SWC(SWAP)" in selected_metrics:
    metric_frames["SWC(SWAP)"] = swap_full.reindex(columns=selected_stations)
if "D86" in selected_metrics:
    metric_frames["D86"] = d86_full.reindex(columns=selected_stations)
if "SWC(SMT)" in selected_metrics:
    smt_cols = [
        f"{station}_SMT_{depth}"
        for station in selected_stations
        for depth in selected_smt_depths
        if f"{station}_SMT_{depth}" in SMT.columns
    ]
    if smt_cols:
        metric_frames["SWC(SMT)"] = SMT[smt_cols]
if "SWC(NEPTOON_DES)" in selected_metrics:
    metric_frames["SWC(NEPTOON_DES)"] = neptoon_des_full.reindex(
        columns=selected_stations
    )
if "SWC(NEPTOON_UTS)" in selected_metrics:
    metric_frames["SWC(NEPTOON_UTS)"] = neptoon_uts_full.reindex(
        columns=selected_stations
    )
for metric, frame in swap_depth_frames.items():
    metric_frames[metric] = frame.reindex(columns=selected_stations)

if not metric_frames:
    st.warning("Keine Daten fuer die aktuelle Variablenauswahl gefunden.")
    st.stop()


combined_for_range = pd.concat(list(metric_frames.values()), axis=1)
if combined_for_range.dropna(how="all").empty:
    st.warning("Keine Daten fuer die aktuelle Variablenauswahl gefunden.")
    st.stop()

st.caption("Zeithorizont: pro Standort Maximum der gewaehlten Variablen.")

NUM_COLS = 2
cols = st.columns(NUM_COLS)

for i, station in enumerate(selected_stations):
    # skip WUS
    if station == "WUS":
        continue
    has_d86 = "D86" in selected_metrics
    fig = make_subplots(specs=[[{"secondary_y": has_d86}]])

    station_frames = []
    if "SWC(CRNS)" in selected_metrics and station in crns_full.columns:
        station_frames.append(crns_full[[station]])
    if "SWC(CRNS_old)" in selected_metrics and station in crns_full_old.columns:
        station_frames.append(crns_full_old[[station]])
    if "SWC(SWAP)" in selected_metrics and station in swap_full.columns:
        station_frames.append(swap_full[[station]])
    if "D86" in selected_metrics and station in d86_full.columns:
        station_frames.append(d86_full[[station]])
    smt_station_cols = []
    if "SWC(SMT)" in selected_metrics:
        smt_station_cols = [
            f"{station}_SMT_{depth}"
            for depth in selected_smt_depths
            if f"{station}_SMT_{depth}" in SMT.columns
        ]
        if smt_station_cols:
            station_frames.append(SMT[smt_station_cols])
    if "SWC(NEPTOON_DES)" in selected_metrics and station in neptoon_des_full.columns:
        station_frames.append(neptoon_des_full[[station]])
    if "SWC(NEPTOON_UTS)" in selected_metrics and station in neptoon_uts_full.columns:
        station_frames.append(neptoon_uts_full[[station]])
    for frame in swap_depth_frames.values():
        if station in frame.columns:
            station_frames.append(frame[[station]])

    if not station_frames:
        continue

    station_combined = pd.concat(station_frames, axis=1)
    station_valid = station_combined.dropna(how="all")
    if station_valid.empty:
        continue

    station_start = station_valid.index.min()
    station_end = station_valid.index.max()

    station_crns = _station_series(crns_full, station, station_start, station_end)
    station_crns_old = _station_series(
        crns_full_old, station, station_start, station_end
    )
    station_swap = _station_series(swap_full, station, station_start, station_end)
    station_d86 = _station_series(d86_full, station, station_start, station_end)
    station_neptoon_des = _station_series(
        neptoon_des_full, station, station_start, station_end
    )
    station_neptoon_uts = _station_series(
        neptoon_uts_full, station, station_start, station_end
    )
    station_smt = (
        SMT.loc[station_start:station_end, smt_station_cols]
        if smt_station_cols
        else pd.DataFrame(index=station_valid.index)
    )

    if "D86" in selected_metrics and station_d86 is not None:
        fig.add_trace(
            go.Scatter(
                x=station_d86.index,
                y=-station_d86,
                mode="lines",
                name=METRIC_LABELS["D86"],
                fillcolor="rgba(0, 158, 115, 0.3)",
                line=dict(color=COLOR_D86, width=0),
                fill="tozeroy",
                opacity=TRACE_ALPHA,
            ),
            secondary_y=True,
        )

    if "SWC(SWAP)" in selected_metrics and station_swap is not None:
        fig.add_trace(
            go.Scatter(
                x=station_swap.index,
                y=station_swap,
                mode="lines",
                name=METRIC_LABELS["SWC(SWAP)"],
                line=dict(color=COLOR_SWAP),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    for metric, frame in swap_depth_frames.items():
        depth_series = _station_series(frame, station, station_start, station_end)
        if depth_series is None or depth_series.dropna().empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=depth_series.index,
                y=depth_series,
                mode="lines",
                name=METRIC_LABELS[metric],
                line=dict(
                    color=SWAP_DEPTH_COLORS.get(SWAP_DEPTH_METRICS[metric], "#6A51A3"),
                    dash="dash",
                ),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    if "SWC(CRNS)" in selected_metrics and station_crns is not None:
        fig.add_trace(
            go.Scatter(
                x=station_crns.index,
                y=station_crns,
                mode="lines",
                name=METRIC_LABELS["SWC(CRNS)"],
                line=dict(color=COLOR_CRNS),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    if "SWC(CRNS_old)" in selected_metrics and station_crns_old is not None:
        fig.add_trace(
            go.Scatter(
                x=station_crns_old.index,
                y=station_crns_old,
                mode="lines",
                name=METRIC_LABELS["SWC(CRNS_old)"],
                line=dict(color=COLOR_CRNS_old, dash="dash"),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    if "SWC(NEPTOON_DES)" in selected_metrics and station_neptoon_des is not None:
        fig.add_trace(
            go.Scatter(
                x=station_neptoon_des.index,
                y=station_neptoon_des,
                mode="lines",
                name=METRIC_LABELS["SWC(NEPTOON_DES)"],
                line=dict(color=COLOR_NEPTOON_DES),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )
    if "SWC(NEPTOON_UTS)" in selected_metrics and station_neptoon_uts is not None:
        fig.add_trace(
            go.Scatter(
                x=station_neptoon_uts.index,
                y=station_neptoon_uts,
                mode="lines",
                name=METRIC_LABELS["SWC(NEPTOON_UTS)"],
                line=dict(color=COLOR_NEPTOON_UTS),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    if "SWC(SMT)" in selected_metrics and not station_smt.empty:
        for smt_col in smt_station_cols:
            depth = smt_col.split("_SMT_", 1)[1]
            fig.add_trace(
                go.Scatter(
                    x=station_smt.index,
                    y=station_smt[smt_col],
                    mode="lines",
                    name=f"SWC (SMT {depth})",
                    line=dict(color=smt_color_map.get(depth, "#737373"), dash="dot"),
                    opacity=TRACE_ALPHA,
                ),
                secondary_y=False,
            )

    fig.update_yaxes(title_text="SWC (m³/m³)", secondary_y=False)
    if "D86" in selected_metrics:
        fig.update_yaxes(title_text="D86 (cm)", range=[-120, -0], secondary_y=True)

    fig.update_layout(
        title=(
            f"{station_name_map[station]} ({station})<br>"
            f"<sup>{station_start.date()} bis {station_end.date()}</sup>"
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=40, r=20, t=50, b=90),
    )

    add_snow_shading(fig, snow_phase_periods, xrange=(station_start, station_end))
    if station in locs.index:
        caldate = locs.loc[station, "caldate"] if "caldate" in locs.columns else None
        theta = locs.loc[station, "theta_eff"] if "theta_eff" in locs.columns else None
        # Snap onto the CRNS sample grid so the point aligns with the CRNS trace.
        cal_index = (
            station_crns.index if station_crns is not None else station_valid.index
        )
        add_calibration_marker(
            fig,
            caldate,
            theta,
            crns_index=cal_index,
            xrange=(station_start, station_end),
            secondary_y=False,
        )

    cell = cols[i % NUM_COLS].container(border=True)
    cell.plotly_chart(fig, width="stretch", key=f"station_{station}")
