import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import date
from typing import Optional


def construction_warning():
    """Site-wide 'under construction / preliminary data' banner."""
    st.warning(
        "Diese Seite befindet sich im Aufbau. Alle Daten und Darstellungen sind "
        "vorläufig und können sich noch ändern."
    )


# Local FIles
# from pathlib import Path
# LOCAL_DATA_DIR = Path(__file__).resolve().parent / "data"
#
# URL_SWC_CRNS = str(LOCAL_DATA_DIR / "swc-from-crns.txt")
# URL_SWC_SWAP = str(LOCAL_DATA_DIR / "swc-from-swap.txt")
# URL_D86_CRNS = str(LOCAL_DATA_DIR / "d86-from-crns.txt")
# URL_LOCATIONS = str(LOCAL_DATA_DIR / "metadata-locations.csv")

# Remote A:
# BASE_URL = "https://b2drop.eudat.eu/public.php/dav/files/efStHSPAM8HLc92"
# URL_SWC_CRNS = f"{BASE_URL}/products/swc-from-crns.txt"
# URL_SWC_SWAP = f"{BASE_URL}/products/swc-from-swap.txt"
# URL_D86_CRNS = f"{BASE_URL}/products/d86-from-crns.txt"
# URL_LOCATIONS = f"{BASE_URL}/metadata/metadata-locations.csv"

# REMOTE NEW:
BASE_URL = "https://b2drop.eudat.eu//public.php/dav/files/yr5d6i72cCacYpH"
# URL_SWC_CRNS = f"{BASE_URL}/swc-from-crns.txt"
URL_SWC_CRNS = f"{BASE_URL}/swc-from-crns.txt"
URL_SWC_CRNS_old = f"{BASE_URL}/swc-from-crns_oldpreproc.txt"
URL_SWC_SWAP = f"{BASE_URL}/swc-from-swap.txt"
URL_D86_CRNS = f"{BASE_URL}/d86-from-crns.txt"
URL_LOCATIONS = f"{BASE_URL}/metadata-locations.csv"
URL_SWC_SMT = f"{BASE_URL}/vwc-from-smt_daily.txt"
URL_SWC_NEPTOON_DES = f"{BASE_URL}/swc-neptoon_DES.txt"
URL_SWC_NEPTOON_UTS = f"{BASE_URL}/swc-neptoon_UTS.txt"
URL_SWC_NEPTOON_DES_old = f"{BASE_URL}/swc-neptoon_DES_oldpreproc.txt"
URL_SWC_NEPTOON_UTS_old = f"{BASE_URL}/swc-neptoon_UTS_oldpreproc.txt"
URL_SNOW_FLAGS = f"{BASE_URL}/snow-flags.csv"
URL_SWAP_SM_0_30 = f"{BASE_URL}/swc-from-swap-mean-0_30.txt"
URL_SWAP_SM_0_100 = f"{BASE_URL}/swc-from-swap-mean-0_100.txt"
URL_SWAP_SM_0_200 = f"{BASE_URL}/swc-from-swap-mean-0_200.txt"
# Per-station daily water balance + the 1994-2024 day-of-year normals.

URL_BALANCE_NORMAL_DIR = "https://b2drop.eudat.eu//public.php/dav/files/7dHbNH26QT2nCef"
URL_WATER_BALANCE = f"{URL_BALANCE_NORMAL_DIR}/{{station}}.csv"
# SWAP soil-moisture depth averages overlaid on the SMI page's secondary axis.
SWAP_SM_DEPTHS = {
    "0–30 cm": URL_SWAP_SM_0_30,
    "0–1 m": URL_SWAP_SM_0_100,
    "0–2 m": URL_SWAP_SM_0_200,
}

STOCKS = [
    "BEE",
    "BOO",
    "DED",
    "DUB",
    "FUE",
    "GOL",
    "KH",
    "LIN",
    "MQ",
    "OEH",
    "PAU",
    "TRE",
    "WUS",
]

DEFAULT_STOCKS = ["OEH", "MQ", "LIN"]


