# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_sources import (
    HORIZON_MAP,
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
    PLOT_CONFIG,
    add_calibration_marker,
    add_range_slider,
    add_snow_shading,
    get_shared_stations,
    get_shared_window,
    glossary_expander,
    load_locations,
    load_snow_flags,
    load_time_series,
    maybe_mask_snow,
    moisture_label,
    reset_shared_window,
    set_shared_window,
    smt_depth_label,
    snow_mask_toggle,
    station_label,
    station_snow_periods,
    to_plot_unit,
    window_from_horizon,
)

st.set_page_config(
    page_title="Einzelne Standorte",
    page_icon=":material/monitoring:",
    layout="wide",
)

construction_warning()

st.title("Messreihen einzelner Standorte")
st.write(
    "Die Seite dient der dient der detaillierten Darstellung der Datne an Einzelstandorten. "
    "Die dargestellten Daten beruhen auf der Messung mit kosmischen Neutronensensoren "
    "(Messung via CRNS), auf punktuellen Bodenfeuchtesensoren (SMT) und auf dem "
    "Bodenwasserhaushaltsmodell [SWAP](https://www.swap.alterra.nl/). "
    "Die Eindringtiefe der Neutronenmessung hängt unter anderem von der Bodenfeuchte selbst "
    "ab und ändert sich daher laufend. Damit Messung und Modell vergleichbar bleiben, kann das "
    "Modellergebnis ebenfalls über diese Eindringtiefe gemittelt werden (tiefengewichtet). "
    "Grundsätzliche Informationen zu den Messungen finden Sie unten auf der Seite."
)

# All hues are from the Okabe-Ito colour-vision-deficiency-safe palette.
COLOR_CRNS = "#E69F00"  # orange
COLOR_CRNS_old = "#CC79A7"  # reddish purple
COLOR_NEPTOON_DES = "#56B4E9"  # sky blue
COLOR_NEPTOON_UTS = "#0072B2"  # blue
COLOR_D86 = "#5A2A00"  # brown
# Kept faint so the penetration depth reads as background, not as a measurement.
FILL_D86 = "rgba(90, 42, 0, 0.08)"
ALPHA_D86 = 0.45
SMT_GRAY_SCALE = ["#1F1F1F", "#4D4D4D", "#737373", "#A6A6A6", "#D0D0D0"]
# One purple family for every SWAP series (light = shallow, dark = deep), kept off
# the orange/blue hues of the measurements. All model traces are dashed.
SWAP_DEPTH_COLORS = {"0–30 cm": "#BCBDDC", "0–1 m": "#807DBA", "0–2 m": "#54278F"}
COLOR_SWAP = "#3F007D"  # depth-weighted model run: darkest of the same family
TRACE_ALPHA = 0.8

# The SWAP runs reach back to 1990, the CRNS record starts in 2021. Clip the model
# series so the long simulation history does not stretch the station plots.
SWAP_START = pd.Timestamp("2024-01-01")

# One metric per fixed SWAP depth mean, next to the CRNS-depth-weighted SWC(SWAP).
SWAP_DEPTH_METRICS = {f"SWC(SWAP {depth})": depth for depth in SWAP_SM_DEPTHS}

