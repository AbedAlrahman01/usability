from __future__ import annotations

import re
import zipfile
from pathlib import Path

import duckdb
import polars as pl

from flight_delay_explorer.config import (
    AIRPORTS_CLEAN_PATH,
    AIRPORTS_FILE,
    COUNTRIES_FILE,
    DUCKDB_PATH,
    EXPECTED_ROW_COUNT,
    FLIGHT_ZIP_GLOB,
    FLIGHTS_CLEAN_PATH,
    FLIGHTS_ENRICHED_PATH,
    FREQUENCIES_FILE,
    MINIMUM_ROW_COUNT,
    MONTH_NAMES,
    PROCESSED_DIR,
    RAW_SEARCH_DIRS,
    REGIONS_FILE,
    RUNWAYS_FILE,
    WEEKDAY_NAMES,
)
from flight_delay_explorer.utils import time_of_day_from_hour


def ensure_processed_data(force: bool = False) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    parquet_files = [FLIGHTS_CLEAN_PATH, AIRPORTS_CLEAN_PATH, FLIGHTS_ENRICHED_PATH]
    required_files = [*parquet_files, DUCKDB_PATH]

    if not force:
        if all(path.exists() for path in required_files) and _duckdb_artifact_is_usable():
            return
        if all(path.exists() for path in parquet_files):
            _write_duckdb_from_existing_parquets()
            return

    build_processed_artifacts()


def _duckdb_artifact_is_usable() -> bool:
    if not DUCKDB_PATH.exists():
        return False
    connection = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        connection.execute("SELECT COUNT(*) FROM flights_enriched").fetchone()
        return True
    except Exception:
        return False
    finally:
        connection.close()


def _write_duckdb_from_existing_parquets() -> None:
    flights_clean = pl.read_parquet(FLIGHTS_CLEAN_PATH)
    airports_clean = pl.read_parquet(AIRPORTS_CLEAN_PATH)
    flights_enriched = pl.read_parquet(FLIGHTS_ENRICHED_PATH)
    _write_duckdb_artifacts(flights_clean, airports_clean, flights_enriched)


def build_processed_artifacts() -> None:
    flight_archives = sorted(_find_raw_files(FLIGHT_ZIP_GLOB))
    if len(flight_archives) != 3:
        raise FileNotFoundError(f"Expected 3 flight zip files, found {len(flight_archives)}.")

    flights_raw = pl.concat(
        [_read_flight_archive(path) for path in flight_archives],
        how="diagonal_relaxed",
        rechunk=True,
    )
    flights_clean = _build_flights_clean(flights_raw)

    airports_raw = _read_csv(_find_raw_file(AIRPORTS_FILE))
    runways_raw = _read_csv(_find_raw_file(RUNWAYS_FILE))
    frequencies_raw = _read_csv(_find_raw_file(FREQUENCIES_FILE))
    countries_raw = _read_csv(_find_raw_file(COUNTRIES_FILE))
    regions_raw = _read_csv(_find_raw_file(REGIONS_FILE))

    airports_clean = _build_airports_clean(
        airports=airports_raw,
        runways=runways_raw,
        frequencies=frequencies_raw,
        countries=countries_raw,
        regions=regions_raw,
    )
    flights_enriched = _build_flights_enriched(flights_clean, airports_clean)

    flights_clean.write_parquet(FLIGHTS_CLEAN_PATH)
    airports_clean.write_parquet(AIRPORTS_CLEAN_PATH)
    flights_enriched.write_parquet(FLIGHTS_ENRICHED_PATH)
    _write_duckdb_artifacts(flights_clean, airports_clean, flights_enriched)


def _find_raw_file(name: str) -> Path:
    for base_dir in RAW_SEARCH_DIRS:
        candidate = base_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not find raw file {name!r}.")


def _find_raw_files(pattern: str) -> list[Path]:
    matches: list[Path] = []
    for base_dir in RAW_SEARCH_DIRS:
        matches.extend(base_dir.glob(pattern))
    deduped = {path.resolve(): path for path in matches}
    return sorted(deduped.values())


def _read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(
        path,
        infer_schema_length=5000,
        ignore_errors=True,
        encoding="utf8-lossy",
        null_values=["", "NA", "NULL"],
        try_parse_dates=False,
        truncate_ragged_lines=True,
    )


