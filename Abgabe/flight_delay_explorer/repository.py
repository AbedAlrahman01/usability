from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from flight_delay_explorer.config import DEFAULT_PAGE_SIZE, DUCKDB_PATH, TIME_OF_DAY_ORDER
from flight_delay_explorer.models import GlobalFilterState
from flight_delay_explorer.utils import cancellation_reason_label


class FlightDelayRepository:
    def __init__(self, db_path: Path = DUCKDB_PATH) -> None:
        self.db_path = db_path

    def get_filter_options(self) -> dict[str, Any]:
        min_max = self._query_df("SELECT MIN(FlightDate) AS start_date, MAX(FlightDate) AS end_date FROM flights_enriched").iloc[0].to_dict()
        options = {
            "start_date": min_max["start_date"],
            "end_date": min_max["end_date"],
            "months": self._distinct_values("flight_month_name"),
            "weekdays": self._distinct_values("flight_weekday_name"),
            "airlines": self._distinct_values("COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)"),
            "origins": self._distinct_values("Origin"),
            "destinations": self._distinct_values("Dest"),
            "routes": self._distinct_values("route"),
            "distance_groups": self._distinct_values("distance_group"),
            "time_of_day_groups": [item for item in TIME_OF_DAY_ORDER if item in self._distinct_values("time_of_day_group")],
        }
        return options

    def get_overview_metrics(self, filters: GlobalFilterState) -> dict[str, Any]:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                COUNT(*) AS total_flights,
                SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) AS completed_flights,
                SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_flights,
                SUM(CASE WHEN is_diverted THEN 1 ELSE 0 END) AS diverted_flights,
                SUM(CASE WHEN is_delayed_15 THEN 1 ELSE 0 END) AS delayed_flights,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                MAX(DepDelay) AS longest_departure_delay,
                MAX(ArrDelay) AS longest_arrival_delay,
                (SELECT COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)
                 FROM filtered
                 GROUP BY 1
                 ORDER BY COUNT(*) DESC, 1
                 LIMIT 1) AS busiest_airline,
                (SELECT Origin
                 FROM filtered
                 GROUP BY 1
                 ORDER BY COUNT(*) DESC, 1
                 LIMIT 1) AS busiest_origin_airport,
                (SELECT Dest
                 FROM filtered
                 GROUP BY 1
                 ORDER BY COUNT(*) DESC, 1
                 LIMIT 1) AS busiest_destination_airport
            FROM filtered
            """,
        )
        return self._query_df(sql, params).iloc[0].to_dict()

    def get_monthly_trends(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                flight_month,
                flight_month_name,
                COUNT(*) AS total_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate
            FROM filtered
            GROUP BY 1, 2
            ORDER BY flight_month
            """,
        )
        return self._query_df(sql, params)

    def get_delay_distribution(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT ArrDelay
            FROM filtered
            WHERE ArrDelay IS NOT NULL
            LIMIT 50000
            """,
        )
        return self._query_df(sql, params)

    def get_top_airlines(self, filters: GlobalFilterState, limit: int = 12) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                ROW_NUMBER() OVER (ORDER BY AVG(DepDelay) DESC) AS rank,
                COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) AS airline_code,
                COUNT(*) AS flights,
                SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) AS completed_flights,
                SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_flights,
                SUM(CASE WHEN is_diverted THEN 1 ELSE 0 END) AS diverted_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(CASE WHEN is_completed AND NOT is_delayed_15 THEN 1.0 ELSE 0.0 END) AS on_time_percentage,
                SUM(CASE WHEN is_severely_delayed_60 THEN 1 ELSE 0 END) AS severe_delay_count,
                AVG(TaxiOut) AS avg_taxi_out
            FROM filtered
            GROUP BY 2
            ORDER BY flights DESC
            LIMIT {int(limit)}
            """,
        )
        return self._query_df(sql, params)

    def get_top_airports(self, filters: GlobalFilterState, mode: str = "origin", limit: int = 12) -> pd.DataFrame:
        if mode == "destination":
            airport_column = "Dest"
            name_column = "dest_airport_name"
            city_column = "dest_city"
            delay_column = "ArrDelay"
            runway_column = "dest_runway_count"
            longest_column = "dest_max_runway_length_ft"
        else:
            airport_column = "Origin"
            name_column = "origin_airport_name"
            city_column = "origin_city"
            delay_column = "DepDelay"
            runway_column = "origin_runway_count"
            longest_column = "origin_max_runway_length_ft"

        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                {airport_column} AS airport_code,
                MAX({name_column}) AS airport_name,
                MAX({city_column}) AS city_name,
                COUNT(*) AS flights,
                AVG({delay_column}) AS avg_delay,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(TaxiOut) AS avg_taxi_out,
                AVG(TaxiIn) AS avg_taxi_in,
                MAX({runway_column}) AS runway_count,
                MAX({longest_column}) AS longest_runway_length
            FROM filtered
            WHERE {airport_column} IS NOT NULL
            GROUP BY 1
            ORDER BY flights DESC
            LIMIT {int(limit)}
            """,
        )
        return self._query_df(sql, params)

    def get_airport_detail(self, filters: GlobalFilterState, airport_code: str) -> dict[str, Any]:
        repeated_codes = [airport_code] * 25
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                ? AS airport_code,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_airport_name END), MAX(CASE WHEN Dest = ? THEN dest_airport_name END)) AS airport_name,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_city END), MAX(CASE WHEN Dest = ? THEN dest_city END)) AS city,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_region_name END), MAX(CASE WHEN Dest = ? THEN dest_region_name END)) AS region_name,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_country_name END), MAX(CASE WHEN Dest = ? THEN dest_country_name END)) AS country_name,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_latitude END), MAX(CASE WHEN Dest = ? THEN dest_latitude END)) AS latitude,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_longitude END), MAX(CASE WHEN Dest = ? THEN dest_longitude END)) AS longitude,
                SUM(CASE WHEN Origin = ? THEN 1 ELSE 0 END) AS total_departures,
                SUM(CASE WHEN Dest = ? THEN 1 ELSE 0 END) AS total_arrivals,
                AVG(CASE WHEN Origin = ? THEN DepDelay END) AS avg_departure_delay,
                AVG(CASE WHEN Dest = ? THEN ArrDelay END) AS avg_arrival_delay,
                AVG(CASE WHEN (Origin = ? OR Dest = ?) AND is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_runway_count END), MAX(CASE WHEN Dest = ? THEN dest_runway_count END)) AS runway_count,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_max_runway_length_ft END), MAX(CASE WHEN Dest = ? THEN dest_max_runway_length_ft END)) AS longest_runway,
                COALESCE(MAX(CASE WHEN Origin = ? THEN origin_frequency_count END), MAX(CASE WHEN Dest = ? THEN dest_frequency_count END)) AS frequency_count
            FROM filtered
            """,
            repeated_codes,
        )
        return self._query_df(sql, params).iloc[0].to_dict()

    def get_airport_top_routes(self, filters: GlobalFilterState, airport_code: str) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                route,
                COUNT(*) AS flights,
                AVG(DepDelay) AS avg_departure_delay
            FROM filtered
            WHERE Origin = ?
            GROUP BY 1
            ORDER BY flights DESC
            LIMIT 8
            """,
            [airport_code],
        )
        return self._query_df(sql, params)

    def get_route_ranking(self, filters: GlobalFilterState, limit: int = 15) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                route,
                Origin,
                Dest,
                COUNT(*) AS total_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(Distance) AS avg_distance,
                AVG(CRSElapsedTime) AS avg_scheduled_duration,
                AVG(ActualElapsedTime) AS avg_actual_duration
            FROM filtered
            GROUP BY 1, 2, 3
            ORDER BY total_flights DESC
            LIMIT {int(limit)}
            """,
        )
        return self._query_df(sql, params)

    def get_route_detail(self, filters: GlobalFilterState, route: str) -> dict[str, Any]:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                route,
                COUNT(*) AS total_flights,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(Distance) AS distance,
                (
                    SELECT COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)
                    FROM filtered f2
                    WHERE f2.route = filtered.route
                    GROUP BY 1
                    ORDER BY AVG(ArrDelay) ASC NULLS LAST
                    LIMIT 1
                ) AS best_airline,
                (
                    SELECT COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)
                    FROM filtered f3
                    WHERE f3.route = filtered.route
                    GROUP BY 1
                    ORDER BY AVG(ArrDelay) DESC NULLS LAST
                    LIMIT 1
                ) AS worst_airline,
                (
                    SELECT flight_month_name
                    FROM filtered f4
                    WHERE f4.route = filtered.route
                    GROUP BY 1, flight_month
                    ORDER BY AVG(ArrDelay) DESC NULLS LAST, flight_month
                    LIMIT 1
                ) AS worst_month,
                (
                    SELECT departure_hour
                    FROM filtered f5
                    WHERE f5.route = filtered.route AND departure_hour IS NOT NULL
                    GROUP BY 1
                    ORDER BY AVG(ArrDelay) ASC NULLS LAST, 1
                    LIMIT 1
                ) AS best_departure_hour
            FROM filtered
            WHERE route = ?
            GROUP BY route
            """,
            [route],
        )
        frame = self._query_df(sql, params)
        return {} if frame.empty else frame.iloc[0].to_dict()

    def get_time_heatmap(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                flight_weekday_name,
                departure_hour,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate
            FROM filtered
            WHERE flight_weekday_name IS NOT NULL
              AND departure_hour IS NOT NULL
            GROUP BY 1, 2
            ORDER BY MIN(flight_weekday), departure_hour
            """,
        )
        return self._query_df(sql, params)

    def get_time_summary(self, filters: GlobalFilterState) -> dict[str, pd.DataFrame]:
        queries = {
            "weekday": """
                SELECT flight_weekday_name, AVG(ArrDelay) AS avg_arrival_delay,
                       AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate
                FROM filtered
                WHERE flight_weekday_name IS NOT NULL
                GROUP BY 1
                ORDER BY MIN(flight_weekday)
            """,
            "hourly": """
                SELECT departure_hour, AVG(DepDelay) AS avg_departure_delay, COUNT(*) AS flights
                FROM filtered
                WHERE departure_hour IS NOT NULL
                GROUP BY 1
                ORDER BY 1
            """,
            "time_of_day": """
                SELECT time_of_day_group, AVG(ArrDelay) AS avg_arrival_delay,
                       AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate
                FROM filtered
                WHERE time_of_day_group IS NOT NULL
                GROUP BY 1
            """,
        }
        result: dict[str, pd.DataFrame] = {}
        for key, body in queries.items():
            sql, params = self._filtered_cte(filters, body)
            result[key] = self._query_df(sql, params)
        return result

    def get_delay_cause_breakdown(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                SUM(COALESCE(CarrierDelay, 0)) AS carrier_delay,
                SUM(COALESCE(WeatherDelay, 0)) AS weather_delay,
                SUM(COALESCE(NASDelay, 0)) AS nas_delay,
                SUM(COALESCE(SecurityDelay, 0)) AS security_delay,
                SUM(COALESCE(LateAircraftDelay, 0)) AS late_aircraft_delay
            FROM filtered
            """,
        )
        frame = self._query_df(sql, params)
        record = frame.iloc[0].to_dict()
        return pd.DataFrame(
            {
                "cause": ["Carrier", "Weather", "NAS", "Security", "Late Aircraft"],
                "delay_minutes": [
                    record["carrier_delay"],
                    record["weather_delay"],
                    record["nas_delay"],
                    record["security_delay"],
                    record["late_aircraft_delay"],
                ],
            }
        )

    def get_delay_cause_by_airline(self, filters: GlobalFilterState, limit: int = 10) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) AS airline_code,
                SUM(COALESCE(CarrierDelay, 0)) AS carrier_delay,
                SUM(COALESCE(WeatherDelay, 0)) AS weather_delay,
                SUM(COALESCE(NASDelay, 0)) AS nas_delay,
                SUM(COALESCE(SecurityDelay, 0)) AS security_delay,
                SUM(COALESCE(LateAircraftDelay, 0)) AS late_aircraft_delay
            FROM filtered
            GROUP BY 1
            ORDER BY carrier_delay + weather_delay + nas_delay + security_delay + late_aircraft_delay DESC
            LIMIT {int(limit)}
            """,
        )
        return self._query_df(sql, params)

    def get_delay_cause_by_airport(self, filters: GlobalFilterState, limit: int = 10) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                Origin AS airport_code,
                SUM(COALESCE(CarrierDelay, 0)) AS carrier_delay,
                SUM(COALESCE(WeatherDelay, 0)) AS weather_delay,
                SUM(COALESCE(NASDelay, 0)) AS nas_delay,
                SUM(COALESCE(SecurityDelay, 0)) AS security_delay,
                SUM(COALESCE(LateAircraftDelay, 0)) AS late_aircraft_delay
            FROM filtered
            GROUP BY 1
            ORDER BY carrier_delay + weather_delay + nas_delay + security_delay + late_aircraft_delay DESC
            LIMIT {int(limit)}
            """,
        )
        return self._query_df(sql, params)

    def get_delay_cause_over_time(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                flight_month,
                flight_month_name,
                SUM(COALESCE(CarrierDelay, 0)) AS carrier_delay,
                SUM(COALESCE(WeatherDelay, 0)) AS weather_delay,
                SUM(COALESCE(NASDelay, 0)) AS nas_delay,
                SUM(COALESCE(SecurityDelay, 0)) AS security_delay,
                SUM(COALESCE(LateAircraftDelay, 0)) AS late_aircraft_delay
            FROM filtered
            GROUP BY 1, 2
            ORDER BY flight_month
            """,
        )
        return self._query_df(sql, params)

    def get_cancellation_metrics(self, filters: GlobalFilterState) -> dict[str, Any]:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS total_cancelled_flights,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                (
                    SELECT CancellationCode
                    FROM filtered f2
                    WHERE f2.is_cancelled
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS most_common_cancellation_reason,
                (
                    SELECT COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)
                    FROM filtered f3
                    WHERE f3.is_cancelled
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS airline_with_most_cancellations,
                (
                    SELECT Origin
                    FROM filtered f4
                    WHERE f4.is_cancelled
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS airport_with_most_cancellations,
                SUM(CASE WHEN is_diverted THEN 1 ELSE 0 END) AS total_diverted_flights,
                AVG(CASE WHEN is_diverted THEN 1.0 ELSE 0.0 END) AS diversion_rate
            FROM filtered
            """,
        )
        payload = self._query_df(sql, params).iloc[0].to_dict()
        payload["most_common_cancellation_reason_label"] = cancellation_reason_label(
            payload["most_common_cancellation_reason"]
        )
        return payload

    def get_cancellations_by_month(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                flight_month,
                flight_month_name,
                SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_flights,
                SUM(CASE WHEN is_diverted THEN 1 ELSE 0 END) AS diverted_flights
            FROM filtered
            GROUP BY 1, 2
            ORDER BY flight_month
            """,
        )
        return self._query_df(sql, params)

    def get_cancellations_by_airline(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) AS airline_code,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                SUM(CASE WHEN is_diverted THEN 1 ELSE 0 END) AS diverted_flights
            FROM filtered
            GROUP BY 1
            ORDER BY cancellation_rate DESC, diverted_flights DESC
            LIMIT 12
            """,
        )
        return self._query_df(sql, params)

    def get_cancellation_reasons(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT COALESCE(CancellationCode, 'Unknown') AS cancellation_code, COUNT(*) AS flights
            FROM filtered
            WHERE is_cancelled
            GROUP BY 1
            ORDER BY flights DESC
            """,
        )
        frame = self._query_df(sql, params)
        frame["reason_label"] = frame["cancellation_code"].map(cancellation_reason_label)
        return frame

    def get_map_airports(self, filters: GlobalFilterState) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            """
            SELECT
                Origin AS airport_code,
                MAX(origin_airport_name) AS airport_name,
                MAX(origin_city) AS city,
                MAX(origin_latitude) AS latitude,
                MAX(origin_longitude) AS longitude,
                COUNT(*) AS total_departures,
                AVG(DepDelay) AS avg_departure_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                MAX(origin_runway_count) AS runway_count,
                (
                    SELECT Dest
                    FROM filtered f2
                    WHERE f2.Origin = filtered.Origin
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS top_destination
            FROM filtered
            WHERE origin_latitude IS NOT NULL AND origin_longitude IS NOT NULL
            GROUP BY 1
            ORDER BY total_departures DESC
            LIMIT 250
            """,
        )
        return self._query_df(sql, params)

    def get_map_routes(self, filters: GlobalFilterState, limit: int = 120) -> pd.DataFrame:
        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                route,
                Origin,
                Dest,
                MAX(origin_airport_name) AS origin_airport_name,
                MAX(dest_airport_name) AS dest_airport_name,
                MAX(origin_latitude) AS origin_latitude,
                MAX(origin_longitude) AS origin_longitude,
                MAX(dest_latitude) AS dest_latitude,
                MAX(dest_longitude) AS dest_longitude,
                COUNT(*) AS total_flights,
                AVG(ArrDelay) AS avg_arrival_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                mode(COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)) AS most_common_airline
            FROM filtered
            WHERE origin_latitude IS NOT NULL
              AND origin_longitude IS NOT NULL
              AND dest_latitude IS NOT NULL
              AND dest_longitude IS NOT NULL
            GROUP BY 1, 2, 3
            ORDER BY total_flights DESC
            LIMIT {int(limit)}
            """,
        )
        return self._query_df(sql, params)

    def get_flights_page(
        self,
        filters: GlobalFilterState,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        search_term: str = "",
        sort_by: str = "FlightDate",
        sort_direction: str = "DESC",
    ) -> tuple[pd.DataFrame, int]:
        safe_sort_columns = {
            "FlightDate",
            "IATA_CODE_Reporting_Airline",
            "Reporting_Airline",
            "Origin",
            "Dest",
            "DepDelay",
            "ArrDelay",
            "Distance",
            "flight_row_id",
        }
        sort_column = sort_by if sort_by in safe_sort_columns else "FlightDate"
        direction = "ASC" if sort_direction.upper() == "ASC" else "DESC"
        offset = max(page - 1, 0) * page_size
        extra_clause = ""
        extra_params: list[Any] = []
        if search_term.strip():
            extra_clause = """
                AND (
                    route ILIKE ?
                    OR Origin ILIKE ?
                    OR Dest ILIKE ?
                    OR COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) ILIKE ?
                    OR CAST(Flight_Number_Reporting_Airline AS VARCHAR) ILIKE ?
                )
            """
            token = f"%{search_term.strip()}%"
            extra_params.extend([token, token, token, token, token])

        count_sql, count_params = self._filtered_cte(
            filters,
            f"SELECT COUNT(*) AS total_rows FROM filtered WHERE 1 = 1 {extra_clause}",
            extra_params,
        )
        total_rows = int(self._query_df(count_sql, count_params).iloc[0]["total_rows"])

        data_sql, data_params = self._filtered_cte(
            filters,
            f"""
            SELECT
                flight_row_id,
                FlightDate,
                COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) AS airline,
                Flight_Number_Reporting_Airline,
                Origin,
                origin_airport_name,
                Dest,
                dest_airport_name,
                crs_dep_time_label,
                dep_time_label,
                DepDelay,
                crs_arr_time_label,
                arr_time_label,
                ArrDelay,
                is_cancelled,
                CancellationCode,
                is_diverted,
                Distance,
                CarrierDelay,
                WeatherDelay,
                NASDelay,
                SecurityDelay,
                LateAircraftDelay
            FROM filtered
            WHERE 1 = 1
            {extra_clause}
            ORDER BY {sort_column} {direction}, flight_row_id ASC
            LIMIT {int(page_size)} OFFSET {int(offset)}
            """,
            extra_params,
        )
        return self._query_df(data_sql, data_params), total_rows

    def get_flight_detail(self, flight_row_id: int) -> dict[str, Any]:
        sql = """
            SELECT
                flight_row_id,
                FlightDate,
                COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline) AS airline,
                Flight_Number_Reporting_Airline,
                route,
                Origin,
                origin_airport_name,
                Dest,
                dest_airport_name,
                crs_dep_time_label,
                dep_time_label,
                DepDelay,
                crs_arr_time_label,
                arr_time_label,
                ArrDelay,
                is_cancelled,
                CancellationCode,
                is_diverted,
                Distance,
                CarrierDelay,
                WeatherDelay,
                NASDelay,
                SecurityDelay,
                LateAircraftDelay
            FROM flights_enriched
            WHERE flight_row_id = ?
        """
        frame = self._query_df(sql, [flight_row_id])
        return {} if frame.empty else frame.iloc[0].to_dict()

    def get_data_quality(self, filters: GlobalFilterState) -> dict[str, Any]:
        overall = self._query_df("SELECT * FROM data_quality_summary").iloc[0].to_dict()
        rows_by_file = self._query_df(
            "SELECT source_file, COUNT(*) AS rows_loaded FROM flights_enriched GROUP BY 1 ORDER BY 1"
        )
        missing_summary = self._query_df(
            """
            SELECT * FROM (
                VALUES
                    ('DepDelay', (SELECT SUM(CASE WHEN DepDelay IS NULL THEN 1 ELSE 0 END) FROM flights_enriched)),
                    ('ArrDelay', (SELECT SUM(CASE WHEN ArrDelay IS NULL THEN 1 ELSE 0 END) FROM flights_enriched)),
                    ('CancellationCode', (SELECT SUM(CASE WHEN CancellationCode IS NULL OR CancellationCode = '' THEN 1 ELSE 0 END) FROM flights_enriched)),
                    ('origin_airport_name', (SELECT SUM(CASE WHEN origin_airport_name IS NULL THEN 1 ELSE 0 END) FROM flights_enriched)),
                    ('dest_airport_name', (SELECT SUM(CASE WHEN dest_airport_name IS NULL THEN 1 ELSE 0 END) FROM flights_enriched))
            ) AS t(column_name, missing_rows)
            ORDER BY missing_rows DESC
            """
        )
        delay_distribution = self._query_df(
            """
            SELECT ArrDelay
            FROM flights_enriched
            WHERE ArrDelay IS NOT NULL
            LIMIT 60000
            """
        )
        status_sql, status_params = self._filtered_cte(
            filters,
            """
            SELECT
                COUNT(*) AS filtered_rows,
                SUM(CASE WHEN origin_airport_name IS NULL THEN 1 ELSE 0 END) AS filtered_origin_misses,
                SUM(CASE WHEN dest_airport_name IS NULL THEN 1 ELSE 0 END) AS filtered_dest_misses
            FROM filtered
            """,
        )
        filtered = self._query_df(status_sql, status_params).iloc[0].to_dict()
        return {
            "overall": overall,
            "filtered": filtered,
            "rows_by_file": rows_by_file,
            "missing_summary": missing_summary,
            "delay_distribution": delay_distribution,
        }

    def get_comparison_metrics(
        self,
        filters: GlobalFilterState,
        entity_type: str,
        left_value: str,
        right_value: str,
    ) -> pd.DataFrame:
        field_map = {
            "Airline": "COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)",
            "Airport": "Origin",
            "Route": "route",
            "Month": "flight_month_name",
            "Weekday": "flight_weekday_name",
        }
        field = field_map[entity_type]
        sql, params = self._filtered_cte(
            filters,
            f"""
            SELECT
                {field} AS entity,
                COUNT(*) AS total_flights,
                AVG(ArrDelay) AS avg_delay,
                AVG(CASE WHEN is_delayed_15 THEN 1.0 ELSE 0.0 END) AS delay_rate,
                AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) AS cancellation_rate,
                AVG(CASE WHEN is_completed AND NOT is_delayed_15 THEN 1.0 ELSE 0.0 END) AS on_time_percentage,
                AVG(CASE WHEN is_severely_delayed_60 THEN 1.0 ELSE 0.0 END) AS severe_delay_rate,
                mode(main_delay_cause) AS main_delay_cause
            FROM filtered
            WHERE {field} IN (?, ?)
            GROUP BY 1
            ORDER BY entity
            """,
            [left_value, right_value],
        )
        return self._query_df(sql, params)

    def get_entity_options(self, entity_type: str) -> list[str]:
        field_map = {
            "Airline": "COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)",
            "Airport": "Origin",
            "Route": "route",
            "Month": "flight_month_name",
            "Weekday": "flight_weekday_name",
        }
        field = field_map[entity_type]
        frame = self._query_df(
            f"SELECT DISTINCT {field} AS entity FROM flights_enriched WHERE {field} IS NOT NULL ORDER BY 1"
        )
        return frame["entity"].tolist()

    def export_summary_payload(self, filters: GlobalFilterState) -> dict[str, Any]:
        return {
            "filters": asdict(filters),
            "overview_metrics": self.get_overview_metrics(filters),
        }

    def get_dataset_overview(self) -> dict[str, Any]:
        return self._query_df("SELECT * FROM data_quality_summary").iloc[0].to_dict()

    def _filtered_cte(
        self,
        filters: GlobalFilterState,
        query_body: str,
        extra_params: list[Any] | None = None,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        def add_in(column: str, values: list[str]) -> None:
            if not values:
                return
            placeholders = ", ".join(["?"] * len(values))
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)

        if filters.start_date:
            clauses.append("FlightDate >= ?")
            params.append(filters.start_date)
        if filters.end_date:
            clauses.append("FlightDate <= ?")
            params.append(filters.end_date)

        add_in("flight_month_name", filters.month)
        add_in("flight_weekday_name", filters.weekday)
        add_in("COALESCE(IATA_CODE_Reporting_Airline, Reporting_Airline)", filters.airline)
        add_in("Origin", filters.origin)
        add_in("Dest", filters.dest)
        add_in("route", filters.route)
        add_in("distance_group", filters.distance_group)
        add_in("time_of_day_group", filters.time_of_day_group)

        if filters.delay_threshold > 0:
            clauses.append("GREATEST(COALESCE(DepDelayMinutes, 0), COALESCE(ArrDelayMinutes, 0)) >= ?")
            params.append(filters.delay_threshold)
        if filters.cancelled == "Yes":
            clauses.append("is_cancelled = TRUE")
        elif filters.cancelled == "No":
            clauses.append("is_cancelled = FALSE")
        if filters.diverted == "Yes":
            clauses.append("is_diverted = TRUE")
        elif filters.diverted == "No":
            clauses.append("is_diverted = FALSE")

        where_clause = ""
        if clauses:
            where_clause = "WHERE " + " AND ".join(clauses)
        sql = f"WITH filtered AS (SELECT * FROM flights_enriched {where_clause}) {query_body}"
        if extra_params:
            params.extend(extra_params)
        return sql, params

    def _query_df(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        connection = duckdb.connect(str(self.db_path), read_only=True)
        try:
            return connection.execute(sql, params or []).df()
        finally:
            connection.close()

    def _distinct_values(self, expression: str) -> list[str]:
        frame = self._query_df(
            f"SELECT DISTINCT {expression} AS value FROM flights_enriched WHERE {expression} IS NOT NULL ORDER BY 1"
        )
        return frame["value"].tolist()
