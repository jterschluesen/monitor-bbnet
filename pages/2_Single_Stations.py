# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_sources import (
    STOCKS,
    URL_D86_CRNS,
    URL_LOCATIONS,
    URL_SWC_CRNS,
    URL_SWC_SWAP,
    URL_SWC_SMT,
    URL_SWC_NEPTOON_DES,
    URL_SWC_NEPTOON_UTS,
    load_locations,
    load_time_series,
)

st.set_page_config(
    page_title="Single Stations",
    page_icon=":material/monitoring:",
    layout="wide",
)

st.title("Single Stations")
st.write(
    "Detaillierte Darstellung je Standort mit frei wählbaren Variablen und Zeitraum."
)

COLOR_CRNS = "#E69F00"
COLOR_SWAP = "#D55E00"
COLOR_NEPTOON_DES = "#56B4E9"
COLOR_NEPTOON_UTS = "#0072B2"
SMT_GRAY_SCALE = ["#1F1F1F", "#4D4D4D", "#737373", "#A6A6A6", "#D0D0D0"]
TRACE_ALPHA = 0.8


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


def rename_smt_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        if col.startswith("MQ35_"):
            renamed[col] = "MQ_" + col[len("MQ35_") :]
        elif col.startswith("QUI_"):
            renamed[col] = "DED_" + col[len("QUI_") :]
    return df.rename(columns=renamed)


crns_full = load_time_series(URL_SWC_CRNS)
swap_full = load_time_series(URL_SWC_SWAP)
d86_full = load_time_series(URL_D86_CRNS)
locs = load_locations(URL_LOCATIONS)
neptoon_des_full = load_time_series(URL_SWC_NEPTOON_DES)
neptoon_uts_full = load_time_series(URL_SWC_NEPTOON_UTS)
SMT = load_time_series(URL_SWC_SMT)
SMT = rename_smt_columns(SMT)

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

selected_metrics = st.pills(
    "Anzuzeigende Messgrößen",
    options=[
        "SWC(CRNS)",
        "SWC(SWAP)",
        "D86",
        "SWC(SMT)",
        "SWC(NEPTOON_DES)",
        "SWC(NEPTOON_UTS)",
    ],
    # options=["SWC(CRNS)", "SWC(SWAP)", "D86"],
    default=["SWC(CRNS)", "SWC(SWAP)", "D86"],
    selection_mode="multi",
)

if not selected_metrics:
    st.info("Wähle mindestens eine Variable.")
    st.stop()

selected_smt_depths = []
if "SWC(SMT)" in selected_metrics:
    if not smt_depths:
        st.warning("Keine SMT-Tiefen in den Daten gefunden.")
        st.stop()
    selected_smt_depths = st.multiselect(
        "SMT Tiefen",
        options=smt_depths,
        default=smt_depths,
        placeholder="Wähle SMT-Tiefen",
    )
    if not selected_smt_depths:
        st.info("Wähle mindestens eine SMT-Tiefe.")
        st.stop()

smt_color_map = _smt_color_map(selected_smt_depths)

metric_frames = {}
if "SWC(CRNS)" in selected_metrics:
    metric_frames["SWC(CRNS)"] = crns_full[selected_stations]
if "SWC(SWAP)" in selected_metrics:
    metric_frames["SWC(SWAP)"] = swap_full[selected_stations]
if "D86" in selected_metrics:
    metric_frames["D86"] = d86_full[selected_stations]
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
    metric_frames["SWC(NEPTOON_DES)"] = neptoon_des_full[selected_stations]
if "SWC(NEPTOON_UTS)" in selected_metrics:
    metric_frames["SWC(NEPTOON_UTS)"] = neptoon_uts_full[selected_stations]


combined_for_range = pd.concat(list(metric_frames.values()), axis=1)
if combined_for_range.dropna(how="all").empty:
    st.warning("Keine Daten fuer die aktuelle Variablenauswahl gefunden.")
    st.stop()

st.caption("Zeithorizont: pro Standort Maximum der gewaehlten Variablen.")

NUM_COLS = 2
cols = st.columns(NUM_COLS)

for i, station in enumerate(selected_stations):
    has_d86 = "D86" in selected_metrics
    fig = make_subplots(specs=[[{"secondary_y": has_d86}]])

    station_frames = []
    if "SWC(CRNS)" in selected_metrics:
        station_frames.append(crns_full[[station]])
    if "SWC(SWAP)" in selected_metrics:
        station_frames.append(swap_full[[station]])
    if "D86" in selected_metrics:
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
    if "SWC(NEPTOON_DES)" in selected_metrics:
        station_frames.append(neptoon_des_full[[station]])
    if "SWC(NEPTOON_UTS)" in selected_metrics:
        station_frames.append(neptoon_uts_full[[station]])

    station_combined = pd.concat(station_frames, axis=1)
    station_valid = station_combined.dropna(how="all")
    if station_valid.empty:
        continue

    station_start = station_valid.index.min()
    station_end = station_valid.index.max()

    station_crns = crns_full.loc[station_start:station_end, station]
    station_swap = swap_full.loc[station_start:station_end, station]
    station_d86 = d86_full.loc[station_start:station_end, station]
    station_neptoon_des = neptoon_des_full.loc[station_start:station_end, station]
    station_neptoon_uts = neptoon_uts_full.loc[station_start:station_end, station]
    station_smt = (
        SMT.loc[station_start:station_end, smt_station_cols]
        if smt_station_cols
        else pd.DataFrame(index=station_crns.index)
    )

    if "D86" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_d86.index,
                y=-station_d86,
                mode="lines",
                name="D86",
                fillcolor="rgba(0, 150, 200, 0.3)",
                line=dict(color="rgb(0,150,200)", width=0),
                fill="tozeroy",
                opacity=TRACE_ALPHA,
            ),
            secondary_y=True,
        )

    if "SWC(SWAP)" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_swap.index,
                y=station_swap,
                mode="lines",
                name="SWC (SWAP)",
                line=dict(color=COLOR_SWAP),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    if "SWC(CRNS)" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_crns.index,
                y=station_crns,
                mode="lines",
                name="SWC (CRNS)",
                line=dict(color=COLOR_CRNS),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )

    if "SWC(NEPTOON_DES)" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_neptoon_des.index,
                y=station_neptoon_des,
                mode="lines",
                name="SWC (NEPTOON_DES)",
                line=dict(color=COLOR_NEPTOON_DES),
                opacity=TRACE_ALPHA,
            ),
            secondary_y=False,
        )
    if "SWC(NEPTOON_UTS)" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_neptoon_uts.index,
                y=station_neptoon_uts,
                mode="lines",
                name="SWC (NEPTOON_UTS)",
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

    cell = cols[i % NUM_COLS].container(border=True)
    cell.plotly_chart(fig, width="stretch", key=f"station_{station}")
