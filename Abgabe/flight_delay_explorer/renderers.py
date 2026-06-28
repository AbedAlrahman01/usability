from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import streamlit as st
from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder

from flight_delay_explorer.maps import build_airport_map, build_route_map
from flight_delay_explorer.models import GlobalFilterState
from flight_delay_explorer.repository import FlightDelayRepository
from flight_delay_explorer.ui import (
    render_chart_summary,
    render_data_toggle,
    render_detail_table,
    render_filter_summary,
    render_hero,
    render_info_panel,
    render_insight,
    render_kpis,
    render_page_intro,
    render_section_header,
)
from flight_delay_explorer.utils import (
    cancellation_reason_label,
    df_to_csv_bytes,
    figure_download_config,
    format_int,
    format_minutes,
    format_percent,
    json_bytes,
)
from flight_delay_explorer.visuals import (
    apply_figure_style,
    bar_chart,
    donut_chart,
    heatmap_chart,
    histogram_chart,
    line_chart,
    stacked_area_chart,
    stacked_bar_chart,
)


def render_overview_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_hero(
        "Flight Delay Explorer",
        "A premium Q1 2024 aviation data viewer for route reliability, airline performance, airport congestion, and cancellation risk across the U.S. network.",
    )
    render_filter_summary(filters)

    metrics = repo.get_overview_metrics(filters)
    monthly = repo.get_monthly_trends(filters)
    airline_ranking = repo.get_top_airlines(filters, limit=10)
    origin_airports = repo.get_top_airports(filters, mode="origin", limit=10)
    distribution = repo.get_delay_distribution(filters)
    map_airports = repo.get_map_airports(filters)

    render_kpis(
        [
            {"label": "Total Flights", "value": format_int(metrics["total_flights"]), "caption": "Selected network volume"},
            {"label": "Delayed Flights", "value": format_int(metrics["delayed_flights"]), "caption": f"Delay rate {format_percent(metrics['delay_rate'])}"},
            {"label": "Cancelled Flights", "value": format_int(metrics["cancelled_flights"]), "caption": f"Cancellation rate {format_percent(metrics['cancellation_rate'])}"},
            {"label": "Avg Departure Delay", "value": format_minutes(metrics["avg_departure_delay"]), "caption": "Across the current filtered set"},
            {"label": "Avg Arrival Delay", "value": format_minutes(metrics["avg_arrival_delay"]), "caption": "Arrival reliability at a glance"},
            {"label": "Busiest Airline", "value": str(metrics["busiest_airline"] or "N/A"), "caption": "Largest carrier in the current slice"},
        ]
    )

    if not monthly.empty:
        highest_month = monthly.sort_values("avg_arrival_delay", ascending=False).iloc[0]
        render_insight(
            f"{highest_month['flight_month_name']} has the highest average arrival delay in the current selection at {format_minutes(highest_month['avg_arrival_delay'])}."
        )

    _plot(
        line_chart(monthly, x="flight_month_name", y=["total_flights", "delay_rate"], title="Flights and Delay Rate by Month"),
        "overview_monthly",
        summary="Monthly traffic and delay pressure are shown together, with January through March forming the current analytic window.",
        data=monthly[["flight_month_name", "total_flights", "delay_rate", "avg_departure_delay", "avg_arrival_delay"]],
    )

    render_section_header("Network Hero Map", "Real airport coordinates and traffic hotspots make the geographic story accessible without relying on hover alone.")
    st.pydeck_chart(build_airport_map(map_airports, mode="traffic"), use_container_width=True, height=520)
    render_chart_summary("Airport bubble size shows traffic volume, while the table and selector below provide a keyboard-friendly path to the same airport details.")
    render_data_toggle("View rendered airport data", map_airports)

    status_tab, airline_tab, airport_tab, distribution_tab = st.tabs(
        ["Operational status", "Airline traffic", "Airport traffic", "Delay distribution"]
    )
    with status_tab:
        status_frame = pd.DataFrame(
            {
                "status": ["Completed", "Cancelled", "Diverted"],
                "value": [
                    metrics["completed_flights"] or 0,
                    metrics["cancelled_flights"] or 0,
                    metrics["diverted_flights"] or 0,
                ],
            }
        )
        _plot(
            donut_chart(status_frame, "status", "value", "Operational Status Mix"),
            "overview_status",
            summary="Completed flights dominate the selected slice, with cancelled and diverted operations isolated as smaller disruption categories.",
            data=status_frame,
        )
    with airline_tab:
        _plot(
            bar_chart(airline_ranking, x="airline_code", y="flights", title="Top Airlines by Flight Count", text_auto=".2s"),
            "overview_airlines",
            summary="The top carriers by visible traffic are listed directly and can be compared without relying on color alone.",
            data=airline_ranking[["airline_code", "flights", "avg_arrival_delay", "delay_rate", "cancellation_rate"]],
        )
    with airport_tab:
        _plot(
            bar_chart(origin_airports, x="airport_code", y="flights", title="Top Origin Airports by Flight Count", text_auto=".2s"),
            "overview_airports",
            summary="The busiest origin airports are ranked explicitly by count, with their delay and cancellation rates available in the fallback table.",
            data=origin_airports[["airport_code", "flights", "avg_delay", "cancellation_rate"]],
        )
    with distribution_tab:
        if not distribution.empty:
            _plot(
                histogram_chart(distribution, "ArrDelay", "Arrival Delay Distribution"),
                "overview_distribution",
                summary="Arrival delays are distributed across early, on-time, and severely delayed flights; the table fallback exposes raw sampled values.",
                data=distribution.head(200),
                table_label="View delay sample table",
            )

    summary_json = repo.export_summary_payload(filters)
    st.download_button(
        "Download Summary JSON",
        data=json_bytes(summary_json),
        file_name="flight_delay_summary.json",
        use_container_width=True,
    )
    st.caption("Plotly charts include PNG export in the toolbar. PDF export remains available via browser print for the overview report layout.")


