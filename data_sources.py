import io
import urllib.request

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


def construction_warning():
    """Site-wide 'under construction / preliminary data' banner."""
    st.warning(
        "Diese Seite befindet sich im Aufbau. Alle Daten und Darstellungen sind "
        "vorläufig und können sich noch ändern."
    )


# --- Reading sources ---------------------------------------------------------
# All data come from the remote directory. A dead host must fail fast and with a
# readable message instead of hanging the page and dumping a URLError traceback.
REMOTE_TIMEOUT = 20  # seconds per file


def _source_bytes(url: str, *, required: bool = True):
    """Raw content of a source file.

    ``required=False`` returns ``None`` instead of stopping the page, for optional
    files whose absence only drops a single feature (e.g. the snow flags).
    """
    text = str(url)
    if not text.lower().startswith(("http://", "https://")):
        return Path(text).read_bytes()
    try:
        with urllib.request.urlopen(text, timeout=REMOTE_TIMEOUT) as response:
            return response.read()
    except Exception as exc:
        if not required:
            return None
        st.error(
            "Die Daten sind derzeit nicht abrufbar: Das Online-Verzeichnis "
            f"antwortet nicht ({text.rsplit('/', 1)[-1]}). Bitte später erneut "
            "versuchen.",
            icon=":material/cloud_off:",
        )
        st.caption(f"Technische Meldung: {type(exc).__name__}: {exc}")
        st.stop()
        # Outside a Streamlit run st.stop() is a no-op; do not return None silently.
        raise RuntimeError(f"Quelle nicht erreichbar: {text}") from exc


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
URL_SWC_CRNS = f"{BASE_URL}//swc-neptoon_DES_general.txt"
URL_SWC_CRNS_Maik = f"{BASE_URL}/swc-from-crns.txt"
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
    # "WUS",
]

DEFAULT_STOCKS = ["OEH", "LIN"]


@st.cache_data(ttl=12 * 3600)
def load_time_series(url: str, sep: Optional[str] = "\t") -> pd.DataFrame:
    raw = _source_bytes(url)
    df = pd.read_csv(io.BytesIO(raw), sep=sep, engine="python", na_values="na")
    if sep == "\t" and df.shape[1] == 1:
        df = pd.read_csv(io.BytesIO(raw), sep=",", engine="python", na_values="na")
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
    raw = _source_bytes(url)
    df = pd.read_csv(io.BytesIO(raw), sep=sep, engine="python")
    if sep == "\t" and df.shape[1] == 1:
        df = pd.read_csv(io.BytesIO(raw), sep=",", engine="python")
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


# --- Shared settings across pages --------------------------------------------
# Streamlit drops widget-bound session_state entries as soon as the widget is not
# rendered on the current page, so the canonical values live under their own keys
# and every page widget only mirrors them.
FULL_RANGE_LABEL = "Gesamte Zeitreihe"

HORIZON_MAP = {
    FULL_RANGE_LABEL: None,
    "1 Monat": 31,
    "3 Monate": 3 * 31,
    "6 Monate": 6 * 31,
    "1 Jahr": 365,
    # "2 Jahre": 2 * 365,
    "3 Jahre": 3 * 365,
}

SHARED_START = "shared_date_start"
SHARED_END = "shared_date_end"
SHARED_HORIZON = "shared_horizon"
SHARED_STATIONS = "shared_stations"
SHARED_UNIT = "shared_unit"

# Soil moisture is stored as m3/m3; Vol.-% is the same number times 100.
UNITS = {"Vol.-%": 100.0, "m³/m³": 1.0}
DEFAULT_UNIT = "Vol.-%"


def window_from_horizon(horizon, min_date: date, max_date: date):
    """(start, end) for a horizon label. Unknown/None horizon -> full range."""
    days = HORIZON_MAP.get(horizon) if horizon else None
    if days is None:
        return min_date, max_date
    return max(min_date, max_date - timedelta(days=days - 1)), max_date