def _read_flight_archive(zip_path: Path) -> pl.DataFrame:
    month_match = re.search(r"_(\d+)\.zip$", zip_path.name)
    source_month = int(month_match.group(1)) if month_match else None
    with zipfile.ZipFile(zip_path) as archive:
        csv_entries = [entry for entry in archive.infolist() if entry.filename.lower().endswith(".csv")]
        if not csv_entries:
            raise FileNotFoundError(f"No CSV found inside archive {zip_path.name}.")
        entry = csv_entries[0]
        with archive.open(entry) as handle:
            frame = pl.read_csv(
                handle,
                infer_schema_length=5000,
                ignore_errors=True,
                encoding="utf8-lossy",
                null_values=["", "NA", "NULL"],
                truncate_ragged_lines=True,
            )
    return frame.with_columns(
        [
            pl.lit(zip_path.name).alias("source_file"),
            pl.lit(source_month).alias("source_month"),
        ]
    )


def _build_flights_clean(flights: pl.DataFrame) -> pl.DataFrame:
    existing_columns = set(flights.columns)

    def text_expr(name: str) -> pl.Expr:
        if name in existing_columns:
            return pl.col(name).cast(pl.Utf8, strict=False).str.strip_chars()
        return pl.lit(None, dtype=pl.Utf8).alias(name)

    def upper_expr(name: str) -> pl.Expr:
        return text_expr(name).str.to_uppercase().alias(name)

    def num_expr(name: str) -> pl.Expr:
        if name in existing_columns:
            return pl.col(name).cast(pl.Float64, strict=False).alias(name)
        return pl.lit(None, dtype=pl.Float64).alias(name)

    def int_expr(name: str) -> pl.Expr:
        if name in existing_columns:
            return pl.col(name).cast(pl.Int64, strict=False).alias(name)
        return pl.lit(None, dtype=pl.Int64).alias(name)

    flights = flights.with_columns(
        [
            upper_expr("Reporting_Airline"),
            upper_expr("IATA_CODE_Reporting_Airline"),
            upper_expr("Origin"),
            upper_expr("Dest"),
            upper_expr("Tail_Number"),
            text_expr("Flight_Number_Reporting_Airline"),
            text_expr("OriginCityName"),
            text_expr("DestCityName"),
            text_expr("OriginStateName"),
            text_expr("DestStateName"),
            pl.col("FlightDate").str.strptime(pl.Date, strict=False).alias("FlightDate")
            if "FlightDate" in existing_columns
            else pl.lit(None, dtype=pl.Date).alias("FlightDate"),
            int_expr("Year"),
            int_expr("Quarter"),
            int_expr("Month"),
            int_expr("DayofMonth"),
            int_expr("DayOfWeek"),
            num_expr("CRSDepTime"),
            num_expr("DepTime"),
            num_expr("CRSArrTime"),
            num_expr("ArrTime"),
            num_expr("WheelsOff"),
            num_expr("WheelsOn"),
            num_expr("DepDelay"),
            num_expr("DepDelayMinutes"),
            num_expr("ArrDelay"),
            num_expr("ArrDelayMinutes"),
            num_expr("DepDel15"),
            num_expr("ArrDel15"),
            num_expr("TaxiOut"),
            num_expr("TaxiIn"),
            num_expr("Cancelled"),
            upper_expr("CancellationCode"),
            num_expr("Diverted"),
            num_expr("CRSElapsedTime"),
            num_expr("ActualElapsedTime"),
            num_expr("AirTime"),
            num_expr("Distance"),
            num_expr("DistanceGroup"),
            num_expr("CarrierDelay"),
            num_expr("WeatherDelay"),
            num_expr("NASDelay"),
            num_expr("SecurityDelay"),
            num_expr("LateAircraftDelay"),
        ]
    )

    departure_minutes = _hhmm_total_minutes("DepTime", existing_columns)
    scheduled_departure_minutes = _hhmm_total_minutes("CRSDepTime", existing_columns)
    arrival_minutes = _hhmm_total_minutes("ArrTime", existing_columns)
    scheduled_arrival_minutes = _hhmm_total_minutes("CRSArrTime", existing_columns)

    carrier_delay = pl.col("CarrierDelay").fill_null(0.0)
    weather_delay = pl.col("WeatherDelay").fill_null(0.0)
    nas_delay = pl.col("NASDelay").fill_null(0.0)
    security_delay = pl.col("SecurityDelay").fill_null(0.0)
    late_aircraft_delay = pl.col("LateAircraftDelay").fill_null(0.0)
    max_cause_delay = pl.max_horizontal(
        [carrier_delay, weather_delay, nas_delay, security_delay, late_aircraft_delay]
    )

    flights = flights.with_row_index("flight_row_id", offset=1).with_columns(
        [
            pl.coalesce([pl.col("Year"), pl.col("FlightDate").dt.year()]).alias("flight_year"),
            pl.coalesce([pl.col("Month"), pl.col("FlightDate").dt.month()]).alias("flight_month"),
            pl.coalesce([pl.col("DayofMonth"), pl.col("FlightDate").dt.day()]).alias("flight_day"),
            pl.coalesce([pl.col("DayOfWeek"), pl.col("FlightDate").dt.weekday()]).alias("flight_weekday"),
            pl.coalesce([departure_minutes // 60, scheduled_departure_minutes // 60]).cast(pl.Int64).alias("departure_hour"),
            pl.coalesce([arrival_minutes // 60, scheduled_arrival_minutes // 60]).cast(pl.Int64).alias("arrival_hour"),
            _hhmm_label("CRSDepTime", existing_columns).alias("crs_dep_time_label"),
            _hhmm_label("DepTime", existing_columns).alias("dep_time_label"),
            _hhmm_label("CRSArrTime", existing_columns).alias("crs_arr_time_label"),
            _hhmm_label("ArrTime", existing_columns).alias("arr_time_label"),
            pl.when(pl.col("DepDelayMinutes").is_not_null())
            .then(pl.col("DepDelayMinutes"))
            .otherwise(pl.max_horizontal([pl.col("DepDelay"), pl.lit(0.0)]))
            .alias("DepDelayMinutes"),
            pl.when(pl.col("ArrDelayMinutes").is_not_null())
            .then(pl.col("ArrDelayMinutes"))
            .otherwise(pl.max_horizontal([pl.col("ArrDelay"), pl.lit(0.0)]))
            .alias("ArrDelayMinutes"),
            (pl.col("Cancelled").fill_null(0.0) == 1.0).alias("is_cancelled"),
            (pl.col("Diverted").fill_null(0.0) == 1.0).alias("is_diverted"),
            ((pl.col("Cancelled").fill_null(0.0) == 0.0) & (pl.col("Diverted").fill_null(0.0) == 0.0)).alias("is_completed"),
            (
                (pl.col("DepDelay").fill_null(-9999.0) >= 15.0)
                | (pl.col("ArrDelay").fill_null(-9999.0) >= 15.0)
            ).alias("is_delayed_15"),
            (pl.col("DepDelay").fill_null(-9999.0) >= 15.0).alias("is_departure_delayed_15"),
            (pl.col("ArrDelay").fill_null(-9999.0) >= 15.0).alias("is_arrival_delayed_15"),
            (
                (pl.col("DepDelay").fill_null(-9999.0) >= 60.0)
                | (pl.col("ArrDelay").fill_null(-9999.0) >= 60.0)
            ).alias("is_severely_delayed_60"),
            pl.concat_str([pl.col("Origin").fill_null("UNK"), pl.lit(" -> "), pl.col("Dest").fill_null("UNK")]).alias("route"),
            pl.concat_str([pl.col("Origin").fill_null("UNK"), pl.lit("_"), pl.col("Dest").fill_null("UNK")]).alias("route_id"),
            (carrier_delay + weather_delay + nas_delay + security_delay + late_aircraft_delay).alias("total_cause_delay_minutes"),
            pl.when(max_cause_delay <= 0.0)
            .then(pl.lit("Unknown / None"))
            .when(late_aircraft_delay == max_cause_delay)
            .then(pl.lit("Late Aircraft"))
            .when(carrier_delay == max_cause_delay)
            .then(pl.lit("Carrier"))
            .when(nas_delay == max_cause_delay)
            .then(pl.lit("NAS"))
            .when(weather_delay == max_cause_delay)
            .then(pl.lit("Weather"))
            .otherwise(pl.lit("Security"))
            .alias("main_delay_cause"),
        ]
    )

    flights = flights.with_columns(
        [
            pl.col("flight_month").replace_strict(MONTH_NAMES, default=None).alias("flight_month_name"),
            pl.col("flight_weekday").replace_strict(WEEKDAY_NAMES, default=None).alias("flight_weekday_name"),
            pl.col("departure_hour")
            .map_elements(time_of_day_from_hour, return_dtype=pl.Utf8)
            .alias("time_of_day_group"),
            pl.when(pl.col("Distance").is_null())
            .then(pl.lit(None, dtype=pl.Utf8))
            .when(pl.col("Distance") < 500)
            .then(pl.lit("Short"))
            .when(pl.col("Distance") < 1500)
            .then(pl.lit("Medium"))
            .when(pl.col("Distance") < 3000)
            .then(pl.lit("Long"))
            .otherwise(pl.lit("Very long"))
            .alias("distance_group"),
        ]
    )

    if flights.height < MINIMUM_ROW_COUNT:
        raise ValueError(f"Combined dataset row count {flights.height:,} is below the required minimum.")
    return flights


def _build_airports_clean(
    airports: pl.DataFrame,
    runways: pl.DataFrame,
    frequencies: pl.DataFrame,
    countries: pl.DataFrame,
    regions: pl.DataFrame,
) -> pl.DataFrame:
    runways_by_airport = (
        runways.with_columns(
            [
                pl.col("airport_ident").cast(pl.Utf8, strict=False).str.to_uppercase(),
                pl.col("length_ft").cast(pl.Float64, strict=False),
                pl.col("surface").cast(pl.Utf8, strict=False),
                pl.col("lighted").cast(pl.Int64, strict=False),
                pl.col("closed").cast(pl.Int64, strict=False),
            ]
        )
        .group_by("airport_ident")
        .agg(
            [
                pl.len().alias("runway_count"),
                pl.col("length_ft").max().alias("max_runway_length_ft"),
                pl.col("length_ft").mean().alias("avg_runway_length_ft"),
                pl.col("lighted").fill_null(0).sum().alias("lighted_runway_count"),
                pl.col("closed").fill_null(0).sum().alias("closed_runway_count"),
                pl.col("surface").drop_nulls().unique().sort().alias("surface_list"),
            ]
        )
        .with_columns(pl.col("surface_list").list.slice(0, 3).list.join(", ").alias("common_runway_surfaces"))
        .drop("surface_list")
    )

    frequencies_by_airport = (
        frequencies.with_columns(
            [
                pl.col("airport_ident").cast(pl.Utf8, strict=False).str.to_uppercase(),
                pl.col("type").cast(pl.Utf8, strict=False).str.to_uppercase(),
            ]
        )
        .group_by("airport_ident")
        .agg(
            [
                pl.len().alias("frequency_count"),
                pl.col("type").drop_nulls().unique().sort().alias("frequency_type_list"),
            ]
        )
        .with_columns(
            [
                pl.col("frequency_type_list").list.join(", ").alias("frequency_types"),
                pl.col("frequency_type_list").list.contains("TWR").alias("has_tower_frequency"),
                pl.col("frequency_type_list").list.contains("GND").alias("has_ground_frequency"),
            ]
        )
        .drop("frequency_type_list")
    )

    countries_clean = countries.select(
        [
            pl.col("code").cast(pl.Utf8, strict=False).str.to_uppercase().alias("airport_country_code"),
            pl.col("name").cast(pl.Utf8, strict=False).alias("country_name"),
        ]
    )
    regions_clean = regions.select(
        [
            pl.col("code").cast(pl.Utf8, strict=False).str.to_uppercase().alias("airport_region_code"),
            pl.col("name").cast(pl.Utf8, strict=False).alias("region_name"),
        ]
    )

    airports_clean = (
        airports.with_columns(
            [
                pl.col("ident").cast(pl.Utf8, strict=False).str.to_uppercase().alias("airport_ident"),
                pl.col("iata_code").cast(pl.Utf8, strict=False).str.to_uppercase().alias("airport_iata_code"),
                pl.col("type").cast(pl.Utf8, strict=False).alias("airport_type"),
                pl.col("name").cast(pl.Utf8, strict=False).alias("airport_name"),
                pl.col("latitude_deg").cast(pl.Float64, strict=False).alias("airport_latitude"),
                pl.col("longitude_deg").cast(pl.Float64, strict=False).alias("airport_longitude"),
                pl.col("elevation_ft").cast(pl.Float64, strict=False).alias("airport_elevation_ft"),
                pl.col("iso_country").cast(pl.Utf8, strict=False).str.to_uppercase().alias("airport_country_code"),
                pl.col("iso_region").cast(pl.Utf8, strict=False).str.to_uppercase().alias("airport_region_code"),
                pl.col("municipality").cast(pl.Utf8, strict=False).alias("airport_municipality"),
                pl.col("scheduled_service").cast(pl.Utf8, strict=False).alias("airport_scheduled_service"),
                pl.col("gps_code").cast(pl.Utf8, strict=False).alias("airport_gps_code"),
                pl.col("local_code").cast(pl.Utf8, strict=False).alias("airport_local_code"),
            ]
        )
        .select(
            [
                "airport_ident",
                "airport_iata_code",
                "airport_type",
                "airport_name",
                "airport_latitude",
                "airport_longitude",
                "airport_elevation_ft",
                "airport_country_code",
                "airport_region_code",
                "airport_municipality",
                "airport_scheduled_service",
                "airport_gps_code",
                "airport_local_code",
            ]
        )
        .filter(pl.col("airport_iata_code").is_not_null() & (pl.col("airport_iata_code") != ""))
        .join(countries_clean, on="airport_country_code", how="left")
        .join(regions_clean, on="airport_region_code", how="left")
        .join(runways_by_airport, on="airport_ident", how="left")
        .join(frequencies_by_airport, on="airport_ident", how="left")
    )
    return airports_clean.unique(subset=["airport_iata_code"], keep="first")


def _build_flights_enriched(flights: pl.DataFrame, airports_clean: pl.DataFrame) -> pl.DataFrame:
    origin_airports = airports_clean.select(
        [
            pl.col("airport_iata_code").alias("Origin"),
            pl.col("airport_name").alias("origin_airport_name"),
            pl.col("airport_latitude").alias("origin_latitude"),
            pl.col("airport_longitude").alias("origin_longitude"),
            pl.col("airport_municipality").alias("origin_city"),
            pl.col("region_name").alias("origin_region_name"),
            pl.col("country_name").alias("origin_country_name"),
            pl.col("runway_count").alias("origin_runway_count"),
            pl.col("max_runway_length_ft").alias("origin_max_runway_length_ft"),
            pl.col("frequency_count").alias("origin_frequency_count"),
        ]
    )
    dest_airports = airports_clean.select(
        [
            pl.col("airport_iata_code").alias("Dest"),
            pl.col("airport_name").alias("dest_airport_name"),
            pl.col("airport_latitude").alias("dest_latitude"),
            pl.col("airport_longitude").alias("dest_longitude"),
            pl.col("airport_municipality").alias("dest_city"),
            pl.col("region_name").alias("dest_region_name"),
            pl.col("country_name").alias("dest_country_name"),
            pl.col("runway_count").alias("dest_runway_count"),
            pl.col("max_runway_length_ft").alias("dest_max_runway_length_ft"),
            pl.col("frequency_count").alias("dest_frequency_count"),
        ]
    )

    return flights.join(origin_airports, on="Origin", how="left").join(dest_airports, on="Dest", how="left")


def _hhmm_total_minutes(column_name: str, existing_columns: set[str]) -> pl.Expr:
    if column_name not in existing_columns:
        return pl.lit(None, dtype=pl.Int64)
    value = pl.col(column_name).cast(pl.Int64, strict=False)
    normalized = pl.when(value == 2400).then(0).otherwise(value % 2400)
    hours = normalized // 100
    minutes = normalized % 100
    return ((hours * 60) + minutes).cast(pl.Int64)


def _hhmm_label(column_name: str, existing_columns: set[str]) -> pl.Expr:
    if column_name not in existing_columns:
        return pl.lit(None, dtype=pl.Utf8)
    value = pl.col(column_name).cast(pl.Int64, strict=False)
    normalized = pl.when(value == 2400).then(2400).otherwise(value % 2400)
    hours = pl.when(normalized == 2400).then(24).otherwise(normalized // 100)
    minutes = pl.when(normalized == 2400).then(0).otherwise(normalized % 100)
    return (
        pl.when(value.is_null())
        .then(pl.lit(None, dtype=pl.Utf8))
        .otherwise(
            pl.concat_str(
                [
                    hours.cast(pl.Utf8).str.zfill(2),
                    pl.lit(":"),
                    minutes.cast(pl.Utf8).str.zfill(2),
                ]
            )
        )
    )


def _write_duckdb_artifacts(
    flights_clean: pl.DataFrame,
    airports_clean: pl.DataFrame,
    flights_enriched: pl.DataFrame,
) -> None:
    if DUCKDB_PATH.exists():
        DUCKDB_PATH.unlink()

    connection = duckdb.connect(str(DUCKDB_PATH))
    try:
        flights_clean_path = FLIGHTS_CLEAN_PATH.as_posix()
        airports_clean_path = AIRPORTS_CLEAN_PATH.as_posix()
        flights_enriched_path = FLIGHTS_ENRICHED_PATH.as_posix()
        connection.execute(
            f"CREATE OR REPLACE VIEW flights_clean AS SELECT * FROM read_parquet('{flights_clean_path}')"
        )
        connection.execute(
            f"CREATE OR REPLACE VIEW airports_clean AS SELECT * FROM read_parquet('{airports_clean_path}')"
        )
        connection.execute(
            f"CREATE OR REPLACE VIEW flights_enriched AS SELECT * FROM read_parquet('{flights_enriched_path}')"
        )

        connection.execute(
            """
            CREATE OR REPLACE VIEW monthly_summary AS
            SELECT
                flight_month,
                flight_month_name,
                COUNT(*) AS total_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate
            FROM flights_enriched
            GROUP BY 1, 2
            ORDER BY 1
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW airline_summary AS
            SELECT
                COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) AS airline_code,
                COUNT(*) AS total_flights,
                SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) AS completed_flights,
                SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_flights,
                SUM(CASE WHEN is_diverted THEN 1 ELSE 0 END) AS diverted_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate
            FROM flights_enriched
            GROUP BY 1
            ORDER BY total_flights DESC
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW route_summary AS
            SELECT
                route,
                Origin,
                Dest,
                COUNT(*) AS total_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(Distance) AS avg_distance
            FROM flights_enriched
            GROUP BY 1, 2, 3
            ORDER BY total_flights DESC
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW delay_cause_summary AS
            SELECT
                SUM(COALESCE(CarrierDelay, 0)) AS carrier_delay_total,
                SUM(COALESCE(WeatherDelay, 0)) AS weather_delay_total,
                SUM(COALESCE(NASDelay, 0)) AS nas_delay_total,
                SUM(COALESCE(SecurityDelay, 0)) AS security_delay_total,
                SUM(COALESCE(LateAircraftDelay, 0)) AS late_aircraft_delay_total
            FROM flights_enriched
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW route_map_summary AS
            SELECT
                route,
                Origin,
                Dest,
                origin_airport_name,
                dest_airport_name,
                origin_latitude,
                origin_longitude,
                dest_latitude,
                dest_longitude,
                COUNT(*) AS total_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                mode(COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)) AS most_common_airline
            FROM flights_enriched
            GROUP BY
                route,
                Origin,
                Dest,
                origin_airport_name,
                dest_airport_name,
                origin_latitude,
                origin_longitude,
                dest_latitude,
                dest_longitude
            HAVING origin_latitude IS NOT NULL
               AND origin_longitude IS NOT NULL
               AND dest_latitude IS NOT NULL
               AND dest_longitude IS NOT NULL
            ORDER BY total_flights DESC
            """
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW data_quality_summary AS
            SELECT
                COUNT(*) AS total_loaded_rows,
                COUNT(DISTINCT source_file) AS number_of_source_files,
                MIN(FlightDate) AS min_flight_date,
                MAX(FlightDate) AS max_flight_date,
                COUNT(DISTINCT COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)) AS number_of_airlines,
                COUNT(DISTINCT Origin) AS number_of_origin_airports,
                COUNT(DISTINCT Dest) AS number_of_destination_airports,
                SUM(CASE WHEN origin_airport_name IS NULL THEN 1 ELSE 0 END) AS flights_without_origin_airport_match,
                SUM(CASE WHEN dest_airport_name IS NULL THEN 1 ELSE 0 END) AS flights_without_destination_airport_match
            FROM flights_enriched
            """
        )
    finally:
        connection.close()

    if EXPECTED_ROW_COUNT and flights_clean.height != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Combined row count mismatch: expected {EXPECTED_ROW_COUNT:,}, got {flights_clean.height:,}."
        )