# Internal metric key -> readable label (legend + selector). Grouped by source.
METRIC_LABELS = {
    "SWC(CRNS)": "Bodenfeuchte (Messung via CRNS, generelle Kalibrierung)",
    "SWC(CRNS_old)": "Bodenfeuchte (Messung via CRNS, frühere Kalibrierung)",
    "SWC(NEPTOON_DES)": "Bodenfeuchte (Messung via CRNS, Auswertung nach Desilets)",
    "SWC(NEPTOON_UTS)": "Bodenfeuchte (Messung via CRNS, Auswertung nach UTS)",
    "D86": "Eindringtiefe (Messung via CRNS)",
    "SWC(SWAP)": "Bodenfeuchte (Modell SWAP, tiefengewichtet)",
    "SWC(SMT)": "Bodenfeuchte (Sensoren SMT)",
    **{
        metric: f"Bodenfeuchte (Modell SWAP, {depth})"
        for metric, depth in SWAP_DEPTH_METRICS.items()
    },
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


locs = load_locations(URL_LOCATIONS)
swap_full = load_time_series(URL_SWC_SWAP).loc[SWAP_START:]
SMT = load_time_series(URL_SWC_SMT)
SMT = rename_smt_columns(SMT)
snow_flags = load_snow_flags(URL_SNOW_FLAGS)

# Snow on the ground biases the neutron count, so every CRNS-derived series is
# blanked out during a snow phase; model and in-soil sensors stay untouched.
crns_full = maybe_mask_snow(load_time_series(URL_SWC_CRNS), snow_flags)
crns_full_old = maybe_mask_snow(load_time_series(URL_SWC_CRNS_old), snow_flags)
d86_full = maybe_mask_snow(load_time_series(URL_D86_CRNS), snow_flags)
neptoon_des_full = maybe_mask_snow(load_time_series(URL_SWC_NEPTOON_DES), snow_flags)
neptoon_uts_full = maybe_mask_snow(load_time_series(URL_SWC_NEPTOON_UTS), snow_flags)

smt_depths = sorted(
    {col.split("_SMT_", 1)[1] for col in SMT.columns if "_SMT_" in col},
    key=_depth_sort_key,
)

available_stations = [station for station in STOCKS if station in crns_full.columns]
# All stations are shown; the ones picked on the overview page come first.
preferred = [s for s in get_shared_stations([]) if s in available_stations]
selected_stations = preferred + [s for s in available_stations if s not in preferred]

station_name_map = {
    station: station_label(station, locs) for station in selected_stations
}

DEFAULT_METRICS_CRNS = ["SWC(CRNS)", "SWC(NEPTOON_UTS)", "D86"]
DEFAULT_METRICS_MODEL = ["SWC(SWAP)"]
DEFAULT_SMT_DEPTHS = ["weighted"] if "weighted" in smt_depths else smt_depths[:1]

# Inside a group the source is already named by the group, so the sub-options only
# carry what distinguishes them.
SUB_LABELS = {
    "SWC(CRNS)": "generelle Kalibrierung",
    "SWC(CRNS_old)": "frühere Kalibrierung",
    "SWC(NEPTOON_DES)": "Auswertung nach Desilets",
    "SWC(NEPTOON_UTS)": "Auswertung nach UTS",
    "D86": "Eindringtiefe",
    "SWC(SWAP)": "tiefengewichtet",
    **{metric: depth for metric, depth in SWAP_DEPTH_METRICS.items()},
}

with st.expander("Datenauswahl", expanded=True):
    col_crns, col_model, col_other = st.columns(3)

    with col_crns:
        use_crns = st.checkbox("**Messung via CRNS**", value=True, key="group_crns")
        crns_sel = (
            st.pills(
                "Auswertung",
                options=CRNS_METRICS,
                format_func=lambda m: SUB_LABELS[m],
                default=DEFAULT_METRICS_CRNS,
                selection_mode="multi",
                label_visibility="collapsed",
                key="metrics_crns",
            )
            if use_crns
            else []
        )

    with col_model:
        use_model = st.checkbox("**Modell SWAP**", value=True, key="group_model")
        model_sel = (
            st.pills(
                "Tiefe der Modellwerte",
                options=MODEL_METRICS,
                format_func=lambda m: SUB_LABELS[m],
                default=DEFAULT_METRICS_MODEL,
                selection_mode="multi",
                label_visibility="collapsed",
                key="metrics_model",
            )
            if use_model
            else []
        )

    with col_other:
        use_smt = st.checkbox(
            "**Bodenfeuchtesensoren (SMT)**", value=False, key="group_smt"
        )
        # The sensor depths are the group's sub-options - no extra metric pill.
        selected_smt_depths = (
            st.pills(
                "Sensortiefen",
                options=smt_depths,
                format_func=smt_depth_label,
                default=DEFAULT_SMT_DEPTHS,
                selection_mode="multi",
                label_visibility="collapsed",
                key="metrics_smt_depths",
            )
            if use_smt and smt_depths
            else []
        )
        if use_smt and not smt_depths:
            st.caption("Keine Sensortiefen in den Daten gefunden.")
        st.markdown("**Schnee**")
        snow_mask_toggle()

    selected_metrics = list(crns_sel) + list(model_sel)
    if selected_smt_depths:
        selected_metrics.append("SWC(SMT)")
    selected_smt_depths = list(selected_smt_depths)

if not selected_metrics:
    st.info("Wähle mindestens eine Gruppe und darin eine Variable.")
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
        st.warning(f"Modellwerte SWAP ({depth}) sind derzeit nicht verfügbar.")

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
    st.warning("Für die aktuelle Variablenauswahl wurden keine Daten gefunden.")
    st.stop()


combined_for_range = pd.concat(list(metric_frames.values()), axis=1)
combined_valid = combined_for_range.dropna(how="all")
if combined_valid.empty:
    st.warning("Für die aktuelle Variablenauswahl wurden keine Daten gefunden.")
    st.stop()

# --- Shared time window (set here or on the overview page) --------------------
data_min_date = combined_valid.index.min().date()
data_max_date = combined_valid.index.max().date()


def _sync_window_from_pills():
    horizon = st.session_state.station_horizon
    if horizon is None:
        # Deselected pill: keep the dates, they are now an own period.
        set_shared_window(
            st.session_state.station_start, st.session_state.station_end, None
        )
        return
    start, end = window_from_horizon(horizon, data_min_date, data_max_date)
    st.session_state.station_start = start
    st.session_state.station_end = end
    set_shared_window(start, end, horizon)


def _sync_window_from_dates():
    # Own start/end: no horizon stays selected.
    st.session_state.station_horizon = None
    set_shared_window(
        st.session_state.station_start, st.session_state.station_end, None
    )


win_start_default, win_end_default, win_horizon = get_shared_window(
    data_min_date, data_max_date
)
st.session_state.setdefault("station_horizon", win_horizon)
st.session_state.station_start = win_start_default
st.session_state.station_end = win_end_default

control_cols = st.columns([3, 1.1, 1.1, 1], vertical_alignment="bottom")
with control_cols[0]:
    st.pills(
        "Zeithorizont",
        options=list(HORIZON_MAP.keys()),
        key="station_horizon",
        selection_mode="single",
        on_change=_sync_window_from_pills,
    )
control_cols[1].date_input(
    "Start",
    min_value=data_min_date,
    max_value=data_max_date,
    key="station_start",
    on_change=_sync_window_from_dates,
)
control_cols[2].date_input(
    "Ende",
    min_value=data_min_date,
    max_value=data_max_date,
    key="station_end",
    on_change=_sync_window_from_dates,
)
if control_cols[3].button(
    "Zurücksetzen",
    icon=":material/restart_alt:",
    help="Gesamte Zeitreihe und Standardauswahl der Variablen wiederherstellen.",
):
    reset_shared_window(data_min_date, data_max_date)
    # Widget keys cannot be assigned after their widget was drawn this run; dropping
    # them makes each widget fall back to its default on the next run.
    for stale in (
        "station_start",
        "station_end",
        "station_horizon",
        "group_crns",
        "group_model",
        "group_smt",
        "metrics_crns",
        "metrics_model",
        "metrics_smt_depths",
    ):
        st.session_state.pop(stale, None)
    st.rerun()

if st.session_state.station_start > st.session_state.station_end:
    st.error("Das Startdatum muss vor dem Enddatum liegen.")
    st.stop()

window_start = pd.to_datetime(st.session_state.station_start)
window_end = pd.to_datetime(st.session_state.station_end)
set_shared_window(
    st.session_state.station_start,
    st.session_state.station_end,
    st.session_state.station_horizon,
)

st.caption(
    "Die Diagramme zeigen den gewählten Zeitraum; die schmale Leiste darunter enthält "
    "die gesamte Zeitreihe zum Ziehen und Verschieben."
)

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
                fillcolor=FILL_D86,
                line=dict(color=COLOR_D86, width=0),
                fill="tozeroy",
                opacity=ALPHA_D86,
            ),
            secondary_y=True,
        )

    if "SWC(SWAP)" in selected_metrics and station_swap is not None:
        fig.add_trace(
            go.Scatter(
                x=station_swap.index,
                y=to_plot_unit(station_swap),
                mode="lines",
                name=METRIC_LABELS["SWC(SWAP)"],
                line=dict(color=COLOR_SWAP, dash="dash"),
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
                y=to_plot_unit(depth_series),
                mode="lines",
                name=METRIC_LABELS[metric],
                line=dict(
                    color=SWAP_DEPTH_COLORS.get(SWAP_DEPTH_METRICS[metric], "#807DBA"),
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
                y=to_plot_unit(station_crns),
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
                y=to_plot_unit(station_crns_old),
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
                y=to_plot_unit(station_neptoon_des),
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
                y=to_plot_unit(station_neptoon_uts),
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
                    y=to_plot_unit(station_smt[smt_col]),
                    mode="lines",
                    name=f"Bodenfeuchte (Sensor SMT, {smt_depth_label(depth)})",
                    line=dict(color=smt_color_map.get(depth, "#737373"), dash="dot"),
                    opacity=TRACE_ALPHA,
                ),
                secondary_y=False,
            )

    fig.update_yaxes(title_text=moisture_label(), secondary_y=False)
    if "D86" in selected_metrics:
        fig.update_yaxes(
            title_text="Eindringtiefe (cm)", range=[-120, -0], secondary_y=True
        )

    # Window shown in the main plot; the slider below always holds the full series.
    view_start = max(window_start, station_start)
    view_end = min(window_end, station_end)
    if view_start >= view_end:
        view_start, view_end = station_start, station_end

    fig.update_layout(
        title=(
            f"{station_name_map[station]}<br>"
            f"<sup>{station_start.date()} bis {station_end.date()}</sup>"
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.35,
            xanchor="center",
            x=0.5,
        ),
        height=520,
        margin=dict(l=40, r=20, t=50, b=120),
    )

    # This station's own snow phases - the same periods masking removes above.
    add_snow_shading(
        fig,
        station_snow_periods(snow_flags, station),
        xrange=(station_start, station_end),
    )
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
            to_plot_unit(theta) if theta is not None and not pd.isna(theta) else theta,
            crns_index=cal_index,
            xrange=(station_start, station_end),
            secondary_y=False,
        )

    add_range_slider(
        fig,
        full_range=(station_start, station_end),
        window=(view_start, view_end),
    )

    cell = cols[i % NUM_COLS].container(border=True)
    cell.plotly_chart(
        fig, width="stretch", key=f"station_{station}", config=PLOT_CONFIG
    )

glossary_expander()