def render_time_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Time Analysis",
        "When the network gets stressed matters as much as where it gets stressed. This page reveals the seasonal, hourly, and weekday rhythm of delay build-up.",
    )
    render_filter_summary(filters)
    monthly = repo.get_monthly_trends(filters)
    summary = repo.get_time_summary(filters)
    heatmap = repo.get_time_heatmap(filters)

    if not monthly.empty:
        worst = monthly.sort_values("avg_departure_delay", ascending=False).iloc[0]
        render_insight(
            f"{worst['flight_month_name']} is the sharpest month operationally, with average departure delay at {format_minutes(worst['avg_departure_delay'])}."
        )

    _plot(
        line_chart(monthly, "flight_month_name", ["avg_departure_delay", "avg_arrival_delay"], "Average Delay by Month"),
        "time_monthly_delay",
        summary="Departure and arrival delays are shown with separate line styles and markers so the comparison still works without color perception.",
        data=monthly[["flight_month_name", "avg_departure_delay", "avg_arrival_delay", "cancellation_rate"]],
    )

    timing_tab, cancellation_tab = st.tabs(["Weekday and hourly", "Monthly cancellation"])
    with timing_tab:
        _plot(
            bar_chart(summary["weekday"], "flight_weekday_name", "delay_rate", "Delay Rate by Weekday"),
            "time_weekday",
            summary="Weekdays are ordered and labeled directly so the most delay-prone day can be identified without interpreting color alone.",
            data=summary["weekday"],
        )
        _plot(
            bar_chart(summary["hourly"], "departure_hour", "avg_departure_delay", "Average Delay by Departure Hour"),
            "time_hourly",
            summary="Departure-hour delays highlight the daily pressure build-up; precise values remain available in the data toggle.",
            data=summary["hourly"],
        )
    with cancellation_tab:
        _plot(
            line_chart(monthly, "flight_month_name", "cancellation_rate", "Cancellation Rate by Month"),
            "time_cancel_rate",
            summary="Cancellation rates remain visible month by month and use direct labels plus a data table fallback for accessibility.",
            data=monthly[["flight_month_name", "cancellation_rate"]],
        )

    _plot(
        heatmap_chart(heatmap, "departure_hour", "flight_weekday_name", "avg_arrival_delay", "Weekday x Departure Hour Heatmap"),
        "time_heatmap",
        summary="The heatmap shows average arrival delay by weekday and departure hour, with the table fallback exposing the underlying matrix values.",
        data=heatmap,
    )

    if not summary["time_of_day"].empty:
        _plot(
            bar_chart(summary["time_of_day"], "time_of_day_group", "delay_rate", "Delay Rate by Time of Day"),
            "time_of_day",
            summary="Time-of-day groups provide a simplified alternative to the heatmap for first-time and mobile users.",
            data=summary["time_of_day"],
        )