@st.cache_data(ttl=12 * 3600)
def load_time_series(url: str, sep: Optional[str] = "\t") -> pd.DataFrame:
    df = pd.read_csv(url, sep=sep, engine="python", na_values="na")
    if sep == "\t" and df.shape[1] == 1:
        df = pd.read_csv(url, sep=",", engine="python", na_values="na")
    if "datetime" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "datetime"})
    if "datetime" not in df.columns and "Date_Time" in df.columns:
        df = df.rename(columns={"Date_Time": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(None)
    df = df.set_index("datetime")
    df.index.name = "Date"
    df = df.rename(columns={"QUI": "DED", "MQ35": "MQ"})
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=12 * 3600)
def load_locations(url: str = URL_LOCATIONS, sep: Optional[str] = "\t") -> pd.DataFrame:
    df = pd.read_csv(url, sep=sep, engine="python")
    if sep == "\t" and df.shape[1] == 1:
        df = pd.read_csv(url, sep=",", engine="python")
    # replace in id MQ35 with MQ
    df["id"] = df["id"].str.replace("MQ35", "MQ")
    return df.set_index("id")


def normalize_stocks(stocks, allowed_stocks=STOCKS):
    # Keep only known station IDs, preserve order, and remove duplicates.
    normalized = []
    seen = set()
    for stock in stocks:
        value = str(stock).upper().strip()
        if value in allowed_stocks and value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def selected_max_date(df: pd.DataFrame, selected_tickers) -> date:
    selected_cols = [ticker for ticker in selected_tickers if ticker in df.columns]
    if selected_cols:
        valid_selected = df[selected_cols].dropna(how="all")
        if not valid_selected.empty:
            return valid_selected.index.max().date()
        # Do not fall back to unrelated stations when current selection has no data.
        return df.index.min().date()

    valid_all = df.dropna(how="all")
    if not valid_all.empty:
        return valid_all.index.max().date()
    return df.index.max().date()


def selected_min_date(df: pd.DataFrame, selected_tickers) -> date:
    selected_cols = [ticker for ticker in selected_tickers if ticker in df.columns]
    if selected_cols:
        first_dates = [
            df[col].dropna().index.min()
            for col in selected_cols
            if not df[col].dropna().empty
        ]
        if first_dates:
            return min(first_dates).date()

    valid_all = df.dropna(how="all")
    if not valid_all.empty:
        return valid_all.index.min().date()
    return df.index.min().date()


SNOW_FILL = "rgba(120, 120, 120, 0.20)"


@st.cache_data(ttl=12 * 3600)
def load_snow_flags(url: str = URL_SNOW_FLAGS) -> pd.DataFrame:
    """Daily per-site snow flags (incl. an ``any_site`` aggregate column).

    Fails soft: if the file is missing/unreachable, return an empty frame so the
    plots simply render without snow shading instead of breaking the page.
    """
    try:
        df = pd.read_csv(url, sep=",", engine="python")
    except Exception:
        return pd.DataFrame()
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(None)
    df = df.set_index("datetime").sort_index()
    df.index.name = "Date"
    return df


def snow_periods(snow_df: pd.DataFrame, column: str = "any_site"):
    """Contiguous date ranges where ``column`` is True.

    Returns a list of (start, end) Timestamps. Consecutive flagged days (gap of
    one day or less) are merged; each period is extended by one day at the end so
    isolated single-day flags stay visible when shaded.
    """
    if snow_df is None or column not in snow_df.columns:
        return []
    flags = snow_df[column].astype(str).str.strip().str.lower().eq("true")
    flagged = flags[flags].index
    if len(flagged) == 0:
        return []
    periods = []
    start = prev = flagged[0]
    for cur in flagged[1:]:
        if (cur - prev) <= pd.Timedelta(days=1):
            prev = cur
            continue
        periods.append((start, prev + pd.Timedelta(days=1)))
        start = prev = cur
    periods.append((start, prev + pd.Timedelta(days=1)))
    return periods


def add_snow_shading(fig, periods, *, xrange=None, add_legend=True):
    """Shade snow phases as background rectangles on a Plotly figure.

    ``xrange`` (lo, hi) clips the rectangles to the visible window so the shapes
    never expand the x-axis autorange. Works on plain and secondary-y figures
    because shapes are anchored to ``yref="paper"``.
    """
    if not periods:
        return fig
    if xrange is not None:
        lo, hi = xrange
        clipped = []
        for start, end in periods:
            if end < lo or start > hi:
                continue
            clipped.append((max(start, lo), min(end, hi)))
        periods = clipped
    if not periods:
        return fig
    for start, end in periods:
        fig.add_shape(
            type="rect",
            xref="x",
            yref="paper",
            x0=start,
            x1=end,
            y0=0,
            y1=1,
            fillcolor=SNOW_FILL,
            line_width=0,
            layer="below",
        )
    if add_legend:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, symbol="square", color=SNOW_FILL),
                name="Schneephase",
                hoverinfo="skip",
            )
        )
    return fig


