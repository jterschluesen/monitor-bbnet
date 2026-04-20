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
    "Detaillierte Darstellung je Standort mit frei waehlbaren Variablen und Zeitraum."
)


def _depth_sort_key(depth_label: str):
    number = "".join(ch for ch in depth_label if ch.isdigit())
    if number:
        return (0, int(number), depth_label)
    return (1, 0, depth_label)


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
    "Anzuzeigende Variablen",
    # options=["SWC(CRNS)", "SWC(SWAP)", "D86", "SWC(SMT)"],
    options=["SWC(CRNS)", "SWC(SWAP)", "D86"],
    default=["SWC(CRNS)", "SWC(SWAP)", "D86"],
    selection_mode="multi",
)

if not selected_metrics:
    st.info("Waehle mindestens eine Variable.")
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
        st.info("Waehle mindestens eine SMT-Tiefe.")
        st.stop()

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

    station_combined = pd.concat(station_frames, axis=1)
    station_valid = station_combined.dropna(how="all")
    if station_valid.empty:
        continue

    station_start = station_valid.index.min()
    station_end = station_valid.index.max()

    station_crns = crns_full.loc[station_start:station_end, station]
    station_swap = swap_full.loc[station_start:station_end, station]
    station_d86 = d86_full.loc[station_start:station_end, station]
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
            ),
            secondary_y=True,
        )

    if "SWC(SWAP)" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_swap.index, y=station_swap, mode="lines", name="SWC(SWAP)"
            ),
            secondary_y=False,
        )

    if "SWC(CRNS)" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=station_crns.index, y=station_crns, mode="lines", name="SWC(CRNS)"
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
                    name=f"SWC(SMT {depth})",
                    line=dict(dash="dot"),
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