def render_airlines_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Airline Analysis",
        "Compare reliability, punctuality, and severe-delay exposure across carriers without losing the elegance of an executive dashboard.",
    )
    render_filter_summary(filters)
    ranking = repo.get_top_airlines(filters, limit=15)
    causes = repo.get_delay_cause_by_airline(filters, limit=10)

    if not ranking.empty:
        worst = ranking.sort_values("avg_arrival_delay", ascending=False).iloc[0]
        render_insight(
            f"{worst['airline_code']} shows the highest average arrival delay among the current leading carriers at {format_minutes(worst['avg_arrival_delay'])}."
        )

    _plot(
        bar_chart(ranking, "airline_code", "avg_arrival_delay", "Average Arrival Delay by Airline"),
        "airline_avg_delay",
        summary="Airlines are ranked explicitly by average arrival delay, so the ordering carries the comparison even without color.",
        data=ranking[["airline_code", "avg_arrival_delay", "delay_rate", "cancellation_rate", "on_time_percentage"]],
    )

    rate_tab, cancel_tab, ontime_tab = st.tabs(["Delay rate", "Cancellation rate", "On-time percentage"])
    with rate_tab:
        _plot(
            bar_chart(ranking, "airline_code", "delay_rate", "Delay Rate by Airline"),
            "airline_delay_rate",
            summary="Delay rates are labeled directly for each airline and paired with a data table fallback.",
            data=ranking[["airline_code", "delay_rate"]],
        )
    with cancel_tab:
        _plot(
            bar_chart(ranking, "airline_code", "cancellation_rate", "Cancellation Rate by Airline"),
            "airline_cancel_rate",
            summary="Cancellation performance is exposed separately so it is not hidden behind the delay charts.",
            data=ranking[["airline_code", "cancellation_rate"]],
        )
    with ontime_tab:
        _plot(
            bar_chart(ranking, "airline_code", "on_time_percentage", "On-Time Percentage by Airline"),
            "airline_ontime",
            summary="On-time percentage gives a positive reliability view and reduces reliance on only negative delay metrics.",
            data=ranking[["airline_code", "on_time_percentage"]],
        )

    if not causes.empty:
        _plot(
            stacked_bar_chart(causes, "airline_code", ["carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"], "Delay Causes by Airline"),
            "airline_causes",
            summary="Delay-cause stacks use both color and pattern shapes so cause categories remain distinguishable when color perception is limited.",
            data=causes,
        )

    st.dataframe(ranking, use_container_width=True, hide_index=True)


def render_airports_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Airport Analysis",
        "Read congestion, cancellation, taxi performance, and airport infrastructure side by side with origin and destination modes.",
    )
    render_filter_summary(filters)
    mode = st.segmented_control("Airport mode", ["Origin", "Destination"], default="Origin")
    mode_key = "origin" if mode == "Origin" else "destination"
    ranking = repo.get_top_airports(filters, mode=mode_key, limit=15)

    if not ranking.empty:
        leader = ranking.sort_values("avg_delay", ascending=False).iloc[0]
        render_insight(
            f"{leader['airport_code']} currently leads the selected airports for average delay at {format_minutes(leader['avg_delay'])}."
        )

    _plot(
        bar_chart(ranking, "airport_code", "avg_delay", f"{mode} Airport Average Delay"),
        f"airport_{mode_key}_delay",
        summary=f"{mode} airports are ranked explicitly by average delay, with precise values available in the accessible table.",
        data=ranking[["airport_code", "avg_delay", "flights", "cancellation_rate"]],
    )

    traffic_tab, cancel_tab, taxi_tab = st.tabs(["Traffic", "Cancellation", "Taxi performance"])
    with traffic_tab:
        _plot(
            bar_chart(ranking, "airport_code", "flights", f"Busiest {mode} Airports"),
            f"airport_{mode_key}_traffic",
            summary=f"Traffic counts reveal the busiest {mode.lower()} airports in the selected slice.",
            data=ranking[["airport_code", "flights"]],
        )
    with cancel_tab:
        _plot(
            bar_chart(ranking, "airport_code", "cancellation_rate", f"{mode} Airport Cancellation Rate"),
            f"airport_{mode_key}_cancel",
            summary=f"Cancellation rates are separated from delay so disruption can be read independently of traffic volume.",
            data=ranking[["airport_code", "cancellation_rate"]],
        )
    with taxi_tab:
        taxi_metric = "avg_taxi_out" if mode_key == "origin" else "avg_taxi_in"
        _plot(
            bar_chart(ranking, "airport_code", taxi_metric, f"{mode} Airport Taxi Performance"),
            f"airport_{mode_key}_taxi",
            summary="Taxi performance acts as an operational friction indicator alongside delay and cancellation metrics.",
            data=ranking[["airport_code", taxi_metric]],
        )

    if not ranking.empty:
        selected_airport = st.selectbox("Airport detail", ranking["airport_code"].tolist())
        detail = repo.get_airport_detail(filters, selected_airport)
        top_routes = repo.get_airport_top_routes(filters, selected_airport)
        render_kpis(
            [
                {"label": "Airport", "value": selected_airport, "caption": str(detail.get("airport_name") or "Airport detail")},
                {"label": "Departures", "value": format_int(detail.get("total_departures")), "caption": "Outbound segments in selection"},
                {"label": "Arrivals", "value": format_int(detail.get("total_arrivals")), "caption": "Inbound segments in selection"},
                {"label": "Runways", "value": format_int(detail.get("runway_count")), "caption": "Infrastructure context"},
            ]
        )
        detail_tab, route_tab = st.tabs(["Airport details", "Top routes"])
        with detail_tab:
            render_detail_table(
                "Airport details",
                {
                    "airport_code": detail.get("airport_code"),
                    "airport_name": detail.get("airport_name"),
                    "city": detail.get("city"),
                    "region_name": detail.get("region_name"),
                    "country_name": detail.get("country_name"),
                    "avg_departure_delay": format_minutes(detail.get("avg_departure_delay")),
                    "avg_arrival_delay": format_minutes(detail.get("avg_arrival_delay")),
                    "cancellation_rate": format_percent(detail.get("cancellation_rate")),
                    "longest_runway_ft": format_int(detail.get("longest_runway")),
                    "frequency_count": format_int(detail.get("frequency_count")),
                },
            )
        with route_tab:
            _plot(
                bar_chart(top_routes, "route", "flights", "Top Routes From This Airport"),
                f"airport_routes_{selected_airport}",
                summary="Top routes from the selected airport are listed directly so the network context is readable without hover interactions.",
                data=top_routes,
            )

    st.dataframe(ranking, use_container_width=True, hide_index=True)


