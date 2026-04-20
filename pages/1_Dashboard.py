# -*- coding: utf-8 -*-
# Copyright 2024-2025 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import streamlit as st
import pandas as pd
from datetime import timedelta
import plotly.express as px
import plotly.graph_objects as go
from data_sources import (
    DEFAULT_STOCKS,
    STOCKS,
    URL_D86_CRNS,
    URL_LOCATIONS,
    URL_SWC_CRNS,
    URL_SWC_SWAP,
    load_locations,
    load_time_series,
    normalize_stocks,
    selected_max_date,
    selected_min_date,
)

st.set_page_config(
    page_title="Soil water viewer",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

"""
# :material/query_stats: Bodenwassermonitor Brandenburg

Die dargestellten Daten beruhen auf Neutronenmessungen und Modellsimulationen. 
Das Monitoringprogramm ist eine Forschungskooperation der Universität Potsdam, des
Helmholtz-Zentrums für Umweltforschung und des Landes Brandenburg.
"""

""  # Add some space.

top_row = st.columns([1, 2])


def stocks_to_str(stocks):
    return ",".join(stocks)


locs = load_locations(URL_LOCATIONS)
station_ids = [station for station in STOCKS if station in locs.index]


if "tickers_input" not in st.session_state:
    requested = st.query_params.get("stocks", stocks_to_str(DEFAULT_STOCKS)).split(",")
    st.session_state.tickers_input = normalize_stocks(requested) or DEFAULT_STOCKS


# Callback to update query param when input changes
def update_query_param():
    if st.session_state.tickers_input:
        st.query_params["stocks"] = stocks_to_str(st.session_state.tickers_input)
    else:
        st.query_params.pop("stocks", None)


def mark_main_horizon_custom():
    st.session_state.selected_horizon = "Custom"
    st.session_state.applied_horizon = "Custom"


def stations_from_map_points(points):
    selected = []
    for point in points:
        station = point.get("customdata")
        if isinstance(station, (list, tuple)):
            station = station[0] if station else None
        if isinstance(station, str):
            station = station.upper().strip()
            if station == "MQ35":
                station = "MQ"
            elif station == "QUI":
                station = "DED"

        if station not in STOCKS:
            point_index = point.get("pointIndex")
            if point_index is None:
                point_index = point.get("pointNumber")
            if point_index is None:
                point_index = point.get("point_index")
            if isinstance(point_index, int) and 0 <= point_index < len(station_ids):
                station = station_ids[point_index]

        if station in STOCKS and station not in selected:
            selected.append(station)

    return selected


def sync_stocks_from_map_selection():
    map_state = st.session_state.get("stations_map", {})
    selection = map_state.get("selection", {}) if isinstance(map_state, dict) else {}
    if not isinstance(selection, dict) or "points" not in selection:
        return

    points = selection.get("points") or []
    # Ignore non-map-triggered reruns where Streamlit reports an empty selection.
    # This prevents timeframe/date widget changes from clearing current stations.
    if not points:
        return

    selected = stations_from_map_points(points)

    # Single-point click toggles; box/lasso replaces selection.
    if len(points) == 1 and len(selected) == 1:
        clicked = selected[0]
        current = normalize_stocks(st.session_state.get("tickers_input", []))
        if clicked in current:
            next_selection = [station for station in current if station != clicked]
        else:
            next_selection = current + [clicked]
        next_selection = normalize_stocks(next_selection)
    else:
        next_selection = selected

    signature = tuple(next_selection)
    if st.session_state.get("map_selection_signature") == signature:
        return

    st.session_state.map_selection_signature = signature
    st.session_state.tickers_input = next_selection
    update_query_param()


sync_stocks_from_map_selection()


top_left_cell = top_row[0].container(
    border=True, height="stretch", vertical_alignment="center"
)

map_cell = top_row[1].container(
    border=True, height="stretch", vertical_alignment="center"
)

main_plot_cell = st.container(border=True)

with top_left_cell:
    st.markdown("### Datenauswahl")

    if "swc_source" not in st.session_state:
        st.session_state.swc_source = "CRNS"
    if "map_style" not in st.session_state:
        st.session_state.map_style = "OpenStreetMap"

    st.radio(
        "SWC fuer Zusammenfassungsplot",
        options=["CRNS", "SWAP"],
        key="swc_source",
        horizontal=True,
    )

    st.selectbox(
        "Hintergrundkarte",
        options=[
            "OpenStreetMap",
            "Carto Positron",
            "Carto Dark",
            "Google Satellite",
        ],
        key="map_style",
    )

    # Selectbox for stock tickers
    st.multiselect(
        "Standorte",
        options=STOCKS,
        key="tickers_input",
        placeholder="Wähle mindestens einen Standort",
        on_change=update_query_param,
    )

# Time horizon selector
horizon_map = {
    "Maximum": None,
    "1 Monat": 31,
    "3 Monate": 3 * 31,
    "6 Monate": 6 * 31,
    "1 Jahr": 365,
    "2 Jahre": 2 * 365,
    "3 Jahre": 3 * 365,
    "Custom": "custom",
}

tickers = normalize_stocks(st.session_state.tickers_input)
if tickers != st.session_state.tickers_input:
    st.session_state.tickers_input = tickers
    update_query_param()

if not tickers:
    top_left_cell.info("Wähle mindestens einen Standort.", icon=":material/info:")


# data = load_data(dtimes, STOCKS, rho=0.7, seed=42)
data2_full = load_time_series(URL_SWC_CRNS)
sim2_full = load_time_series(URL_SWC_SWAP)
d862_full = load_time_series(URL_D86_CRNS)
# https://b2drop.eudat.eu/s/yr5d6i72cCacYpH/swc-from-swap.txt


min_date = selected_min_date(data2_full, tickers)
max_date = selected_max_date(data2_full, tickers)
today_date = pd.Timestamp.today().date()

if "selected_horizon" not in st.session_state:
    st.session_state.selected_horizon = "Maximum"
if "applied_horizon" not in st.session_state:
    st.session_state.applied_horizon = st.session_state.selected_horizon
if "date_start" not in st.session_state:
    st.session_state.date_start = min_date
if "date_end" not in st.session_state:
    st.session_state.date_end = today_date

ticker_signature = tuple(tickers)
if "last_ticker_signature" not in st.session_state:
    st.session_state.last_ticker_signature = ticker_signature
if "last_selected_min_date" not in st.session_state:
    st.session_state.last_selected_min_date = min_date

# If a new station selection extends the available history, switch to Maximum range.
if ticker_signature != st.session_state.last_ticker_signature:
    previous_min_date = st.session_state.last_selected_min_date
    if min_date < previous_min_date:
        st.session_state.selected_horizon = "Maximum"
        st.session_state.applied_horizon = "Maximum"
        st.session_state.date_start = min_date
        st.session_state.date_end = today_date
    st.session_state.last_ticker_signature = ticker_signature

st.session_state.last_selected_min_date = min_date

with top_left_cell:
    # Reserve layout position so date pickers stay above the horizon selector.
    date_container = st.container()

    if st.session_state.selected_horizon not in horizon_map:
        st.session_state.selected_horizon = "Maximum"

    st.pills(
        "Zeithorizont",
        options=list(horizon_map.keys()),
        key="selected_horizon",
        selection_mode="single",
    )

    horizon = st.session_state.selected_horizon
    if horizon not in horizon_map:
        horizon = "Maximum"
        st.session_state.selected_horizon = horizon
    horizon_days = horizon_map[horizon]

    if horizon != st.session_state.applied_horizon:
        st.session_state.applied_horizon = horizon
        if horizon_days == "custom":
            pass
        elif horizon_days is None:
            st.session_state.date_start = min_date
            st.session_state.date_end = today_date
        else:
            st.session_state.date_end = today_date
            candidate_start = today_date - timedelta(days=horizon_days - 1)
            st.session_state.date_start = max(min_date, candidate_start)

    # Keep existing values valid when selected stations change available date range.
    if st.session_state.date_end > today_date:
        st.session_state.date_end = today_date
    if st.session_state.date_end < min_date:
        st.session_state.date_end = min_date
    if st.session_state.date_start > today_date:
        st.session_state.date_start = today_date
    if st.session_state.date_start < min_date:
        st.session_state.date_start = min_date

    with date_container:
        date_cols = st.columns(2)
        date_cols[0].date_input(
            "Start",
            min_value=min_date,
            max_value=today_date,
            key="date_start",
            on_change=mark_main_horizon_custom,
        )
        date_cols[1].date_input(
            "Ende",
            min_value=min_date,
            max_value=today_date,
            key="date_end",
            on_change=mark_main_horizon_custom,
        )

if st.session_state.date_start > st.session_state.date_end:
    st.error("Das Startdatum muss vor dem Enddatum liegen.")
    st.stop()

date_start = pd.to_datetime(st.session_state.date_start)
date_end = pd.to_datetime(st.session_state.date_end)

data2 = data2_full.loc[date_start:date_end]
sim2 = sim2_full.loc[date_start:date_end]
d862 = d862_full.loc[date_start:date_end]

if data2.empty:
    st.warning("Keine Daten im gewaelten Zeitraum gefunden.")
    st.stop()

data = data2[tickers]
sim = sim2[tickers]
d86 = d862[tickers]

summary_data = data if st.session_state.swc_source == "CRNS" else sim

locs = load_locations(URL_LOCATIONS)


# @st.cache_resource(show_spinner=False, ttl="6h")
# def load_data(tickers, period):
#    tickers_obj = yf.Tickers(tickers)
#    data = tickers_obj.history(period=period)
#    if data is None:
#        raise RuntimeError("YFinance returned no data.")
#    return data["Close"]

# Load the data
# try:
#    data = load_data(tickers, horizon_map[horizon])
# except yf.exceptions.YFRateLimitError as e:
#    st.warning("YFinance is rate-limiting us :(\nTry again later.")
#    load_data.clear()  # Remove the bad cache entry.
#    st.stop()

empty_columns = data.columns[data.isna().all()].tolist()

if empty_columns:
    st.error(f"Error loading data for the tickers: {', '.join(empty_columns)}.")
    st.stop()

mean_theta = data.mean()

# with bottom_left_cell:
#     cols = st.columns(2)
#     cols[0].metric(
#         "Mittelwert: "+mean_theta.idxmin(),
#         round(mean_theta.min(), 2),
#         delta=f"{round(mean_theta.min() * 100)}%",
#         width="content",
#     )
#     cols[1].metric(
#         "Mittelwert: "+mean_theta.idxmax(),
#         round(mean_theta.max(), 2),
#         delta=f"{round(mean_theta.max() * 100)}%",
#         width="content",
#     )

with map_cell:
    st.caption(
        "Klicke mehrere Punkte zum Hinzufuegen/Entfernen oder nutze Box/Lasso fuer Mehrfachauswahl."
    )

    station_ids = [station for station in STOCKS if station in locs.index]
    station_locs = locs.loc[station_ids]
    if (
        "manufacturer" not in station_locs.columns
        and "manufactur" in station_locs.columns
    ):
        station_locs["manufacturer"] = station_locs["manufactur"]
    elif (
        "manufacturer" in station_locs.columns and "manufactur" in station_locs.columns
    ):
        station_locs["manufacturer"] = station_locs["manufacturer"].fillna(
            station_locs["manufactur"]
        )

    hover_fields = [
        ("id", "ID"),
        ("name", "Name"),
        ("landuse", "Landnutzung"),
        ("manufacturer", "Hersteller"),
        # ("ka5_kurz", "KA5 kurz"),
        ("ka5_bez", "Bodenart KA5"),
        ("m1_wert", "kF (bis 1m)"),
        ("m2_wert", "kF (bis 2m)"),
        ("fk_1m_wert", "FK 1m"),
        ("nfk_1m_wer", "nFK 1m"),
        ("humus", "Humusgehalt"),
        ("biomass_eff", "Biomasse [kg/m²]"),
        ("bulk_density_eff", "Rohdichte [kg/m³]"),
        # ("theta_eff", "Theta"),
        # ("organic_matter_eff", "Organische Substanz"),
        # ("lattice_water_eff", "Gitterwasser"),
        # ("theta_total_eff_eff", "Theta gesamt"),
        ("gw_depth", "GW Tiefe [m]"),
    ]

    for col, _ in hover_fields:
        if col not in station_locs.columns:
            station_locs[col] = None

    station_attributes = [
        [station_locs.loc[sid, col] for col, _ in hover_fields] for sid in station_ids
    ]

    hover_lines = [
        f"{label}: %{{customdata[{idx}]}}"
        for idx, (_, label) in enumerate(hover_fields)
    ]
    hover_template = (
        "<b>%{text}</b><br>"
        + "<br>".join(hover_lines)
        + "<br>Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>"
    )

    selected_point_indices = [
        idx for idx, station in enumerate(station_ids) if station in tickers
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scattermapbox(
            lat=station_locs.lat,
            lon=station_locs.lon,
            mode="markers+text",
            marker=dict(
                size=12,
                color="#1D4ED8",
            ),
            text=station_ids,
            textposition="top center",
            customdata=station_attributes,
            selectedpoints=selected_point_indices,
            selected=dict(marker=dict(size=16, color="#DC2626", opacity=1)),
            unselected=dict(marker=dict(size=12, opacity=0.85)),
            hovertemplate=hover_template,
        )
    )

    fig.update_layout(showlegend=False)

    #
    #
    # go.Scattermapbox(
    #     lat=locs.lat,
    #     lon=locs.lon,
    #     mode="markers",
    #     marker=dict(
    #         size=12,
    #         color="royalblue",
    #         line=dict(width=2, color="white")
    #     ),
    #     text=locs.index
    # ))

    mapbox_layout: dict[str, object] = dict(
        zoom=6,
        center=dict(lat=52.507401395949145, lon=13.413453748453412),
    )
    if st.session_state.map_style == "OpenStreetMap":
        mapbox_layout["style"] = "open-street-map"
    elif st.session_state.map_style == "Carto Positron":
        mapbox_layout["style"] = "carto-positron"
    else:
        # Google Satellite tiles as raster layer.
        mapbox_layout["style"] = "white-bg"
        mapbox_layout["layers"] = [
            {
                "below": "traces",
                "sourcetype": "raster",
                "source": ["https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"],
                "opacity": 1,
            }
        ]

    fig.update_layout(
        mapbox=mapbox_layout,
        height=420,
        margin=dict(l=0, r=0, t=0, b=0),
    )

    st.plotly_chart(
        fig,
        width="stretch",
        key="stations_map",
        on_select="rerun",
        selection_mode=("points", "box", "lasso"),
        config={"scrollZoom": True},
    )

with main_plot_cell:
    st.markdown("#### Zusammenfassungsplot")
    if tickers:
        fig = px.line(summary_data, x=summary_data.index, y=tickers)
        fig.update_layout(legend_title_text="Standorte")
        fig.update_yaxes(title_text=f"SWC ({st.session_state.swc_source}) (m³/m³)")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Waehle Standorte, um den Zeitreihen-Plot anzuzeigen.")

""
""

"""
## Datendownload
"""

plot_start_date = date_start.date()
plot_end_date = date_end.date()
defaults_anchor = (plot_start_date, plot_end_date, tuple(tickers))

if (
    "download_defaults_anchor" not in st.session_state
    or st.session_state.download_defaults_anchor != defaults_anchor
):
    st.session_state.download_stations = tickers.copy()
    st.session_state.download_horizon = st.session_state.selected_horizon
    st.session_state.download_applied_horizon = st.session_state.download_horizon
    st.session_state.download_start = plot_start_date
    st.session_state.download_end = plot_end_date
    st.session_state.download_defaults_anchor = defaults_anchor
    for station in STOCKS:
        st.session_state[f"download_station_{station}"] = station in tickers

if "download_horizon" not in st.session_state:
    st.session_state.download_horizon = st.session_state.selected_horizon
if "download_applied_horizon" not in st.session_state:
    st.session_state.download_applied_horizon = st.session_state.download_horizon
if st.session_state.download_horizon not in horizon_map:
    st.session_state.download_horizon = "Maximum"

with st.expander("Download", expanded=False):
    st.write("Datenarten")
    source_cols = st.columns(3)
    include_crns = source_cols[0].checkbox("SWC (CRNS)", value=True)
    include_swap = source_cols[1].checkbox("SWC (SWAP)", value=False)
    include_d86 = source_cols[2].checkbox("D86 (CRNS)", value=False)

    selected_sources = []
    if include_crns:
        selected_sources.append(("SWC_CRNS", data2_full))
    if include_swap:
        selected_sources.append(("SWC_SWAP", sim2_full))
    if include_d86:
        selected_sources.append(("D86_CRNS", d862_full))

    st.write("Stationen zum Download")
    if st.button("Alle Stationen auswählen", key="download_select_all"):
        for station in STOCKS:
            st.session_state[f"download_station_{station}"] = True

    station_cols = st.columns(3)
    for idx, station in enumerate(STOCKS):
        station_cols[idx % 3].checkbox(station, key=f"download_station_{station}")

    download_stations = [
        station
        for station in STOCKS
        if st.session_state.get(f"download_station_{station}", False)
    ]
    st.session_state.download_stations = download_stations

    effective_download_stations = normalize_stocks(download_stations) or tickers
    download_min_date = selected_min_date(data2_full, effective_download_stations)
    download_max_date = today_date

    if st.session_state.download_horizon not in horizon_map:
        st.session_state.download_horizon = "Maximum"

    st.pills(
        "Download Zeithorizont",
        options=list(horizon_map.keys()),
        key="download_horizon",
        selection_mode="single",
    )

    download_horizon = st.session_state.download_horizon
    if download_horizon not in horizon_map:
        download_horizon = "Maximum"
        st.session_state.download_horizon = download_horizon
    download_horizon_days = horizon_map[download_horizon]

    if download_horizon != st.session_state.download_applied_horizon:
        st.session_state.download_applied_horizon = download_horizon
        if download_horizon_days == "custom":
            pass
        elif download_horizon_days is None:
            st.session_state.download_start = download_min_date
            st.session_state.download_end = download_max_date
        else:
            st.session_state.download_end = download_max_date
            candidate_start = download_max_date - timedelta(
                days=download_horizon_days - 1
            )
            st.session_state.download_start = max(download_min_date, candidate_start)

    if download_horizon_days is None:
        st.session_state.download_start = download_min_date
        st.session_state.download_end = download_max_date

    if st.session_state.download_start < download_min_date:
        st.session_state.download_start = download_min_date
    if st.session_state.download_start > download_max_date:
        st.session_state.download_start = download_max_date
    if st.session_state.download_end < download_min_date:
        st.session_state.download_end = download_min_date
    if st.session_state.download_end > download_max_date:
        st.session_state.download_end = download_max_date
    if st.session_state.download_start > st.session_state.download_end:
        st.session_state.download_end = st.session_state.download_start

    download_cols = st.columns(2)
    download_cols[0].date_input(
        "Download Start",
        min_value=download_min_date,
        max_value=download_max_date,
        key="download_start",
    )
    download_cols[1].date_input(
        "Download Ende",
        min_value=download_min_date,
        max_value=download_max_date,
        key="download_end",
    )

    download_start = pd.to_datetime(st.session_state.download_start)
    download_end = pd.to_datetime(st.session_state.download_end)
    normalized_download_stations = normalize_stocks(download_stations)
    preview_frames = []
    for source_name, source_df in selected_sources:
        source_slice = source_df.loc[download_start:download_end]
        if normalized_download_stations:
            source_slice = source_slice[normalized_download_stations]
        else:
            source_slice = pd.DataFrame(index=source_slice.index)
        source_slice = source_slice.rename(columns=lambda col: f"{col}_{source_name}")
        preview_frames.append(source_slice)

    if preview_frames:
        download_data = pd.concat(preview_frames, axis=1)
    else:
        # Keep time index visible even if no source is selected.
        download_data = pd.DataFrame(
            index=data2_full.loc[download_start:download_end].index
        )

    st.caption(
        "Vorschau der Downloaddaten (Spalten sind nach Datenart gekennzeichnet)."
    )
    st.dataframe(download_data, width="stretch")

    license_text = st.write(
        "Für die Nutzung aller Daten im obenstehenden Verzeichnis gilt die Creative Commons Attribution Lizenz CC-BY 4.0. "
        "Bitte zitieren Sie im Nutzungsfall die Daten wie folgt: "
        "University of Potsdam, Helmholtz Centre for Environmental Research: CRNS-based soil moisture and drought monitoring in the Germany federal state of Brandenburg [Data set], URL: https://cosmic-sense.github.io/brandenburg/daten/."
    )
    st.link_button("CC-BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
    if normalized_download_stations and selected_sources:
        csv_content = download_data.reset_index().to_csv(index=False)
        st.download_button(
            label="CSV herunterladen",
            data=csv_content.encode("utf-8"),
            file_name="monitoring_subset.csv",
            mime="text/csv",
            use_container_width=True,
        )
    elif not selected_sources:
        st.info("Wähle mindestens eine Datenart fuer den Download.")
    else:
        st.info("Wähle mindestens eine Station fuer den Download.")