def init_shared_window(min_date: date, max_date: date):
    """Seed the shared window once, from the horizon if one is already set."""
    if SHARED_HORIZON not in st.session_state:
        st.session_state[SHARED_HORIZON] = FULL_RANGE_LABEL
    if SHARED_START not in st.session_state or SHARED_END not in st.session_state:
        start, end = window_from_horizon(
            st.session_state[SHARED_HORIZON], min_date, max_date
        )
        st.session_state[SHARED_START] = start
        st.session_state[SHARED_END] = end


def get_shared_window(min_date: date, max_date: date):
    """(start, end, horizon) clamped to the range available on the calling page.

    ``horizon`` is ``None`` when the user typed their own start/end dates.
    """
    init_shared_window(min_date, max_date)
    start = min(max(st.session_state[SHARED_START], min_date), max_date)
    end = min(max(st.session_state[SHARED_END], min_date), max_date)
    if start > end:
        start, end = min_date, max_date
    return start, end, st.session_state.get(SHARED_HORIZON)


def set_shared_window(start: date, end: date, horizon=None):
    st.session_state[SHARED_START] = start
    st.session_state[SHARED_END] = end
    st.session_state[SHARED_HORIZON] = horizon


def reset_shared_window(min_date: date, max_date: date):
    st.session_state[SHARED_HORIZON] = FULL_RANGE_LABEL
    st.session_state[SHARED_START] = min_date
    st.session_state[SHARED_END] = max_date


def get_shared_stations(default=None):
    stations = normalize_stocks(st.session_state.get(SHARED_STATIONS) or [])
    if stations:
        return stations
    return list(default) if default is not None else list(DEFAULT_STOCKS)


def set_shared_stations(stations):
    st.session_state[SHARED_STATIONS] = normalize_stocks(stations)


# Every plot shows Vol.-%; only the CSV download offers a choice of unit.
PLOT_UNIT = "Vol.-%"


def to_plot_unit(data):
    """Scale soil-moisture values (stored as m3/m3) to Vol.-% for plotting."""
    if data is None:
        return None
    return data * UNITS[PLOT_UNIT]


def moisture_label(prefix: str = "Bodenfeuchte") -> str:
    return f"{prefix} ({PLOT_UNIT})"


def get_download_unit() -> str:
    unit = st.session_state.get(SHARED_UNIT, DEFAULT_UNIT)
    return unit if unit in UNITS else DEFAULT_UNIT


def set_download_unit(unit: str):
    if unit in UNITS:
        st.session_state[SHARED_UNIT] = unit


def to_download_unit(data):
    if data is None:
        return None
    return data * UNITS[get_download_unit()]


# --- Labels ------------------------------------------------------------------
def station_label(station: str, locs: Optional[pd.DataFrame] = None) -> str:
    """``"BEE (Beerenbusch)"`` when the station name is known, else the ID."""
    if locs is not None and station in locs.index and "name" in locs.columns:
        value = locs.loc[station, "name"]
        if isinstance(value, str) and value.strip():
            # return f"{station} ({value.strip()})"
            # return f"{value.strip()} ({station})"
            return f"{value.strip()}"
    return station


def station_labeller(locs: Optional[pd.DataFrame] = None):
    """``format_func`` for station selectors."""
    return lambda station: station_label(station, locs)


def smt_depth_label(depth: str) -> str:
    """Sensor depth as shown in the UI; the raw ``weighted`` suffix never leaks."""
    text = str(depth).strip()
    if text.lower() == "weighted":
        return "tiefengewichtet"
    if text.endswith("cm") and not text.endswith(" cm"):
        return f"{text[:-2].strip()} cm"
    return text if text.endswith("cm") else f"{text} cm"