def add_calibration_marker(
    fig,
    caldate,
    theta=None,
    *,
    crns_index=None,
    xrange=None,
    secondary_y=False,
    color="#000000",
):
    """Mark the local CRNS calibration as a point at (caldate, theta_eff).

    ``caldate`` is snapped onto ``crns_index`` (nearest sample) so the point lands
    exactly on a plotted CRNS timestep: CRNS is backward-aggregated, so e.g. a
    12:00 calibration on a daily series aligns to the bounding 00:00 stamp (and
    likewise to the last 6 h stamp on 6-hourly data). The marker sits on the SWC
    axis at the theta value; an annotation labels the calibration date.
    """
    caldate = pd.to_datetime(caldate, errors="coerce")
    if pd.isna(caldate) or theta is None or pd.isna(theta):
        return fig
    try:
        theta = float(theta)
    except (TypeError, ValueError):
        return fig
    caldate_dt = caldate
    calstart = caldate_dt - pd.Timedelta(hours=2)
    calend = caldate_dt + pd.Timedelta(hours=2)

    # if crns_index is not None and len(crns_index) > 0:
    #    pos = crns_index.get_indexer([caldate], method="pad")[0]
    #    if pos != -1:
    #        caldate = crns_index[pos]

    if xrange is not None:
        lo, hi = xrange
        if caldate < lo or caldate > hi:
            return fig

    label = f"Lokale Kalibrierung am {caldate_dt:%Y-%m-%d} von {calstart:%H:%M} bis {calend:%H:%M} Uhr"
    marker = go.Scatter(
        x=[caldate],
        y=[theta],
        mode="markers",
        name="Lokale Kalibrierung",
        marker=dict(symbol="circle-open-dot", size=12, color=color, line=dict(width=0)),
        hovertemplate=f"{label}<br>θ={theta:.2f}<extra></extra>",
    )
    try:
        # secondary_y is only valid on make_subplots figures; plain figures raise.
        fig.add_trace(marker, secondary_y=secondary_y)
    except Exception:
        fig.add_trace(marker)

    fig.add_vline(
        x=caldate,
        line=dict(color=color, width=1, dash="dot"),
        name="Lokale Kalibrierung",
    )
    # fig.add_annotation(
    #    x=caldate,
    #    y=theta,
    #    xref="x",
    #    yref="y",
    #    text=label,
    #    showarrow=True,
    #    arrowhead=0,
    #    ax=0,
    #    ay=-25,
    #    font=dict(size=10, color=color),
    # )
    return fig


# --- Soil-Moisture-Index (empirical CDF) -------------------------------------
# The SMI is the empirical non-exceedance probability of the actual (unsmoothed)
# SWAP soil moisture within the reference distribution. Every calendar day has its
# own CDF, pooled from a +/-7 d window around that day over all reference years
# (Weibull plotting positions).
#
# Because the CDF is empirical it is bounded: the ``*_first_step`` / ``*_last_step``
# files hold the lowest / highest resolvable SMI per station and day. Soil moisture
# at or beyond those steps only yields a bound, not an exact SMI (see
# ``smi_censoring``). ``*_lt`` is the full history, ``smi_<depth>.txt`` the recent
# part of it.
SMI_REFERENCE_PERIOD = "1994–2024"
SMI_POOL_HALFWIDTH_DAYS = 7

SMI_DEPTHS = {
    "0–30 cm": "0_30cm",
    "0–100 cm": "0_100cm",
    "0–200 cm": "0_200cm",
}
DEFAULT_SMI_DEPTH = "0–100 cm"

# The SWAP soil moisture an SMI depth is derived from -> keys of SWAP_SM_DEPTHS.
# Only that depth may be overlaid on the SMI page; the SMI would otherwise be
# compared against soil moisture from a different profile.
SMI_SWAP_DEPTH = {
    "0_30cm": "0–30 cm",
    "0_100cm": "0–1 m",
    "0_200cm": "0–2 m",
}

# Values are stored with 4 decimals, so an exact step hit compares equal.
SMI_STEP_TOL = 1e-6


def _smi_url(depth_key: str, suffix: str = "") -> str:
    return f"{BASE_URL}/smi_{depth_key}{suffix}.txt"


@st.cache_data(ttl=12 * 3600)
def load_smi(depth_key: str) -> pd.DataFrame:
    """Full SMI history for one depth."""
    return load_time_series(_smi_url(depth_key, "_lt"))