def render_routes_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Route Analysis",
        "See which city pairs move the most traffic, which corridors absorb the worst delays, and which airline wins or loses on each route.",
    )
    render_filter_summary(filters)
    ranking = repo.get_route_ranking(filters, limit=20)

    if not ranking.empty:
        busiest = ranking.iloc[0]
        render_insight(
            f"{busiest['route']} is the busiest route in the current slice with {format_int(busiest['total_flights'])} flights."
        )

    _plot(
        bar_chart(ranking.head(12), "route", "total_flights", "Busiest Routes"),
        "route_busiest",
        summary="The busiest routes are ordered by traffic count, making the primary corridor ranking readable without depending on chart color.",
        data=ranking[["route", "total_flights", "avg_arrival_delay", "delay_rate"]].head(12),
    )
    delay_sorted = ranking.sort_values("avg_arrival_delay", ascending=False).head(12)
    _plot(
        bar_chart(delay_sorted, "route", "avg_arrival_delay", "Most Delayed Routes"),
        "route_delayed",
        summary="Most delayed routes are shown separately from traffic so high-delay corridors are visible even when they are not the busiest.",
        data=delay_sorted[["route", "avg_arrival_delay", "delay_rate", "cancellation_rate"]],
    )

    if not ranking.empty:
        selected_route = st.selectbox("Route detail", ranking["route"].tolist())
        detail = repo.get_route_detail(filters, selected_route)
        render_kpis(
            [
                {"label": "Route", "value": selected_route, "caption": "Selected corridor"},
                {"label": "Flights", "value": format_int(detail.get("total_flights")), "caption": "Traffic volume"},
                {"label": "Avg Arrival Delay", "value": format_minutes(detail.get("avg_arrival_delay")), "caption": f"Delay rate {format_percent(detail.get('delay_rate'))}"},
                {"label": "Best Airline", "value": str(detail.get("best_airline") or "N/A"), "caption": f"Worst airline {detail.get('worst_airline') or 'N/A'}"},
            ]
        )
        render_detail_table(
            "Route details",
            {
                "route": detail.get("route"),
                "total_flights": format_int(detail.get("total_flights")),
                "avg_departure_delay": format_minutes(detail.get("avg_departure_delay")),
                "avg_arrival_delay": format_minutes(detail.get("avg_arrival_delay")),
                "delay_rate": format_percent(detail.get("delay_rate")),
                "cancellation_rate": format_percent(detail.get("cancellation_rate")),
                "distance_miles": format_int(detail.get("distance")),
                "best_airline": detail.get("best_airline"),
                "worst_airline": detail.get("worst_airline"),
                "worst_month": detail.get("worst_month"),
                "best_departure_hour": detail.get("best_departure_hour"),
            },
        )

    st.dataframe(ranking, use_container_width=True, hide_index=True)


def render_delay_causes_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Delay Causes",
        "Break delay minutes into their operational origins so the story moves from what happened to why it happened.",
    )
    render_filter_summary(filters)
    cause_totals = repo.get_delay_cause_breakdown(filters)
    cause_by_airline = repo.get_delay_cause_by_airline(filters, limit=10)
    cause_by_airport = repo.get_delay_cause_by_airport(filters, limit=10)
    cause_over_time = repo.get_delay_cause_over_time(filters)

    if not cause_totals.empty:
        biggest = cause_totals.sort_values("delay_minutes", ascending=False).iloc[0]
        render_insight(
            f"{biggest['cause']} is the dominant delay source in the current slice, accounting for {format_int(biggest['delay_minutes'])} total minutes."
        )

    _plot(
        bar_chart(cause_totals, "cause", "delay_minutes", "Total Delay Minutes by Cause"),
        "causes_totals",
        summary="Delay causes are ranked and labeled directly so the dominant source is clear without relying on color.",
        data=cause_totals,
    )

    share_tab, airline_tab, airport_tab, time_tab = st.tabs(["Cause share", "By airline", "By airport", "Over time"])
    with share_tab:
        _plot(
            donut_chart(cause_totals, "cause", "delay_minutes", "Delay Cause Share"),
            "causes_share",
            summary="The cause share view complements the ranked bar chart and is paired with a table fallback for exact percentages.",
            data=cause_totals,
        )
    with airline_tab:
        _plot(
            stacked_bar_chart(cause_by_airline, "airline_code", ["carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"], "Delay Causes by Airline"),
            "causes_airline",
            summary="Patterned stacks provide a color-independent way to distinguish delay-cause categories across airlines.",
            data=cause_by_airline,
        )
    with airport_tab:
        _plot(
            stacked_bar_chart(cause_by_airport, "airport_code", ["carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"], "Delay Causes by Airport"),
            "causes_airport",
            summary="Airport delay-cause mixes use both color and pattern, and the data table preserves the exact totals.",
            data=cause_by_airport,
        )
    with time_tab:
        if not cause_over_time.empty:
            _plot(
                stacked_area_chart(
                    cause_over_time,
                    "flight_month_name",
                    ["carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"],
                    "Delay Causes Over Time",
                ),
                "causes_time",
                summary="Cause trends over time use different line styles on the stacked boundaries and a data table fallback for exact month totals.",
                data=cause_over_time,
            )


