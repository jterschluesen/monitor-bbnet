import pandas as pd
import streamlit as st
from datetime import date
from typing import Optional


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
URL_SWC_SWAP = f"{BASE_URL}/swc-from-swap.txt"
URL_D86_CRNS = f"{BASE_URL}/d86-from-crns.txt"
URL_LOCATIONS = f"{BASE_URL}/metadata-locations.csv"
URL_SWC_SMT = f"{BASE_URL}/vwc-from-smt.csv"

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

DEFAULT_STOCKS = ["OEH", "MQ", "DED"]


@st.cache_data(ttl=12 * 3600)
def load_time_series(url: str, sep: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(url, sep=sep, engine="python", na_values="na")
    if "datetime" not in df.columns and "Date" in df.columns:
        df = df.rename(columns={"Date": "datetime"})
    if "datetime" not in df.columns and "Date_Time" in df.columns:
        df = df.rename(columns={"Date_Time": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert(None)
    df = df.set_index("datetime")
    df.index.name = "Date"
    df = df.rename(columns={"QUI": "DED", "MQ35": "MQ"})
    if "WUS" in df.columns:
        df = df.drop(columns=["WUS"])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=12 * 3600)
def load_locations(url: str = URL_LOCATIONS, sep: Optional[str] = None) -> pd.DataFrame:
    df = pd.read_csv(url, sep=sep, engine="python")
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
