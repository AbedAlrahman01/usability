from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
APP_TITLE = "Flight Delay Explorer"

RAW_SEARCH_DIRS = [
    DATA_DIR / "raw",
    PROJECT_ROOT,
]

FLIGHT_ZIP_GLOB = "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_*.zip"
AIRPORTS_FILE = "airports.csv"
RUNWAYS_FILE = "runways.csv"
FREQUENCIES_FILE = "airport-frequencies.csv"
COUNTRIES_FILE = "countries.csv"
REGIONS_FILE = "regions.csv"

FLIGHTS_CLEAN_PATH = PROCESSED_DIR / "flights_clean.parquet"
AIRPORTS_CLEAN_PATH = PROCESSED_DIR / "airports_clean.parquet"
FLIGHTS_ENRICHED_PATH = PROCESSED_DIR / "flights_enriched.parquet"
DUCKDB_PATH = PROCESSED_DIR / "flight_delay.duckdb"

EXPECTED_ROW_COUNT = 1_658_259
MINIMUM_ROW_COUNT = 10_000

COLOR_TOKENS = {
    "background": "#f5f1e8",
    "surface": "#fbf8f1",
    "surface_alt": "#eef2f3",
    "navy": "#18324a",
    "slate": "#405363",
    "teal": "#2f7c84",
    "teal_soft": "#a3c8cb",
    "amber": "#d58b3d",
    "coral": "#cf6a5d",
    "sage": "#6f8b6e",
    "line": "#d9d2c3",
    "muted": "#56656f",
}

MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

WEEKDAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

TIME_OF_DAY_ORDER = ["Night", "Morning", "Afternoon", "Evening"]
DISTANCE_GROUP_ORDER = ["Short", "Medium", "Long", "Very long"]
DELAY_CAUSE_ORDER = [
    "Late Aircraft",
    "Carrier",
    "NAS",
    "Weather",
    "Security",
    "Unknown / None",
]

DEFAULT_PAGE_SIZE = 100