def render_cancellations_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Cancellation and Diversion",
        "Special-case operations deserve their own lens. This page isolates instability, reason codes, and diversion exposure.",
    )
    render_filter_summary(filters)
    metrics = repo.get_cancellation_metrics(filters)
    monthly = repo.get_cancellations_by_month(filters)
    airline = repo.get_cancellations_by_airline(filters)
    reasons = repo.get_cancellation_reasons(filters)
    overview = repo.get_overview_metrics(filters)

    render_kpis(
        [
            {"label": "Cancelled Flights", "value": format_int(metrics["total_cancelled_flights"]), "caption": f"Rate {format_percent(metrics['cancellation_rate'])}"},
            {"label": "Diversions", "value": format_int(metrics["total_diverted_flights"]), "caption": f"Rate {format_percent(metrics['diversion_rate'])}"},
            {"label": "Top Cancellation Reason", "value": metrics["most_common_cancellation_reason_label"], "caption": "Mapped from BTS reason codes"},
            {"label": "Most Affected Airline", "value": str(metrics["airline_with_most_cancellations"] or "N/A"), "caption": "Highest cancellation count"},
        ]
    )
    render_insight(
        f"{metrics['most_common_cancellation_reason_label']} is the most common cancellation reason in the current selection."
    )

    _plot(
        line_chart(monthly, "flight_month_name", ["cancelled_flights", "diverted_flights"], "Cancelled and Diverted Flights by Month"),
        "cancel_monthly",
        summary="Cancelled and diverted flights are shown with separate line styles and exact monthly values in the fallback table.",
        data=monthly,
    )

    reason_tab, airline_tab, status_tab = st.tabs(["Reason share", "By airline", "Status mix"])
    with reason_tab:
        _plot(
            donut_chart(reasons, "reason_label", "flights", "Cancellation Reasons"),
            "cancel_reasons",
            summary="Cancellation reasons are labeled directly and mapped from BTS codes so the chart is understandable without code memorization.",
            data=reasons,
        )
    with airline_tab:
        _plot(
            bar_chart(airline, "airline_code", "cancellation_rate", "Cancellation Rate by Airline"),
            "cancel_airline",
            summary="Airline cancellation rates are shown independently from diversions and include a full data table fallback.",
            data=airline,
        )
    with status_tab:
        status_frame = pd.DataFrame(
            {
                "status": ["Cancelled", "Delayed", "On Time"],
                "value": [
                    metrics["total_cancelled_flights"] or 0,
                    overview["delayed_flights"] or 0,
                    max((overview["completed_flights"] or 0) - (overview["delayed_flights"] or 0), 0),
                ],
            }
        )
        _plot(
            donut_chart(status_frame, "status", "value", "Cancelled vs Delayed vs On Time"),
            "cancel_status_mix",
            summary="The disruption mix shows cancelled, delayed, and on-time outcomes together, with the exact counts preserved below the chart.",
            data=status_frame,
        )


