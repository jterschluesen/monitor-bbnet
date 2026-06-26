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
URL_SMI_UFZ = f"{BASE_URL}/smi-from-swap-whole.txt"
URL_SWAP_SM_0_30 = f"{BASE_URL}/swc-from-swap-mean-0_30.txt"
URL_SWAP_SM_0_100 = f"{BASE_URL}/swc-from-swap-mean-0_100.txt"
URL_SWAP_SM_100_200 = f"{BASE_URL}/swc-from-swap-mean-100_200.txt"
# Per-station daily water balance + the 1994-2024 day-of-year normals.

URL_BALANCE_NORMAL_DIR = "https://b2drop.eudat.eu//public.php/dav/files/7dHbNH26QT2nCef"
URL_WATER_BALANCE = f"{URL_BALANCE_NORMAL_DIR}/{{station}}.csv"
# Drought-index sources for the SMI page. Extend with one entry per new source.
SMI_SOURCES = {
    "SMI (14 Tage)": URL_SMI_UFZ,
}
# SWAP soil-moisture depth averages overlaid on the SMI page's secondary axis.
SWAP_SM_DEPTHS = {
    "0–30 cm": URL_SWAP_SM_0_30,
    "0–100 cm (1 m)": URL_SWAP_SM_0_100,
    "100–200 cm (2 m)": URL_SWAP_SM_100_200,
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


# --- Soil-Moisture-Index drought bands (US Drought Monitor style) -------------
# SMI in [0, 1]; lower = drier. (lo, hi, key); hi is exclusive except the top band.
SMI_BANDS = [
    (0.00, 0.02, "exceptional"),
    (0.02, 0.05, "extreme"),
    (0.05, 0.10, "severe"),
    (0.10, 0.20, "moderate"),
    (0.20, 0.30, "abnormally_dry"),
    (0.30, 1.01, "no_drought"),
]
SMI_BAND_LABELS = {
    "exceptional": "außergewöhnliche Dürre",
    "extreme": "extreme Dürre",
    "severe": "schwere Dürre",
    "moderate": "moderate Dürre",
    "abnormally_dry": "ungewöhnlich trocken",
    "no_drought": "keine Dürre",
}
# CVD-safe RdYlBu-derived sequence (ColorBrewer flags RdYlBu colour-blind-safe):
# dark red = worst drought, blue = wettest. Brightness also varies monotonically.
SMI_BAND_COLORS = {
    "exceptional": "#7b0000",
    "extreme": "#d7191c",
    "severe": "#fdae61",
    "moderate": "#fee090",
    "abnormally_dry": "#abd9e9",
    "no_drought": "#2c7bb6",
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


