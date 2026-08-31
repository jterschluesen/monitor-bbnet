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
from plotly.subplots import make_subplots
from data_sources import (
    DEFAULT_STOCKS,
    DEFAULT_UNIT,
    FULL_RANGE_LABEL,
    HORIZON_MAP,
    STOCKS,
    PRIMARY_CRNS,
    UNITS,
    construction_warning,
    URL_LOCATIONS,
    URL_SNOW_FLAGS,
    PLOT_CONFIG,
    add_range_slider,
    add_snow_shading,
    get_download_unit,
    get_mask_snow,
    get_series,
    get_shared_window,
    glossary_expander,
    init_shared_window,
    load_locations,
    load_series,
    load_snow_flags,
    maybe_mask_snow,
    moisture_label,
    normalize_stocks,
    selected_max_date,
    selected_min_date,
    set_download_unit,
    set_shared_stations,
    snow_mask_toggle,
    set_shared_window,
    station_label,
    union_snow_periods,
    station_labeller,
    to_download_unit,
    to_plot_unit,
)

st.set_page_config(
    page_title="Bodenwassermonitor Brandenburg",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

construction_warning()

st.title("Bodenwassermonitor Brandenburg")
st.write(
    "Der Bodenwassermonitor Brandenburg dient der Darstellung von gemessenen und simulierten Bodenfeuchtedaten, verschiedener Standorte in Brandenburg, sowir daraus abgeleiteter Ergebnisse zu den Themen Bodenfeuchte-Monitoring und Grundwasserneubildung in Brandenburg. "
    'Die Universität Potsdam kooperiert dazu mit dem Land Brandenburg, dem Helmholtz-Zentrum für Umweltforschung und dem Climate Change Center Berlin-Brandenburg, unter anderem in den vom Land Brandenburg geförderten Projekten “Einfluss des Klimawandels auf die Grundwasserneubildung in Brandenburg: Anpassungsbedarfe und Hebelpunkte” und "Klimafolgen- und Anpassung Brandenburg: Untersuchungen zum Landschaftswasserhaushalt und Starkregenrisikomanagement".'
)
st.write(
    "Die dargestellten Daten beruhen auf zwei Grundlagen: der Messung der Bodenfeuchte mit kosmischen Neutronensensoren, welche die Beziehung zwischen der Menge der kosmischen Neutronen zur Bodenfeuchte ausnutzt (Messung via CRNS, siehe 'Abkürzungen und Erklärungen') und Modellergebnissen aus dem Bodenwasserhaushaltsmodell [SWAP](https://www.swap.alterra.nl/) (Boden-Wasser-Atmosphäre-Pflanze). Die Daten werden in der Einheit Volumenprozent (Vol.-%) dargestellt. "
    "Die Daten beschreiben die Bodenfeuchte in der oberen Bodenschicht. Da die Eindringtiefe des CRNS-Signals selbst von der Bodenfeuchte abhängt, ist die Tiefe, über die die Messung aggregiert wird, variable. Eine Standortbasierte Darstellung der Messungen via CRNS ist auf der Seite Messstationen verfügbar."
    "Derzeit stehen die Messdaten des CRNS-Netzwerks (Cosmic Ray Neutron Sensing) von 12 Standorten in Brandenburg zur Verfügung, welche von der Universität Potsdam, dem Helmholtz-Zentrum für Umweltforschung (UFZ) sowie dem Land Brandenburg (LGBR) betrieben werden. Die Messungen dienen zur Kallibrierung des Bodenwasserhaushaltsmodell SWAP (Boden-Wasser-Atmosphäre-Pflanze) mit welchem historische Bodenfeuchtedaten für die Standorte in Brandenburg simuliert werden können. "
)


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
    set_shared_stations(st.session_state.tickers_input)


def mark_main_horizon_custom():
    # Typing a start/end date means "own period": no horizon pill stays selected.
    st.session_state.selected_horizon = None
    st.session_state.applied_horizon = None


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


# One heading over both columns: map and stations on the left, the time series with
# its controls on the right.
st.markdown("### Standortübersicht der Zeitreihen")

map_col, plot_col = st.columns([1.2, 2.5], gap="medium")
map_cell = map_col.container(border=True, height="stretch")
plot_cell = plot_col.container(border=True, height="stretch")
with plot_cell:
    # Created first so the chart stays above; the widgets below are filled in early
    # because the figure needs their values.
    main_plot_cell = st.container()
    controls_cell = st.container()

# Names come from the shared registry, so the overview and the station page always
# mean the same thing by "CRNS". These label the subplots, hence the spelled-out form.
SOURCE_LABELS = {
    "CRNS": get_series(PRIMARY_CRNS).hover,
    "SWAP": get_series("swap_0_30").hover,
}

with controls_cell:
    if "swc_sources" not in st.session_state:
        st.session_state.swc_sources = ["CRNS"]
    if "map_style" not in st.session_state:
        st.session_state.map_style = "OpenStreetMap"

    selection_cols = st.columns([3, 1], gap="medium")

    with selection_cols[0]:
        st.pills(
            "Datengrundlage",
            options=list(SOURCE_LABELS),
            format_func=lambda source: SOURCE_LABELS[source],
            key="swc_sources",
            selection_mode="multi",
        )

    with selection_cols[1]:
        # The station list itself lives next to the map in the left column.
        snow_mask_toggle()

# Time horizon selector; shared with the "Messstationen" page.
horizon_map = HORIZON_MAP

tickers = normalize_stocks(st.session_state.tickers_input)
if tickers != st.session_state.tickers_input:
    st.session_state.tickers_input = tickers
    update_query_param()

if not tickers:
    map_cell.info("Wähle mindestens einen Standort.", icon=":material/info:")


# data = load_data(dtimes, STOCKS, rho=0.7, seed=42)
data2_full = load_series(PRIMARY_CRNS)
sim2_full = load_series("swap_0_30")  # use 0-30cm instead of weighted
d862_full = load_series("d86")
snow_flags = load_snow_flags(URL_SNOW_FLAGS)
# Shade exactly the phases of the stations on screen, so the band matches the gaps
# that masking leaves in the curves.
snow_phase_periods = union_snow_periods(snow_flags, tickers)
# Snow biases the neutron count: the plots show gaps there, the download keeps the
# unmasked source data.
crns_plot_full = maybe_mask_snow(data2_full, snow_flags)
# https://b2drop.eudat.eu/s/yr5d6i72cCacYpH/swc-from-swap.txt


# The overview window follows the CRNS record only: the model runs reach back to
# 1990 and would otherwise stretch the axis and the navigator far beyond the
# measurements.
min_date = selected_min_date(data2_full, tickers)
max_date = selected_max_date(data2_full, tickers)
today_date = pd.Timestamp.today().date()
end_bound = min(max_date, today_date)
crns_span = (pd.to_datetime(min_date), pd.to_datetime(end_bound))

# Seed the page widgets from the window shared with the "Messstationen" page.
init_shared_window(min_date, end_bound)
shared_start, shared_end, shared_horizon = get_shared_window(min_date, end_bound)

if "selected_horizon" not in st.session_state:
    st.session_state.selected_horizon = shared_horizon
if "applied_horizon" not in st.session_state:
    st.session_state.applied_horizon = st.session_state.selected_horizon
if "date_start" not in st.session_state:
    st.session_state.date_start = shared_start
if "date_end" not in st.session_state:
    st.session_state.date_end = shared_end

ticker_signature = tuple(tickers)
if "last_ticker_signature" not in st.session_state:
    st.session_state.last_ticker_signature = ticker_signature
if "last_selected_min_date" not in st.session_state:
    st.session_state.last_selected_min_date = min_date

# If a new station selection extends the available history, show the whole series.
if ticker_signature != st.session_state.last_ticker_signature:
    previous_min_date = st.session_state.last_selected_min_date
    if min_date < previous_min_date:
        st.session_state.selected_horizon = FULL_RANGE_LABEL
        st.session_state.applied_horizon = FULL_RANGE_LABEL
        st.session_state.date_start = min_date
        st.session_state.date_end = end_bound
    st.session_state.last_ticker_signature = ticker_signature

st.session_state.last_selected_min_date = min_date

with controls_cell:
    # Dates and horizon share one row; the columns are created up front so the
    # widgets can be filled in whatever order the logic below needs.
    time_cols = st.columns([1, 1, 3], gap="medium", vertical_alignment="bottom")

    if (
        st.session_state.selected_horizon is not None
        and st.session_state.selected_horizon not in horizon_map
    ):
        st.session_state.selected_horizon = FULL_RANGE_LABEL

    with time_cols[2]:
        st.pills(
            "Zeithorizont",
            options=list(horizon_map.keys()),
            key="selected_horizon",
            selection_mode="single",
        )

    # Deselecting the pill (or editing a date) means "own period": the dates below
    # stay as they are.
    horizon = st.session_state.selected_horizon
    horizon_days = horizon_map.get(horizon) if horizon else None

    if horizon != st.session_state.applied_horizon:
        st.session_state.applied_horizon = horizon
        if horizon is None:
            pass
        elif horizon_days is None:
            st.session_state.date_start = min_date
            st.session_state.date_end = end_bound
        else:
            st.session_state.date_end = end_bound
            candidate_start = end_bound - timedelta(days=horizon_days - 1)
            st.session_state.date_start = max(min_date, candidate_start)

    # Keep existing values valid when selected stations change available date range.
    if st.session_state.date_end > end_bound:
        st.session_state.date_end = end_bound
    if st.session_state.date_end < min_date:
        st.session_state.date_end = min_date
    if st.session_state.date_start > end_bound:
        st.session_state.date_start = end_bound
    if st.session_state.date_start < min_date:
        st.session_state.date_start = min_date

    if horizon is None:
        time_cols[2].caption("Eigener Zeitraum – über Start und Ende gesetzt.")

    time_cols[0].date_input(
        "Start",
        min_value=min_date,
        max_value=end_bound,
        key="date_start",
        on_change=mark_main_horizon_custom,
    )
    time_cols[1].date_input(
        "Ende",
        min_value=min_date,
        max_value=end_bound,
        key="date_end",
        on_change=mark_main_horizon_custom,
    )

# Hand the window and the station selection to the other pages.
set_shared_window(
    st.session_state.date_start,
    st.session_state.date_end,
    st.session_state.selected_horizon,
)
set_shared_stations(tickers)

if st.session_state.date_start > st.session_state.date_end:
    st.error("Das Startdatum muss vor dem Enddatum liegen.")
    st.stop()

date_start = pd.to_datetime(st.session_state.date_start)
date_end = pd.to_datetime(st.session_state.date_end)

data2 = data2_full.loc[date_start:date_end]
sim2 = sim2_full.loc[date_start:date_end]
d862 = d862_full.loc[date_start:date_end]

if data2.empty:
    st.warning("Keine Daten im gewählten Zeitraum gefunden.")
    st.stop()

# reindex (not direct selection): stations missing from a source - e.g. WUS,
# which has no SWAP run - become NaN columns instead of raising KeyError.
data = data2.reindex(columns=tickers)
sim = sim2.reindex(columns=tickers)
d86 = d862.reindex(columns=tickers)

selected_sources_overview = [
    source for source in SOURCE_LABELS if source in st.session_state.swc_sources
]
# The overview plots the whole series; the range slider below it holds the full
# record while the axis shows the selected window. Both are clipped to the CRNS
# span so the long model history does not stretch axis and navigator.
source_data = {
    "CRNS": crns_plot_full.loc[crns_span[0] : crns_span[1]].reindex(columns=tickers),
    "SWAP": sim2_full.loc[crns_span[0] : crns_span[1]].reindex(columns=tickers),
}

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
    st.error(
        "Für folgende Standorte konnten keine Daten geladen werden: "
        f"{', '.join(station_label(col, locs) for col in empty_columns)}."
    )
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
    # Station selection sits with the map, both feed the same session state.
    st.multiselect(
        "Standorte",
        options=STOCKS,
        key="tickers_input",
        format_func=station_labeller(locs),
        placeholder="Wähle mindestens einen Standort",
        on_change=update_query_param,
    )
    st.caption(
        "Klicke mehrere Punkte zum Hinzufügen oder Entfernen oder nutze Box und Lasso für die Mehrfachauswahl."
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
        # ("id", "ID"),
        ("name", "Name"),
        ("landuse", "Landnutzung"),
        ("manufacturer/model", "Messgerät (Modell/Hersteller)"),
        # ("ka5_kurz", "KA5 kurz"),
        ("ka5_bez", "Bodenart (Kartieranleitung KA5)"),
        ("m1_wert", "Gesättigte Leitfähigkeit (0-1 m)"),
        ("m2_wert", "Gesättigte Leitfähigkeit (0-2 m)"),
        ("fk_1m_wert", "Feldkapazität (0-1 m)"),
        ("nfk_1m_wert", "Nutzbare Feldkapazität (0-1 m)"),
        ("humus", "Humusgehalt"),
        ("biomass_eff", "Biomasse [kg/m²]"),
        ("bulk_density_eff", "Rohdichte des Bodens [kg/m³]"),
        # ("theta_eff", "Theta"),
        # ("organic_matter_eff", "Organische Substanz"),
        # ("lattice_water_eff", "Gitterwasser"),
        # ("theta_total_eff_eff", "Theta gesamt"),
        ("gw_depth", "Grundwassertiefe [m]"),
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

    # Marker and label colours follow the basemap so both stay legible.
    dark_basemap = st.session_state.map_style in ("Carto Dark", "Google Satellite")
    marker_color = "#7E7C7C" if dark_basemap else "#1A4600"
    selected_color = "#FFFFFF" if dark_basemap else "#20C000"
    label_color = "#7E7C7C" if dark_basemap else "#1A4600"

    fig = go.Figure()

    fig.add_trace(
        go.Scattermap(
            lat=station_locs.lat,
            lon=station_locs.lon,
            mode="markers+text",
            marker=dict(
                size=12,
                color=marker_color,
            ),
            text=[station_label(sid, locs) for sid in station_ids],
            # Full opacity and bold, so the names stay readable on every basemap.
            textfont=dict(size=12, color=label_color, weight="bold"),
            textposition="top center",
            customdata=station_attributes,
            selectedpoints=selected_point_indices,
            selected=dict(marker=dict(size=16, color=selected_color, opacity=1)),
            unselected=dict(marker=dict(size=12, opacity=1)),
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

    map_layout: dict[str, object] = dict(
        zoom=6,
        center=dict(lat=52.507401395949145, lon=13.413453748453412),
    )
    if st.session_state.map_style == "OpenStreetMap":
        map_layout["style"] = "open-street-map"
    elif st.session_state.map_style == "Carto Positron":
        map_layout["style"] = "carto-positron"
    elif st.session_state.map_style == "Carto Dark":
        map_layout["style"] = "carto-darkmatter"
    else:
        # Google Satellite tiles as raster layer.
        map_layout["style"] = "white-bg"
        map_layout["layers"] = [
            {
                "below": "traces",
                "sourcetype": "raster",
                "source": ["https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"],
                "opacity": 1,
            }
        ]

    fig.update_layout(
        map=map_layout,
        height=250,
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

    if st.button(
        "Zu den Messreihen",
        icon=":material/monitoring:",
        width="stretch",
        disabled=not tickers,
    ):
        set_shared_stations(tickers)
        st.switch_page("pages/2_Single_Stations.py")

with main_plot_cell:
    if not tickers:
        st.info("Standorte wählen, um den Zeitreihen-Plot anzuzeigen.")
    elif not selected_sources_overview:
        st.info("Mindestens eine Datengrundlage wählen.")
    else:
        station_colors = {
            station: px.colors.qualitative.Safe[idx % len(px.colors.qualitative.Safe)]
            for idx, station in enumerate(tickers)
        }
        # One row per data source, sharing the time axis.
        overview_fig = make_subplots(
            rows=len(selected_sources_overview),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.16,
            subplot_titles=[
                SOURCE_LABELS[source] for source in selected_sources_overview
            ],
        )
        # Navigator span comes from the measurements, never from the model run.
        crns_valid = source_data["CRNS"].dropna(how="all").index
        full_start = crns_valid.min() if len(crns_valid) else None
        full_end = crns_valid.max() if len(crns_valid) else None
        for row, source in enumerate(selected_sources_overview, start=1):
            frame = source_data[source]
            valid_index = frame.dropna(how="all").index
            if len(valid_index) and full_start is None:
                full_start = (
                    valid_index.min()
                    if full_start is None
                    else min(full_start, valid_index.min())
                )
                full_end = (
                    valid_index.max()
                    if full_end is None
                    else max(full_end, valid_index.max())
                )
            for station in tickers:
                if station not in frame.columns:
                    continue
                series = to_plot_unit(frame[station])
                overview_fig.add_trace(
                    go.Scatter(
                        x=series.index,
                        y=series,
                        mode="lines",
                        name=station_label(station, locs),
                        legendgroup=station,
                        showlegend=row == 1,
                        # Model runs are dashed everywhere in the app.
                        line=dict(
                            color=station_colors[station],
                            dash="dash" if source == "SWAP" else "solid",
                        ),
                    ),
                    row=row,
                    col=1,
                )
            overview_fig.update_yaxes(title_text=moisture_label(), row=row, col=1)
            add_snow_shading(
                overview_fig,
                snow_phase_periods,
                xrange=(full_start, full_end)
                if full_start is not None
                else (date_start, date_end),
                add_legend=row == 1,
                add_label=row == 1,
                row=row,
                col=1,
            )
        overview_fig.update_layout(
            height=400,
            legend_title_text="Standorte",
            margin=dict(l=40, r=20, t=40, b=40),
        )
        # Navigator strip over the whole record, window on the axis.
        if full_start is None:
            full_start, full_end = date_start, date_end
        add_range_slider(
            overview_fig,
            full_range=(full_start, full_end),
            window=(max(date_start, full_start), min(date_end, full_end)),
            thickness=0.08,
            row=len(selected_sources_overview),
            col=1,
        )
        st.plotly_chart(overview_fig, width="stretch", config=PLOT_CONFIG)

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

# Widget-bound keys are dropped while another page is shown, so re-seed whatever
# is missing instead of relying on the anchor block above.
if "download_start" not in st.session_state:
    st.session_state.download_start = plot_start_date
if "download_end" not in st.session_state:
    st.session_state.download_end = plot_end_date
for station in STOCKS:
    st.session_state.setdefault(f"download_station_{station}", station in tickers)
if "download_horizon" not in st.session_state:
    st.session_state.download_horizon = st.session_state.selected_horizon
if "download_applied_horizon" not in st.session_state:
    st.session_state.download_applied_horizon = st.session_state.download_horizon
if (
    st.session_state.download_horizon is not None
    and st.session_state.download_horizon not in horizon_map
):
    st.session_state.download_horizon = FULL_RANGE_LABEL

with st.expander("Download", expanded=False):
    st.write("Datenarten")
    source_cols = st.columns(3)
    include_crns = source_cols[0].checkbox(
        "Bodenfeuchte (Messung via CRNS)", value=True
    )
    include_swap = source_cols[1].checkbox("Bodenfeuchte (Modell SWAP)", value=False)
    include_d86 = source_cols[2].checkbox(
        "Eindringtiefe (Messung via CRNS)", value=False
    )

    # The plots always show Vol.-%; only the download offers a choice of unit.
    if "download_unit" not in st.session_state:
        st.session_state.download_unit = DEFAULT_UNIT

    def sync_download_unit():
        choice = st.session_state.download_unit
        if choice not in UNITS:
            # Deselecting would leave no unit at all; keep the last one.
            st.session_state.download_unit = get_download_unit()
            return
        set_download_unit(choice)

    st.segmented_control(
        "Einheit der Bodenfeuchte",
        options=list(UNITS),
        key="download_unit",
        selection_mode="single",
        on_change=sync_download_unit,
    )
    sync_download_unit()

    unit_suffix = "Vol-Prozent" if get_download_unit() == "Vol.-%" else "m3_pro_m3"
    # The CRNS export follows the snow setting from the selection above.
    selected_sources = []
    if include_crns:
        selected_sources.append(
            (f"Bodenfeuchte_CRNS_{unit_suffix}", to_download_unit(crns_plot_full))
        )
    if include_swap:
        selected_sources.append(
            (f"Bodenfeuchte_SWAP_{unit_suffix}", to_download_unit(sim2_full))
        )
    if include_d86:
        selected_sources.append(
            ("Eindringtiefe_CRNS_cm", maybe_mask_snow(d862_full, snow_flags))
        )

    st.write("Stationen zum Download")
    if st.button("Alle Stationen auswählen", key="download_select_all"):
        for station in STOCKS:
            st.session_state[f"download_station_{station}"] = True

    station_cols = st.columns(3)
    for idx, station in enumerate(STOCKS):
        station_cols[idx % 3].checkbox(
            station_label(station, locs), key=f"download_station_{station}"
        )

    download_stations = [
        station
        for station in STOCKS
        if st.session_state.get(f"download_station_{station}", False)
    ]
    st.session_state.download_stations = download_stations

    effective_download_stations = normalize_stocks(download_stations) or tickers
    download_min_date = selected_min_date(data2_full, effective_download_stations)
    download_max_date = today_date

    if (
        st.session_state.download_horizon is not None
        and st.session_state.download_horizon not in horizon_map
    ):
        st.session_state.download_horizon = FULL_RANGE_LABEL

    st.pills(
        "Download Zeithorizont",
        options=list(horizon_map.keys()),
        key="download_horizon",
        selection_mode="single",
    )

    download_horizon = st.session_state.download_horizon
    download_horizon_days = (
        horizon_map.get(download_horizon) if download_horizon else None
    )

    if download_horizon != st.session_state.download_applied_horizon:
        st.session_state.download_applied_horizon = download_horizon
        if download_horizon is None:
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
            # reindex so a station absent from this source (e.g. WUS in SWAP)
            # yields an empty column instead of a KeyError.
            source_slice = source_slice.reindex(columns=normalized_download_stations)
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
        "Vorschau der Downloaddaten. Die Spaltennamen nennen Standort, Datenart und "
        f"Einheit; die Bodenfeuchte steht in {get_download_unit()}. "
        + (
            "Messwerte via CRNS in Schneephasen sind ausgeblendet."
            if get_mask_snow()
            else "Schneephasen sind nicht ausgeblendet."
        )
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
        st.info("Wähle mindestens eine Datenart für den Download.")
    else:
        st.info("Wähle mindestens eine Station für den Download.")

glossary_expander()
