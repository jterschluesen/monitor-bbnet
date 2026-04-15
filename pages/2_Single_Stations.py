# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Single Stations",
    page_icon=":material/monitoring:",
    layout="wide",
)

st.title("Single Stations")
st.write(
    "Detaillierte Darstellung je Standort mit frei waehlbaren Variablen und Zeitraum."
)

STOCKS = [
    "OEH",
    "LIN",
    "MQ",
    "PAU",
    "BOO",
    "DED",
    "KH",
    "GOL",
    "TRE",
    "DUB",
    "FUE",
]


def load_data(url):
    df = pd.read_csv(url, sep="\t", na_values="na")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(None)
    df = df.set_index("datetime")
    df.index.name = "Date"
    df = df.rename(columns={"QUI": "DED", "MQ35": "MQ"})
    if "WUS" in df.columns:
        df = df.drop(columns=["WUS"])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


crns_full = load_data(
    "https://b2drop.eudat.eu/public.php/dav/files/efStHSPAM8HLc92/products/swc-from-crns.txt"
)
swap_full = load_data(
    "https://b2drop.eudat.eu/public.php/dav/files/efStHSPAM8HLc92/products/swc-from-swap.txt"
)
d86_full = load_data(
    "https://b2drop.eudat.eu/public.php/dav/files/efStHSPAM8HLc92/products/d86-from-crns.txt"
)

available_stations = [station for station in STOCKS if station in crns_full.columns]
selected_stations = available_stations

selected_metrics = st.pills(
    "Anzuzeigende Variablen",
    options=["SWC(CRNS)", "SWC(SWAP)", "D86"],
    default=["SWC(CRNS)", "SWC(SWAP)", "D86"],
    selection_mode="multi",
)

if not selected_metrics:
    st.info("Waehle mindestens eine Variable.")
    st.stop()

crns = crns_full[selected_stations]
swap = swap_full[selected_stations]
d86 = d86_full[selected_stations]

NUM_COLS = 2
cols = st.columns(NUM_COLS)

for i, station in enumerate(selected_stations):
    has_d86 = "D86" in selected_metrics
    fig = make_subplots(specs=[[{"secondary_y": has_d86}]])

    if "D86" in selected_metrics:
        fig.add_trace(
            go.Scatter(
                x=d86.index,
                y=-d86[station],
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
            go.Scatter(x=swap.index, y=swap[station], mode="lines", name="SWC(SWAP)"),
            secondary_y=False,
        )

    if "SWC(CRNS)" in selected_metrics:
        fig.add_trace(
            go.Scatter(x=crns.index, y=crns[station], mode="lines", name="SWC(CRNS)"),
            secondary_y=False,
        )

    fig.update_yaxes(title_text="SWC (m³/m³)", secondary_y=False)
    if "D86" in selected_metrics:
        fig.update_yaxes(title_text="D86 (cm)", range=[-120, -0], secondary_y=True)

    fig.update_layout(
        title=station,
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