GLOSSARY = {
    "Bodenfeuchte": ("Volumetrischer Wassergehalt des Bodens, angegeben in Vol.-% "),
    "CRNS": (
        "Cosmic-Ray Neutron Sensing: Messung der Bodenfeuchte mit kosmischen Neutronensensoren."
        " Tief im Boden führen Wechselwirkungen mit kosmischer Strahlung zur Entstehung schneller Neutronen. Diese Neutronen werden durch Zusammenstöße mit Atomen abgebremst, wobei Wasserstoff aufgrund seiner Größe den höchsten Einfluss hat."
        " Die Anzahl der gemessenen schnellen Neutronen ist somit ein Maß für die Bodenfeuchte (How does Cosmic-Ray Neutron Sensing work? - neptoon Docs, o. J.)."
    ),
    "D86": (
        "Tiefe, aus der 86 % des gemessenen Neutronensignals stammen (Schrön et al., 2017). Sie hängt von der Bodenfeuchte selbst ab und ändert sich daher "
        "laufend, wobei sie die Bodenschicht beschreibt für den die CRNS-Sonde repräsentative Bodenfeuchtewerte liefert."
    ),
    "SWAP": (
        "Soil-Water-Atmosphere-Plant, deutsch Boden-Wasser-Atmosphäre-Pflanze: https://www.swap.alterra.nl/: "
        "Modell zur Simulation des Transports von Wasser, gelösten Stoffen und Wärme in ungesättigten bzw. gesättigten Böden. "
    ),
    "Tiefengewichtete Bodenfeuchte": (
        "Über die Eindringtiefe der Neutronenmessung gewichteter Mittelwert des SWAP-Modells über die Bodenschichten. Die Eindringtiefe hängt von der Bodenfeuchte ab und ändert sich daher laufend."
    ),
    "Bodenfeuchtesensoren (SMT)": (
        "Punktuell im Boden in verschiedenen Bodenschichten eingebaute Sensoren, die die Bodenfeuchte "
        "über dielektrische Permittivitäten messen."
    ),
    "Auswertung nach Desilets / UTS": (
        "Zwei Verfahren, um gemessene Neutronen in Bodenfeuchte umzurechnen: die "
        "klassische Gleichung nach Desilets (Desilets et al., 2010) und die neuere universelle "
        "Transportgleichung (UTS) (Köhli et al., 2021)."
    ),
    ("Generelle und Lokale Kalibrierung"): (
        "Die generelle Kalibrierung (Heistermann et al., 2024) liefert Schätzung der Bodenfeuchte durch Bestimmung umliegender Wasserstoffpools und Sensorsensivitäten. "
        "Die lokale Kalibrierung nutzt zusätzlich lokale Bodenfeuchtemessungen zu einem Zeitpunkt, um das Signal auf die lokale Bodenfeuchte zu justieren (vgl Schrön et al., 2017). "
    ),
    "Bodenart (KA5)": (
        "Bodenartenklassifikation nach der Bodenkundlichen Kartieranleitung, "
        "5. Auflage. (Sponagel et al., 2005)"
    ),
    "kf-Wert (Gesättigte Leitfähigkeit)": (
        "Die Gesättigte Leitfähigkeit/Durchlässigkeitsbeiwert ist ein Maß dafür, wie schnell Wasser im gesättigten Boden versickert. Sie wird wesentlich bestimmt durch Bodenart, Lagerungsdichte und Wassertemperatur (Bodenkundliche Kartieranleitung in zwei Bänden. 2, 2024)."
    ),
    "Feldkapazität": (
        "Die Feldkapazität ist die Wassermenge, die ein Boden gegen die Schwerkraft halten kann (Bodenkundliche Kartieranleitung in zwei Bänden. 2, 2024). "
    ),
    ("Nutzbare Feldkapazität"): (
        "Die nutzbare Feldkapazität ist der Anteil der Feldkapazität, der für Pflanzen verfügbar ist. Sie ist die Differenz zwischen Feldkapazität und permanentem Welkenpunkt (Bodenkundliche Kartieranleitung in zwei Bänden. 2, 2024). "
    ),
    ("Permanenter Welkenpunkt"): (
        "Der permanente Welkenpunkt ist die Bodenfeuchte, bei der Pflanzen beginnen irreversibel zu Welken. "
        "Zu diesem Zeitpunkt enthält der Boden nur noch Totwasser, wleches bei einer Saugspannung größer pF 4,2 gebunden ist (Bodenkundliche Kartieranleitung in zwei Bänden. 2, 2024)."
    ),
    "Klimatischer Bodenfeuchteindex (SMI)": (
        "Einordnung der aktuellen Bodenfeuchte in die historische Verteilung "
        "desselben Kalendertags; 0 = sehr trocken, 1 = sehr nass."
    ),
    "Schneephase": (
        "Zeitraum mit Schneebedeckung. Schnee verfälscht die Bodenfeuchte-Messung mit Neutronen, da die Neutronen durch den Wasserstoff im Schnee abgebremst werden. "
        "Die Werte sind dort nur eingeschränkt belastbar und maskiert. Die Schneephasen werden aus den täglichen Messungen der Bodenfeuchte-Sensoren abgeleitet."
    ),
}