def render_map_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Map View",
        "This is the showcase layer: actual airport coordinates, route arcs, and geographic context for reliability, traffic, and cancellation exposure.",
    )
    render_filter_summary(filters)
    airports = repo.get_map_airports(filters)
    routes = repo.get_map_routes(filters)
    airport_display = airports.copy()
    route_display = routes.copy()
    mode = st.segmented_control(
        "Map mode",
        ["Airport traffic", "Airport delay", "Airport cancellation", "Route network"],
        default="Airport traffic",
    )

    if mode == "Route network":
        render_info_panel(
            "How to Read This Map",
            "Each **line** represents a route between two airports. **Thicker lines** mean more flights on that route. "
            "**Warmer line colors** indicate higher average arrival delay. The route table and selector below provide a keyboard path to the same details, and each route also carries a textual delay band."
        )
        route_display["delay_band"] = route_display["avg_arrival_delay"].apply(_delay_band)
        st.pydeck_chart(build_route_map(routes), use_container_width=True, height=640)
        render_chart_summary("Use the route selector below if you cannot rely on hover. The table exposes the same route-level delay and volume information as the map.")
        render_data_toggle("View rendered route data", route_display)
        if not routes.empty:
            selected_route = st.selectbox("Select route from the rendered map", routes["route"].tolist())
            detail = repo.get_route_detail(filters, selected_route)
            render_detail_table(
                "Route map details",
                {
                    "route": detail.get("route"),
                    "total_flights": format_int(detail.get("total_flights")),
                    "avg_arrival_delay": format_minutes(detail.get("avg_arrival_delay")),
                    "delay_band": _delay_band(detail.get("avg_arrival_delay")),
                    "delay_rate": format_percent(detail.get("delay_rate")),
                    "cancellation_rate": format_percent(detail.get("cancellation_rate")),
                    "best_airline": detail.get("best_airline"),
                    "worst_airline": detail.get("worst_airline"),
                    "worst_month": detail.get("worst_month"),
                },
            )
            render_insight(
                f"{selected_route} is available through both the map and the keyboard selector, so the route story is not pointer-only."
            )
    else:
        airport_mode = {
            "Airport traffic": "traffic",
            "Airport delay": "delay",
            "Airport cancellation": "cancellation",
        }[mode]
        if mode == "Airport delay":
            render_info_panel(
                "How to Read This Map",
                "Bubble size shows total departures. **Color** and **outline thickness** together show delay severity. "
                "Lower delay, moderate delay, high delay, and severe delay are also exposed as text in the data table and the airport selector below."
            )
            airport_display["severity_band"] = airport_display["avg_departure_delay"].apply(_delay_band)
        elif mode == "Airport cancellation":
            render_info_panel(
                "How to Read This Map",
                "Bubble size shows total departures. **Color** and **outline thickness** together show cancellation risk, with textual risk bands available below for keyboard users."
            )
            airport_display["severity_band"] = airport_display["cancellation_rate"].apply(_risk_band)
        else:
            render_info_panel(
                "How to Read This Map",
                "Bubble size shows traffic volume. Delay-rate severity is also exposed through outline thickness and the table fallback, not only by bubble color."
            )
            airport_display["severity_band"] = airport_display["delay_rate"].apply(_risk_band)
        st.pydeck_chart(build_airport_map(airports, mode=airport_mode), use_container_width=True, height=640)
        render_chart_summary("Use the airport selector below if you cannot rely on hover. The selector and table expose the same airport-level details as the map.")
        render_data_toggle("View rendered airport data", airport_display)
        if not airports.empty:
            selected_airport = st.selectbox("Select airport from the rendered map", airports["airport_code"].tolist())
            detail = repo.get_airport_detail(filters, selected_airport)
            if mode == "Airport delay":
                severity_label = _delay_band(detail.get("avg_departure_delay"))
            elif mode == "Airport cancellation":
                severity_label = _risk_band(detail.get("cancellation_rate"))
            else:
                selected_row = airport_display.loc[airport_display["airport_code"] == selected_airport]
                severity_label = selected_row["severity_band"].iloc[0] if not selected_row.empty else "Lower risk"
            render_detail_table(
                "Airport map details",
                {
                    "airport_code": detail.get("airport_code"),
                    "airport_name": detail.get("airport_name"),
                    "city": detail.get("city"),
                    "region_name": detail.get("region_name"),
                    "country_name": detail.get("country_name"),
                    "total_departures": format_int(detail.get("total_departures")),
                    "total_arrivals": format_int(detail.get("total_arrivals")),
                    "avg_departure_delay": format_minutes(detail.get("avg_departure_delay")),
                    "avg_arrival_delay": format_minutes(detail.get("avg_arrival_delay")),
                    "severity_band": severity_label,
                    "cancellation_rate": format_percent(detail.get("cancellation_rate")),
                    "runway_count": format_int(detail.get("runway_count")),
                },
            )
            render_insight(
                f"{selected_airport} is reachable from the map and from the keyboard selector, so airport details are not locked behind pointer interaction."
            )

    tab_airports, tab_routes = st.tabs(["Airport Data", "Route Data"])
    with tab_airports:
        st.dataframe(airport_display, use_container_width=True, hide_index=True)
    with tab_routes:
        st.dataframe(route_display, use_container_width=True, hide_index=True)


