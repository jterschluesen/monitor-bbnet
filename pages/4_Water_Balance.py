# -*- coding: utf-8 -*-

from datetime import date

import pandas as pd
import streamlit as st

from data_sources import (
    BALANCE_FIRST_YEAR,
    BALANCE_REFERENCE_PERIOD,
    DEFAULT_BALANCE_SPAN_START,
    DEFAULT_BALANCE_YEAR,
    PLOT_CONFIG,
    STOCKS,
    URL_LOCATIONS,
    build_water_balance_figure,
    construction_warning,
    get_shared_stations,
    glossary_expander,
    load_balance_normals,
    load_locations,
    load_water_balance,
    station_label,
    station_labeller,
)

st.set_page_config(
    page_title="Wasserbilanz",
    page_icon=":material/balance:",
    layout="wide",
)

construction_warning()

st.title("Wasserbilanz")
st.write(
    "Die Grafiken zeigen die jährliche Wasserbilanz je Standort aus den SWAP-Simulationen: "
    "Niederschlag, Verdunstung/Evapotranspiration (ET inkl. Interzeption) und das Sickerwasser "
    "in 2 m Tiefe, welches zur Grundwasserneubildung beiträgt. Gestrichelt ist jeweils das "
    f"langjährige Mittel ({BALANCE_REFERENCE_PERIOD}) zum Vergleich. Grau hinterlegt ist der "
    "Bodenwasserspeicher der obersten 1 m Bodenschicht."
)

locs = load_locations(URL_LOCATIONS)
# Stations without a balance file are dropped where they are loaded, not listed here.
wb_stations = list(STOCKS)
normals = load_balance_normals()

current_year = date.today().year
today = pd.Timestamp(date.today())

# --- One station in detail, over as many years as the slider spans ------------
ctrl = st.columns([2, 3])
# The station picked on the overview page comes preselected.
shared_station = next(
    (s for s in get_shared_stations([]) if s in wb_stations), wb_stations[0]
)
station = ctrl[0].selectbox(
    "Standort",
    options=wb_stations,
    index=wb_stations.index(shared_station),
    format_func=station_labeller(locs),
)
first_year, last_year = ctrl[1].slider(
    "Jahre",
    min_value=BALANCE_FIRST_YEAR,
    max_value=current_year,
    value=(DEFAULT_BALANCE_SPAN_START, current_year),
    help="Die Jahre im Diagramm dieses Standorts. Beide Regler auf dasselbe Jahr "
    "zeigen ein einzelnes Jahr.",
)
years = list(range(first_year, last_year + 1))
# Clamp the upper bound to today so the (incomplete) current year shows no trailing gap.
xrange = (
    pd.Timestamp(f"{first_year}-01-01"),
    min(pd.Timestamp(f"{last_year}-12-31"), today),
)

wb = load_water_balance(station)
if wb.empty:
    st.warning("Wasserbilanz-Daten für diesen Standort sind derzeit nicht verfügbar ")
    st.stop()

fig = build_water_balance_figure(
    wb,
    normals,
    station,
    years,
    station_name=station_label(station, locs),
    xrange=xrange,
)
st.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

st.caption(
    "Kumulative Flüsse je Kalenderjahr. Gestrichelt: langjähriges Mittel "
    f"{BALANCE_REFERENCE_PERIOD}."
)

# --- Overview raster: every station, one year -------------------------------
st.divider()
head = st.columns([2, 3], vertical_alignment="bottom")
# One year per tile keeps the tiles comparable; several years are read off the
# station plot above.
overview_years = list(range(BALANCE_FIRST_YEAR, current_year + 1))
overview_year = head[1].selectbox(
    "Jahr",
    options=overview_years,
    index=overview_years.index(DEFAULT_BALANCE_YEAR),
)
head[0].subheader(f"Übersicht {overview_year} – alle Standorte")

overview_xrange = (
    pd.Timestamp(f"{overview_year}-01-01"),
    min(pd.Timestamp(f"{overview_year}-12-31"), today),
)

NCOLS = 3
grid = st.columns(NCOLS)
for i, s in enumerate(wb_stations):
    cell = grid[i % NCOLS].container(border=True)
    wb_s = load_water_balance(s)
    if wb_s.empty:
        cell.caption(f"{station_label(s, locs)}: keine Daten")
        continue
    tile = build_water_balance_figure(
        wb_s,
        normals,
        s,
        [overview_year],
        station_name=station_label(s, locs),
        xrange=overview_xrange,
        show_legend=False,
        height=240,
        compact=True,
    )
    cell.plotly_chart(tile, width="stretch", key=f"wb_overview_{s}", config=PLOT_CONFIG)

glossary_expander()