@st.cache_data(ttl=12 * 3600)
def load_smi_steps(depth_key: str):
    """(first_step, last_step): lowest / highest resolvable SMI per station and day."""
    return (
        load_time_series(_smi_url(depth_key, "_first_step")),
        load_time_series(_smi_url(depth_key, "_last_step")),
    )


def smi_censoring(value, first_step=None, last_step=None):
    """Whether an SMI value sits on the empirical CDF's lowest / highest step.

    Returns ``"low"`` (soil moisture at or below the driest reference sample, so the
    SMI is only an upper bound), ``"high"`` (only a lower bound), or ``None`` when
    the SMI resolves normally.
    """
    if value is None or pd.isna(value):
        return None
    if (
        first_step is not None
        and not pd.isna(first_step)
        and value <= first_step + SMI_STEP_TOL
    ):
        return "low"
    if (
        last_step is not None
        and not pd.isna(last_step)
        and value >= last_step - SMI_STEP_TOL
    ):
        return "high"
    return None


# --- Soil-Moisture-Index bands (US Drought Monitor style, mirrored to the wet end)
# SMI in [0, 1]; lower = drier. (lo, hi, key); hi is exclusive except the top band.
# The wet classes mirror the drought thresholds (0.02/0.05/0.10/0.20/0.30) around
# the middle, so 0.70-1.00 is graded the same way 0.00-0.30 is.
SMI_BANDS = [
    (0.00, 0.02, "exceptional"),
    (0.02, 0.05, "extreme"),
    (0.05, 0.10, "severe"),
    (0.10, 0.20, "moderate"),
    (0.20, 0.30, "abnormally_dry"),
    (0.30, 0.70, "normal"),
    (0.70, 0.80, "abnormally_wet"),
    (0.80, 0.90, "moderate_wet"),
    (0.90, 0.95, "severe_wet"),
    (0.95, 0.98, "extreme_wet"),
    (0.98, 1.01, "exceptional_wet"),
]
SMI_BAND_LABELS = {
    "exceptional": "außergewöhnliche Dürre",
    "extreme": "extreme Dürre",
    "severe": "schwere Dürre",
    "moderate": "moderate Dürre",
    "abnormally_dry": "ungewöhnlich trocken",
    "normal": "normal",
    "abnormally_wet": "ungewöhnlich nass",
    "moderate_wet": "moderate Nässe",
    "severe_wet": "starke Nässe",
    "extreme_wet": "extreme Nässe",
    "exceptional_wet": "außergewöhnliche Nässe",
}
# ColorBrewer RdYlBu-11 (flagged colour-blind-safe): dark red = driest, pale yellow
# = normal, dark blue = wettest. Brightness varies monotonically towards both ends.
SMI_BAND_COLORS = {
    "exceptional": "#7b0000",
    "extreme": "#d7191c",
    "severe": "#fdae61",
    "moderate": "#fee090",
    "abnormally_dry": "#fff8e6",
    "normal": "#dfdfdf",
    "abnormally_wet": "#e0f3f8",
    "moderate_wet": "#abd9e9",
    "severe_wet": "#74add1",
    "extreme_wet": "#4575b4",
    "exceptional_wet": "#313695",
}
SMI_NA_COLOR = "#cccccc"


def smi_band(value):
    """Map an SMI value to (key, German label, hex colour). NaN -> grey 'no data'."""
    if value is None or pd.isna(value):
        return (None, "keine Daten", SMI_NA_COLOR)
    for lo, hi, key in SMI_BANDS:
        if lo <= value < hi:
            return (key, SMI_BAND_LABELS[key], SMI_BAND_COLORS[key])
    # value at/above the top of the scale -> wettest band
    key = SMI_BANDS[-1][2]
    return (key, SMI_BAND_LABELS[key], SMI_BAND_COLORS[key])


def add_smi_bands(fig, *, opacity=0.18):
    """Shade the SMI drought bands as horizontal background stripes.

    Uses ``add_shape`` with ``xref="paper"`` / ``yref="y"`` so it works on plain
    and secondary-y figures and spans the full width without touching autorange.
    """
    for lo, hi, key in SMI_BANDS:
        fig.add_shape(
            type="rect",
            xref="paper",
            yref="y",
            x0=0,
            x1=1,
            y0=lo,
            y1=min(hi, 1.0),
            fillcolor=SMI_BAND_COLORS[key],
            opacity=opacity,
            line_width=0,
            layer="below",
        )
    return fig