def render_flights_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Flight Table Explorer",
        "Inspect actual BTS rows with server-side filtering, sorting, search, export, and a details-on-demand drawer.",
    )
    render_filter_summary(filters)

    search_term = st.text_input("Search airport, airline, route, or flight number", placeholder="JFK, DL, JFK -> LAX, 421...")
    control_row_one = st.columns(2)
    sort_by = control_row_one[0].selectbox("Sort by", ["FlightDate", "airline", "Origin", "Dest", "DepDelay", "ArrDelay", "Distance"])
    sort_column_map = {"airline": "IATA_CODE_Reporting_Airline"}.get(sort_by, sort_by)
    sort_direction = control_row_one[1].selectbox("Direction", ["DESC", "ASC"])
    control_row_two = st.columns(2)
    page_size = control_row_two[0].selectbox("Rows per page", [50, 100, 250], index=1)
    page_number = control_row_two[1].number_input("Page", min_value=1, value=1, step=1)

    rows, total_rows = repo.get_flights_page(
        filters,
        page=int(page_number),
        page_size=int(page_size),
        search_term=search_term,
        sort_by=sort_column_map,
        sort_direction=sort_direction,
    )

    st.caption(f"Filtered rows available: {format_int(total_rows)}")
    if not rows.empty:
        st.download_button(
            "Export Filtered Rows as CSV",
            data=df_to_csv_bytes(rows),
            file_name="filtered_flights.csv",
            use_container_width=True,
        )
        selected_row_id = _render_aggrid(rows)
        render_data_toggle("View current page as table", rows)
        if selected_row_id is not None:
            detail = repo.get_flight_detail(int(selected_row_id))
            render_insight(f"Flight {detail.get('Flight_Number_Reporting_Airline')} on {detail.get('route')} is open in the details panel below.")
            render_detail_table(
                "Flight details",
                {
                    "flight_date": detail.get("FlightDate"),
                    "airline": detail.get("airline"),
                    "flight_number": detail.get("Flight_Number_Reporting_Airline"),
                    "route": detail.get("route"),
                    "origin_airport": f"{detail.get('Origin')} - {detail.get('origin_airport_name')}",
                    "destination_airport": f"{detail.get('Dest')} - {detail.get('dest_airport_name')}",
                    "scheduled_departure": detail.get("crs_dep_time_label"),
                    "actual_departure": detail.get("dep_time_label"),
                    "departure_delay": format_minutes(detail.get("DepDelay")),
                    "scheduled_arrival": detail.get("crs_arr_time_label"),
                    "actual_arrival": detail.get("arr_time_label"),
                    "arrival_delay": format_minutes(detail.get("ArrDelay")),
                    "cancelled": "Yes" if detail.get("is_cancelled") else "No",
                    "cancellation_reason": cancellation_reason_label(detail.get("CancellationCode")),
                    "diverted": "Yes" if detail.get("is_diverted") else "No",
                    "distance_miles": format_int(detail.get("Distance")),
                    "carrier_delay": format_minutes(detail.get("CarrierDelay")),
                    "weather_delay": format_minutes(detail.get("WeatherDelay")),
                    "nas_delay": format_minutes(detail.get("NASDelay")),
                    "security_delay": format_minutes(detail.get("SecurityDelay")),
                    "late_aircraft_delay": format_minutes(detail.get("LateAircraftDelay")),
                },
            )
    else:
        st.info("No rows match the current filters. Try widening the date range or relaxing the delay threshold.")


def render_comparison_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Comparison Mode",
        "Mirror two entities against the same KPI set so trade-offs become obvious in one glance.",
    )
    render_filter_summary(filters)

    entity_type = st.selectbox("Comparison type", ["Airline", "Airport", "Route", "Month", "Weekday"])
    options = repo.get_entity_options(entity_type)
    if len(options) < 2:
        st.info("Not enough entities are available to compare for the current selection.")
        return
    left_value = st.selectbox("Left entity", options, key=f"{entity_type}_left")
    right_value = st.selectbox("Right entity", [opt for opt in options if opt != left_value], key=f"{entity_type}_right")
    comparison = repo.get_comparison_metrics(filters, entity_type, left_value, right_value)

    if comparison.empty:
        st.info("No comparison rows are available for the current filters.")
        return

    render_kpis(
        [
            {"label": comparison.iloc[0]["entity"], "value": format_minutes(comparison.iloc[0]["avg_delay"]), "caption": f"Delay rate {format_percent(comparison.iloc[0]['delay_rate'])}"},
            {"label": comparison.iloc[1]["entity"], "value": format_minutes(comparison.iloc[1]["avg_delay"]), "caption": f"Delay rate {format_percent(comparison.iloc[1]['delay_rate'])}"},
        ]
    )
    render_insight(
        f"{comparison.sort_values('avg_delay', ascending=False).iloc[0]['entity']} shows the weaker delay performance in this side-by-side comparison."
    )

    numeric = comparison.melt(
        id_vars=["entity"],
        value_vars=["avg_delay", "delay_rate", "cancellation_rate", "on_time_percentage", "severe_delay_rate"],
        var_name="metric",
        value_name="value",
    )
    fig = px.bar(
        numeric,
        x="metric",
        y="value",
        color="entity",
        pattern_shape="entity",
        pattern_shape_sequence=["/", "\\"],
        barmode="group",
        title="Side-by-Side KPI Comparison",
    )
    _plot(
        apply_figure_style(fig),
        "comparison_kpis",
        summary="Each compared entity uses both color and pattern, so the grouped KPI comparison remains readable without relying on hue alone.",
        data=comparison,
    )
    st.dataframe(comparison, use_container_width=True, hide_index=True)