# Literature behind the CRNS processing steps named in the glossary.
GLOSSARY_SOURCES = [
    (
        "Desilets, D., Zreda, M., & Ferré, T. P. A. (2010). Nature's neutron probe: "
        "Land surface hydrology at an elusive scale with cosmic rays. Water Resources "
        "Research, 46(11). https://doi.org/10.1029/2009WR008726"
    ),
    (
        "Köhli, M., Weimar, J., Schrön, M., Baatz, R., & Schmidt, U. (2021). Soil "
        "Moisture and Air Humidity Dependence of the Above-Ground Cosmic-Ray Neutron "
        "Intensity. Frontiers in Water, 2. https://doi.org/10.3389/frwa.2020.544847"
    ),
    (
        "Köhli, M., Schrön, M., Zreda, M., Schmidt, U., Dietrich, P., & Zacharias, S. (2015). Footprint characteristics revised for field-scale soil moisture monitoring with cosmic-ray neutrons. Water Resources Research, 51(7), 5772–5790. https://doi.org/10.1002/2015WR017169"
    ),
    (
        "Schrön, M., Köhli, M., Scheiffele, L., Iwema, J., Bogena, H. R., Lv, L., Martini, E., Baroni, G., Rosolem, R., Weimar, J., Mai, J., Cuntz, M., Rebmann, C., Oswald, S. E., Dietrich, P., Schmidt, U., & Zacharias, S. (2017). Improving calibration and validation of cosmic-ray neutron sensors in the light of spatial sensitivity. Hydrology and Earth System Sciences, 21(10), 5009–5030. https://doi.org/10.5194/hess-21-5009-2017"
    ),
    (
        "Heistermann, M., Francke, T., Schrön, M., & Oswald, S. E. (2024). Technical "
        "Note: Revisiting the general calibration of cosmic-ray neutron sensors to "
        "estimate soil water content. Hydrology and Earth System Sciences, 28(4), "
        "989–1000. https://doi.org/10.5194/hess-28-989-2024"
    ),
    (
        "How does Cosmic-Ray Neutron Sensing work? – Neptoon Docs. (o. J.). Abgerufen "
        "5. August 2026, von https://www.neptoon.org/en/latest/home/crns-overview/"
    ),
    (
        "Bodenkundliche Kartieranleitung in zwei Bänden. 2: Geländeaufnahme und Systematik (6., komplett überarbeitete und erweiterte Auflage). (2024). In Kommission bei der E. Schweizerbart´sche Verlagsbuchhandlung (Nägele u. Obermiller)."
    ),
    (
        "Sponagel, H., Eckelmann, W., Ad-hoc-Arbeitsgruppe Boden der Staatlichen Geologischen Dienste und der Bundesanstalt für Geowissenschaften und Rohstoffe, & Bundesanstalt für Geowissenschaften und Rohstoffe (Hrsg.). (2005). Bodenkundliche Kartieranleitung: Mit 41 Abbildungen, 103 Tabellen und 31 Listen (5., verbesserte und erweiterte Auflage). Bundesanst. für Geowiss. und Rohstoffe."
    ),
]


def glossary_expander(title: str = "Abkürzungen und Erklärungen"):
    """Site-wide glossary; shown at the bottom of every page."""
    with st.expander(title, expanded=False):
        st.markdown(
            "\n".join(f"- **{term}**: {text}" for term, text in GLOSSARY.items())
        )
        st.markdown("**Quellen**")
        st.markdown("\n".join(f"- {source}" for source in GLOSSARY_SOURCES))


