# -*- coding: utf-8 -*-

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_sources import (
    HORIZON_MAP,
    PRIMARY_CRNS,
    STOCKS,
    SWAP_START,
    construction_warning,
    URL_LOCATIONS,
    URL_SNOW_FLAGS,
    PLOT_CONFIG,
    add_calibration_marker,
    add_range_slider,
    add_snow_shading,
    get_series,
    get_shared_stations,
    get_shared_window,
    glossary_expander,
    hover_template,
    load_locations,
    load_series,
    load_snow_flags,
    maybe_mask_snow,
    moisture_label,
    reset_shared_window,
    series_for,
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

st.title("Messreihen Einzelner Standorte")
# Which sources are named here follows the profile - the sensors are not part of
# every one, so the sentence must not promise data the page cannot show.
_SOURCE_TEXTS = [
    "auf der Messung mit kosmischen Neutronensensoren (Messung via CRNS)",
    *(
        ["auf punktuellen Bodenfeuchtesensoren (SMT)"]
        if series_for("smt")
        else []
    ),
    "auf dem Bodenwasserhaushaltsmodell [SWAP](https://www.swap.alterra.nl/)",
]
st.write(
    "Die Seite dient der detaillierten Darstellung der Daten an Einzelstandorten. "
    "Die dargestellten Daten beruhen "
    + ", ".join(_SOURCE_TEXTS[:-1])
    + f" und {_SOURCE_TEXTS[-1]}. "
    "Die Eindringtiefe der Neutronenmessung hängt unter anderem von der Bodenfeuchte selbst "
    "ab und ändert sich daher laufend. Damit Messung und Modell vergleichbar bleiben, kann das "
    "Modellergebnis ebenfalls über diese Eindringtiefe gemittelt werden (tiefengewichtet). "
    "Grundsätzliche Informationen zu den Messungen finden Sie unten auf der Seite."
)

# Which series exist, what they are called and how they are drawn all live in the
# registry in data_sources.py, filtered by the active profile. Only the per-depth
# SMT ramp stays here, because those traces are one per sensor depth, not per series.
SMT_GRAY_SCALE = ["#1F1F1F", "#4D4D4D", "#737373", "#A6A6A6", "#D0D0D0"]


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
snow_flags = load_snow_flags(URL_SNOW_FLAGS)


def frame_for(series):
    """Full frame for one registry entry, with its per-series treatment applied."""
    df = load_series(series.key)
    if series.clip_start:
        df = df.loc[SWAP_START:]
    if series.snow_masked:
        # Snow on the ground biases the neutron count, so every CRNS-derived series
        # is blanked out during a snow phase; model and in-soil sensors stay untouched.
        df = maybe_mask_snow(df, snow_flags)
    return df


# The station list always comes from the primary CRNS series, loaded whether or not
# it is selected; the calibration marker snaps onto its sample grid too.
crns_primary = frame_for(get_series(PRIMARY_CRNS))

# The sensors are not part of every profile, and their depths have to be known
# before the selector is drawn.
smt_series = next(iter(series_for("smt")), None)
SMT = rename_smt_columns(load_series(smt_series.key)) if smt_series else pd.DataFrame()
smt_depths = sorted(
    {col.split("_SMT_", 1)[1] for col in SMT.columns if "_SMT_" in col},
    key=_depth_sort_key,
)

available_stations = [station for station in STOCKS if station in crns_primary.columns]
# All stations are shown; the ones picked on the overview page come first.
preferred = [s for s in get_shared_stations([]) if s in available_stations]
selected_stations = preferred + [s for s in available_stations if s not in preferred]

station_name_map = {
    station: station_label(station, locs) for station in selected_stations
}

DEFAULT_SMT_DEPTHS = ["weighted"] if "weighted" in smt_depths else smt_depths[:1]


def _metric_pills(label: str, options, key: str):
    """Pill row for one group. A group with a single option needs no row - the
    group checkbox already names it."""
    defaults = [s.key for s in options if s.default]
    if len(options) < 2:
        return defaults
    return st.pills(
        label,
        options=[s.key for s in options],
        format_func=lambda k: get_series(k).pill,
        default=defaults,
        selection_mode="multi",
        label_visibility="collapsed",
        key=key,
    )


crns_options = series_for("crns")
model_options = series_for("model")

with st.expander("Datenauswahl", expanded=True):
    col_crns, col_model, col_other = st.columns(3)

    with col_crns:
        use_crns = st.checkbox("**Messung via CRNS**", value=True, key="group_crns")
        crns_sel = (
            _metric_pills("Auswertung", crns_options, "metrics_crns")
            if use_crns
            else []
        )

    with col_model:
        use_model = st.checkbox("**Modell SWAP**", value=True, key="group_model")
        model_sel = (
            _metric_pills("Tiefe der Modellwerte", model_options, "metrics_model")
            if use_model
            else []
        )

    with col_other:
        if smt_series:
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
        else:
            selected_smt_depths = []
        st.markdown("**Schnee**")
        snow_mask_toggle()

    selected_metrics = list(crns_sel) + list(model_sel)
    if selected_smt_depths and smt_series:
        selected_metrics.append(smt_series.key)
    selected_smt_depths = list(selected_smt_depths)

if not selected_metrics:
    st.info("Wähle mindestens eine Gruppe und darin eine Variable.")
    st.stop()

smt_color_map = _smt_color_map(selected_smt_depths)

# One frame per selected series, in draw order. A source that is unreachable only
# drops its own trace. reindex (not direct selection) so stations missing from a
# source - e.g. WUS, which has no SWAP run - yield NaN columns, not a KeyError.
frames = {}
for series in series_for():
    if series.key not in selected_metrics or series.group == "smt":
        continue
    try:
        frames[series.key] = frame_for(series).reindex(columns=selected_stations)
    except Exception:
        st.warning(f"{series.label} ist derzeit nicht verfügbar.")

# SMT is one series with many columns - one per station and sensor depth - so it
# keeps its own column selection rather than being reindexed onto the stations.
smt_cols = []
if smt_series and smt_series.key in selected_metrics:
    smt_cols = [
        f"{station}_SMT_{depth}"
        for station in selected_stations
        for depth in selected_smt_depths
        if f"{station}_SMT_{depth}" in SMT.columns
    ]

metric_frames = dict(frames)
if smt_cols:
    metric_frames[smt_series.key] = SMT[smt_cols]

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
    has_d86 = any(get_series(key).axis == "d86" for key in frames)
    fig = make_subplots(specs=[[{"secondary_y": has_d86}]])

    station_frames = [
        frame[[station]] for frame in frames.values() if station in frame.columns
    ]
    smt_station_cols = (
        [col for col in smt_cols if col.startswith(f"{station}_SMT_")]
        if smt_cols
        else []
    )
    if smt_station_cols:
        station_frames.append(SMT[smt_station_cols])

    if not station_frames:
        continue

    station_combined = pd.concat(station_frames, axis=1)
    station_valid = station_combined.dropna(how="all")
    if station_valid.empty:
        continue

    station_start = station_valid.index.min()
    station_end = station_valid.index.max()

    # The calibration marker snaps onto the primary CRNS grid, whether or not that
    # series is selected.
    station_crns = _station_series(crns_primary, station, station_start, station_end)
    station_smt = (
        SMT.loc[station_start:station_end, smt_station_cols]
        if smt_station_cols
        else pd.DataFrame(index=station_valid.index)
    )

    # One pass over the registry in draw order; every special case - the downward
    # D86 fill, the dashed model runs - is a field on the series itself.
    for series in series_for():
        if series.key not in frames:
            continue
        values = _station_series(
            frames[series.key], station, station_start, station_end
        )
        if values is None or values.dropna().empty:
            continue
        line = dict(color=series.color, dash=series.dash)
        if series.line_width is not None:
            line["width"] = series.line_width
        fig.add_trace(
            go.Scatter(
                x=values.index,
                y=-values if series.negate else to_plot_unit(values),
                mode="lines",
                name=series.label,  # terse, for the horizontal legend
                hovertemplate=hover_template(series),  # spelled out, for the tooltip
                line=line,
                opacity=series.opacity,
                fill=series.fill,
                fillcolor=series.fill_color,
            ),
            secondary_y=(series.axis == "d86"),
        )

    # The sensors are one trace per depth, shaded along a grey ramp.
    if smt_series and not station_smt.empty:
        for smt_col in smt_station_cols:
            depth = smt_col.split("_SMT_", 1)[1]
            depth_text = smt_depth_label(depth)
            fig.add_trace(
                go.Scatter(
                    x=station_smt.index,
                    y=to_plot_unit(station_smt[smt_col]),
                    mode="lines",
                    name=f"SWC (SMT, {depth_text})",
                    hovertemplate=hover_template(
                        smt_series, f"{smt_series.hover}, {depth_text})"
                    ),
                    line=dict(
                        color=smt_color_map.get(depth, "#737373"), dash=smt_series.dash
                    ),
                    opacity=smt_series.opacity,
                ),
                secondary_y=False,
            )

    fig.update_yaxes(title_text=moisture_label(), secondary_y=False)
    if has_d86:
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
