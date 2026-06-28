from __future__ import annotations

import math

import pandas as pd
import pydeck as pdk

from flight_delay_explorer.config import COLOR_TOKENS


def build_airport_map(frame: pd.DataFrame, mode: str = "traffic") -> pdk.Deck:
    if frame.empty:
        return _empty_map()

    data = frame.copy()
    data["radius"] = data["total_departures"].fillna(1).pow(0.58) * 250
    if mode == "delay":
        data["severity_band"] = data["avg_departure_delay"].fillna(0).map(_delay_band)
        data["fill_color"] = data["avg_departure_delay"].fillna(0).map(_delay_color)
        data["line_width"] = data["severity_band"].map(_band_line_width)
    elif mode == "cancellation":
        data["severity_band"] = data["cancellation_rate"].fillna(0).map(_ratio_band)
        data["fill_color"] = data["cancellation_rate"].fillna(0).map(lambda value: _ratio_color(value, accent="coral"))
        data["line_width"] = data["severity_band"].map(_band_line_width)
    else:
        data["severity_band"] = data["delay_rate"].fillna(0).map(_ratio_band)
        data["fill_color"] = data["delay_rate"].fillna(0).map(lambda value: _ratio_color(value, accent="teal"))
        data["line_width"] = data["severity_band"].map(_band_line_width)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="[longitude, latitude]",
        get_radius="radius",
        get_fill_color="fill_color",
        pickable=True,
        opacity=0.72,
        stroked=True,
        get_line_color=[24, 50, 74, 160],
        get_line_width="line_width",
        line_width_min_pixels=1,
    )
    tooltip = {
        "html": """
            <div style="font-family: Manrope, sans-serif;">
                <b>{airport_code} - {airport_name}</b><br/>
                City: {city}<br/>
                Departures: {total_departures}<br/>
                Avg dep delay: {avg_departure_delay} min<br/>
                Delay rate: {delay_rate}<br/>
                Cancellation rate: {cancellation_rate}<br/>
                Severity band: {severity_band}<br/>
                Runways: {runway_count}<br/>
                Top destination: {top_destination}
            </div>
        """
    }
    return pdk.Deck(
        layers=[layer],
        tooltip=tooltip,
        initial_view_state=_default_view_state(),
        map_style="light",
    )


def build_route_map(frame: pd.DataFrame) -> pdk.Deck:
    if frame.empty:
        return _empty_map()
    data = frame.copy()
    data["delay_band"] = data["avg_arrival_delay"].fillna(0).map(_delay_band)
    data["width"] = data["total_flights"].fillna(1).pow(0.48) / 11
    data["source_color"] = data["avg_arrival_delay"].fillna(0).map(_delay_color)
    arc_layer = pdk.Layer(
        "ArcLayer",
        data=data,
        get_source_position="[origin_longitude, origin_latitude]",
        get_target_position="[dest_longitude, dest_latitude]",
        get_width="width",
        get_source_color="source_color",
        get_target_color=[24, 50, 74, 80],
        pickable=True,
        auto_highlight=True,
    )
    airport_layer = pdk.Layer(
        "ScatterplotLayer",
        data=_airport_nodes_from_routes(data),
        get_position="[longitude, latitude]",
        get_radius="radius",
        get_fill_color=[24, 50, 74, 170],
        pickable=False,
        opacity=0.5,
    )
    tooltip = {
        "html": """
            <div style="font-family: Manrope, sans-serif;">
                <b>{route}</b><br/>
                Flights: {total_flights}<br/>
                Avg arr delay: {avg_arrival_delay} min<br/>
                Delay band: {delay_band}<br/>
                Delay rate: {delay_rate}<br/>
                Cancellation rate: {cancellation_rate}<br/>
                Most common airline: {most_common_airline}
            </div>
        """
    }
    return pdk.Deck(
        layers=[arc_layer, airport_layer],
        tooltip=tooltip,
        initial_view_state=_default_view_state(),
        map_style="light",
    )


def _airport_nodes_from_routes(frame: pd.DataFrame) -> pd.DataFrame:
    origin_nodes = frame[["Origin", "origin_latitude", "origin_longitude", "total_flights"]].rename(
        columns={"Origin": "airport_code", "origin_latitude": "latitude", "origin_longitude": "longitude"}
    )
    dest_nodes = frame[["Dest", "dest_latitude", "dest_longitude", "total_flights"]].rename(
        columns={"Dest": "airport_code", "dest_latitude": "latitude", "dest_longitude": "longitude"}
    )
    nodes = pd.concat([origin_nodes, dest_nodes], ignore_index=True)
    nodes = nodes.groupby(["airport_code", "latitude", "longitude"], as_index=False)["total_flights"].sum()
    nodes["radius"] = nodes["total_flights"].fillna(1).pow(0.45) * 110
    return nodes


def _delay_color(value: float) -> list[int]:
    value = 0 if pd.isna(value) else float(value)
    if value >= 25:
        return [207, 106, 93, 220]
    if value >= 12:
        return [213, 139, 61, 205]
    if value >= 5:
        return [47, 124, 132, 195]
    return [111, 139, 110, 185]


def _ratio_color(value: float, accent: str = "teal") -> list[int]:
    value = 0 if pd.isna(value) else max(0.0, min(float(value), 1.0))
    if accent == "coral":
        base = (207, 106, 93)
    else:
        base = (47, 124, 132)
    alpha = 120 + math.floor(value * 120)
    return [base[0], base[1], base[2], alpha]


def _delay_band(value: float) -> str:
    value = 0 if pd.isna(value) else float(value)
    if value >= 25:
        return "Severe delay"
    if value >= 12:
        return "High delay"
    if value >= 5:
        return "Moderate delay"
    return "Lower delay"


def _ratio_band(value: float) -> str:
    value = 0 if pd.isna(value) else float(value)
    if value >= 0.12:
        return "Severe risk"
    if value >= 0.06:
        return "High risk"
    if value >= 0.03:
        return "Moderate risk"
    return "Lower risk"


def _band_line_width(band: str) -> int:
    return {
        "Severe delay": 6,
        "Severe risk": 6,
        "High delay": 4,
        "High risk": 4,
        "Moderate delay": 3,
        "Moderate risk": 3,
        "Lower delay": 2,
        "Lower risk": 2,
    }.get(band, 2)


def _default_view_state() -> pdk.ViewState:
    return pdk.ViewState(latitude=38.5, longitude=-96.0, zoom=3.3, pitch=30, bearing=0)


def _empty_map() -> pdk.Deck:
    return pdk.Deck(
        layers=[],
        initial_view_state=_default_view_state(),
        map_style="light",
    )