# --- Plot helpers ------------------------------------------------------------
def add_range_slider(
    fig, *, full_range=None, window=None, thickness: float = 0.12, row=None, col=1
):
    """Navigator strip under a plot: full series in the slider, window on the axis.

    On stacked subplots pass ``row`` of the bottom subplot - otherwise every row
    would get its own slider.
    """
    slider: dict[str, object] = dict(
        visible=True,
        thickness=thickness,
        bgcolor="#f8fafc",
        bordercolor="#dbe2ea",
        borderwidth=1,
        # "auto" autoranges the navigator over the whole series, independent of the
        # main plot: zooming above never crops the strip below. ("fixed" would use
        # rangeslider.yaxis.range, "match" would follow the main y-axis.)
        yaxis=dict(rangemode="auto"),
    )
    if full_range is not None:
        slider["range"] = list(full_range)
    axis: dict[str, object] = dict(rangeslider=slider, fixedrange=False)
    if window is not None:
        axis["range"] = list(window)
    if row is not None:
        fig.update_xaxes(**axis, row=row, col=col)
    else:
        fig.update_xaxes(**axis)
    # Box zoom must still work in both directions next to the slider.
    fig.update_yaxes(fixedrange=False)
    fig.update_layout(dragmode="zoom")
    return fig


# Modebar with the full zoom/pan toolset; scroll wheel zooms both axes.
PLOT_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": ["zoom2d", "pan2d", "zoomIn2d", "zoomOut2d", "autoScale2d"],
}


SNOW_FILL = "rgba(120, 120, 120, 0.20)"
# Thin bands need more contrast than a full-height wash; light blue reads as snow.
SNOW_FILL_BAND = "rgba(125, 185, 232, 0.85)"
SNOW_LABEL = "Schneephase"


@st.cache_data(ttl=12 * 3600)
def load_snow_flags(url: str = URL_SNOW_FLAGS) -> pd.DataFrame:
    """Daily per-site snow flags (incl. an ``any_site`` aggregate column).

    Fails soft: if the file is missing/unreachable, return an empty frame so the
    plots simply render without snow shading instead of breaking the page.
    """
    raw = _source_bytes(url, required=False)
    if raw is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(io.BytesIO(raw), sep=",", engine="python")
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


# The snow-flag file names some stations differently than the time series do.
SNOW_COLUMN_ALIASES = {"MQ": ("MQ", "MQ35", "MQ4"), "DED": ("DED", "QUI")}


def station_snow_periods(snow_df: pd.DataFrame, station: str):
    """Snow periods for one station, falling back to the ``any_site`` aggregate."""
    if snow_df is None or snow_df.empty:
        return []
    for candidate in SNOW_COLUMN_ALIASES.get(station, (station,)):
        if candidate in snow_df.columns:
            return snow_periods(snow_df, candidate)
    return snow_periods(snow_df)