def render_data_quality_page(repo: FlightDelayRepository, filters: GlobalFilterState) -> None:
    render_page_intro(
        "Data Quality",
        "Expose what was loaded, what was matched, and whether the dataset satisfies the big-data requirement before any analytic claim is trusted.",
    )
    render_filter_summary(filters)
    quality = repo.get_data_quality(filters)
    overall = quality["overall"]
    filtered = quality["filtered"]

    render_kpis(
        [
            {"label": "Loaded Rows", "value": format_int(overall["total_loaded_rows"]), "caption": "All Q1 2024 flights combined"},
            {"label": "Requirement", "value": "> 10,000", "caption": "Assignment minimum"},
            {"label": "Status", "value": "Passed" if overall["total_loaded_rows"] > 10000 else "Failed", "caption": "Big-data threshold check"},
            {"label": "Filtered Rows", "value": format_int(filtered["filtered_rows"]), "caption": "Rows after current filters"},
        ]
    )
    render_insight(
        f"The combined dataset currently reports {format_int(overall['total_loaded_rows'])} rows across {format_int(overall['number_of_source_files'])} source files."
    )

    _plot(
        bar_chart(quality["rows_by_file"], "source_file", "rows_loaded", "Rows by Source File"),
        "quality_rows_by_file",
        summary="Source-file row counts verify that all three monthly archives were loaded into the combined dataset.",
        data=quality["rows_by_file"],
    )
    _plot(
        bar_chart(quality["missing_summary"], "column_name", "missing_rows", "Missing Values by Column"),
        "quality_missing",
        summary="Missing-value counts are shown directly by field, and the fallback table keeps the exact totals accessible.",
        data=quality["missing_summary"],
    )

    if not quality["delay_distribution"].empty:
        _plot(
            histogram_chart(quality["delay_distribution"], "ArrDelay", "Delay Value Distribution"),
            "quality_delay_dist",
            summary="The delay distribution highlights outliers and missingness patterns while preserving a sampled value table for auditability.",
            data=quality["delay_distribution"].head(200),
            table_label="View delay quality sample",
        )

    render_detail_table(
        "Overall quality summary",
        {
            "total_loaded_rows": format_int(overall["total_loaded_rows"]),
            "number_of_source_files": format_int(overall["number_of_source_files"]),
            "min_flight_date": overall["min_flight_date"],
            "max_flight_date": overall["max_flight_date"],
            "number_of_airlines": format_int(overall["number_of_airlines"]),
            "number_of_origin_airports": format_int(overall["number_of_origin_airports"]),
            "number_of_destination_airports": format_int(overall["number_of_destination_airports"]),
            "origin_airport_misses": format_int(overall["flights_without_origin_airport_match"]),
            "destination_airport_misses": format_int(overall["flights_without_destination_airport_match"]),
        },
    )
    render_detail_table(
        "Filtered quality summary",
        {
            "filtered_rows": format_int(filtered["filtered_rows"]),
            "filtered_origin_misses": format_int(filtered["filtered_origin_misses"]),
            "filtered_destination_misses": format_int(filtered["filtered_dest_misses"]),
        },
    )


def _plot(
    fig,
    filename: str,
    summary: str | None = None,
    data: pd.DataFrame | None = None,
    table_label: str = "View chart data",
) -> None:
    st.plotly_chart(fig, use_container_width=True, config=figure_download_config(filename))
    if summary:
        render_chart_summary(summary)
    if data is not None and not data.empty:
        render_data_toggle(table_label, data)


def _render_aggrid(frame: pd.DataFrame) -> int | None:
    builder = GridOptionsBuilder.from_dataframe(frame)
    builder.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=min(len(frame), 12))
    builder.configure_side_bar()
    builder.configure_selection("single", use_checkbox=True)
    builder.configure_default_column(groupable=True, value=True, enableRowGroup=True, editable=False)
    options = builder.build()
    grid_response = AgGrid(
        frame,
        gridOptions=options,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        height=min(520, 120 + math.ceil(len(frame) * 28)),
        update_mode="SELECTION_CHANGED",
        fit_columns_on_grid_load=False,
        enable_enterprise_modules=False,
        allow_unsafe_jscode=False,
    )
    selected = grid_response.get("selected_rows", [])
    if not selected:
        return None
    if isinstance(selected[0], dict):
        return selected[0].get("flight_row_id")
    return None


def _delay_band(value: object) -> str:
    value = 0.0 if value is None or pd.isna(value) else float(value)
    if value >= 25:
        return "Severe delay"
    if value >= 12:
        return "High delay"
    if value >= 5:
        return "Moderate delay"
    return "Lower delay"


def _risk_band(value: object) -> str:
    value = 0.0 if value is None or pd.isna(value) else float(value)
    if value >= 0.12:
        return "Severe risk"
    if value >= 0.06:
        return "High risk"
    if value >= 0.03:
        return "Moderate risk"
    return "Lower risk"