def union_snow_periods(snow_df: pd.DataFrame, stations):
    """Merged snow periods across several stations.

    Shared plots must shade exactly what masking removes, so the band is the union
    of the per-station periods - not the ``any_site`` aggregate, which also covers
    stations that are not on screen.
    """
    collected = []
    for station in stations:
        collected.extend(station_snow_periods(snow_df, station))
    if not collected:
        return []
    collected.sort()
    merged = [list(collected[0])]
    for start, end in collected[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def mask_snow_periods(data, periods):
    """Blank out values recorded inside the given periods.

    Snow on the ground biases the neutron count, so CRNS-derived values are shown as
    gaps there rather than as measurements; the shaded band still marks the phase.
    """
    if data is None or not periods or data.empty:
        return data
    covered = pd.Series(False, index=data.index)
    for start, end in periods:
        covered |= (data.index >= start) & (data.index <= end)
    if not covered.any():
        return data
    masked = data.copy()
    masked[covered.to_numpy()] = float("nan")
    return masked


def mask_snow(df: pd.DataFrame, snow_df: pd.DataFrame) -> pd.DataFrame:
    """Apply :func:`mask_snow_periods` per station column of a CRNS time series."""
    if df is None or df.empty or snow_df is None or snow_df.empty:
        return df
    masked = df.copy()
    for column in masked.columns:
        masked[column] = mask_snow_periods(
            masked[column], station_snow_periods(snow_df, column)
        )
    return masked


# Masking CRNS values during snow is on by default but stays the user's choice.
SHARED_MASK_SNOW = "shared_mask_snow"
DEFAULT_MASK_SNOW = True
SNOW_MASK_HELP = (
    "Schnee als Wasserstoffpool auf dem Boden verfälscht die Neutronenmessung der Bodenfecuhte. Ist die Option aktiv, "
    "werden Schneephasen in der Messung maskiert."
)


def get_mask_snow() -> bool:
    return bool(st.session_state.get(SHARED_MASK_SNOW, DEFAULT_MASK_SNOW))


def set_mask_snow(enabled: bool):
    st.session_state[SHARED_MASK_SNOW] = bool(enabled)


def maybe_mask_snow(df: pd.DataFrame, snow_df: pd.DataFrame) -> pd.DataFrame:
    """:func:`mask_snow` when the shared snow-masking setting is switched on."""
    return mask_snow(df, snow_df) if get_mask_snow() else df


def snow_mask_toggle(
    container=None,
    *,
    key: str = "mask_snow_choice",
    label: str = "Messwerte bei Schnee ausblenden",
) -> bool:
    """Checkbox mirroring the shared snow-masking setting across pages."""
    target = container if container is not None else st
    if key not in st.session_state:
        st.session_state[key] = get_mask_snow()

    def _sync():
        set_mask_snow(st.session_state[key])

    target.checkbox(label, key=key, help=SNOW_MASK_HELP, on_change=_sync)
    _sync()
    return st.session_state[key]


def add_snow_shading(
    fig,
    periods,
    *,
    xrange=None,
    add_legend=True,
    position: str = "bottom",
    thickness: float = 0.04,
    add_label: bool = True,
    row=None,
    col=1,
):
    """Mark snow phases as a narrow band along the time axis.

    ``position`` is ``"bottom"``, ``"top"`` or ``"both"``; ``thickness`` is the band
    height as a fraction of the plot. ``add_label`` writes the word "Schneephase" once
    above the widest band. ``xrange`` (lo, hi) clips the rectangles to the visible
    window so the shapes never expand the x-axis autorange. Anchored to
    ``yref="y domain"`` so it also works on secondary-y figures and next to a range
    slider (which would sit inside a ``"paper"``-referenced band).
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
    bands = []
    if position in ("bottom", "both"):
        bands.append((0.0, thickness))
    if position in ("top", "both"):
        bands.append((1.0 - thickness, 1.0))
    if not bands:
        bands = [(0.0, thickness)]

    target = dict(row=row, col=col) if row is not None else {}
    for start, end in periods:
        for y0, y1 in bands:
            fig.add_shape(
                type="rect",
                xref="x",
                yref="y domain",
                x0=start,
                x1=end,
                y0=y0,
                y1=y1,
                fillcolor=SNOW_FILL_BAND,
                line_width=0,
                layer="below",
                **target,
            )
    if add_label and periods:
        # Label the widest band so the colour is self-explanatory without the legend.
        start, end = max(periods, key=lambda p: p[1] - p[0])
        anchor_y = bands[0][1] if bands[0][0] == 0.0 else bands[0][0]
        fig.add_annotation(
            x=start + (end - start) / 2,
            y=anchor_y,
            xref="x",
            yref="y domain",
            text=SNOW_LABEL,
            showarrow=False,
            yanchor="bottom",
            font=dict(size=10, color="#2b6ca3"),
            **target,
        )
    if add_legend:
        legend_marker = go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, symbol="square", color=SNOW_FILL_BAND),
            name=SNOW_LABEL,
            hoverinfo="skip",
        )
        if row is not None:
            fig.add_trace(legend_marker, row=row, col=col)
        else:
            fig.add_trace(legend_marker)
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
SMI_STEP_TOL = 1e-8


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
