from __future__ import annotations

import html
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from flight_delay_explorer.config import (
    APP_TITLE,
    COLOR_TOKENS,
    DISTANCE_GROUP_ORDER,
    MONTH_NAMES,
    TIME_OF_DAY_ORDER,
    WEEKDAY_NAMES,
)
from flight_delay_explorer.data import ensure_processed_data
from flight_delay_explorer.models import GlobalFilterState
from flight_delay_explorer.repository import FlightDelayRepository
from flight_delay_explorer.utils import format_int


def configure_page(page_title: str, page_icon: str = "✈️") -> None:
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()


@st.cache_resource(show_spinner=False)
def prepare_repository() -> FlightDelayRepository:
    ensure_processed_data()
    return FlightDelayRepository()


def apply_theme() -> None:
    st.html(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Manrope:wght@400;500;600;700&display=swap');

            :root {{
                --fde-bg: {COLOR_TOKENS["background"]};
                --fde-surface: {COLOR_TOKENS["surface"]};
                --fde-surface-alt: {COLOR_TOKENS["surface_alt"]};
                --fde-navy: {COLOR_TOKENS["navy"]};
                --fde-slate: {COLOR_TOKENS["slate"]};
                --fde-teal: {COLOR_TOKENS["teal"]};
                --fde-amber: {COLOR_TOKENS["amber"]};
                --fde-coral: {COLOR_TOKENS["coral"]};
                --fde-sage: {COLOR_TOKENS["sage"]};
                --fde-line: {COLOR_TOKENS["line"]};
                --fde-muted: {COLOR_TOKENS["muted"]};
            }}

            .stApp {{
                background:
                    radial-gradient(circle at top left, rgba(47,124,132,0.09), transparent 32%),
                    radial-gradient(circle at top right, rgba(213,139,61,0.08), transparent 24%),
                    linear-gradient(180deg, #fcfaf5 0%, var(--fde-bg) 100%);
                color: var(--fde-slate);
                font-family: "Manrope", sans-serif;
            }}

            .block-container {{
                padding-top: 1.6rem;
                padding-bottom: 3rem;
            }}

            .fde-hero {{
                background: linear-gradient(135deg, rgba(24,50,74,0.97), rgba(24,50,74,0.86));
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 24px;
                padding: 1.7rem 1.8rem;
                color: #f7f3ea;
                box-shadow: 0 24px 80px rgba(24, 50, 74, 0.22);
                overflow: hidden;
                position: relative;
                margin-bottom: 1.2rem;
            }}

            .fde-hero::after {{
                content: "";
                position: absolute;
                inset: auto -4rem -4rem auto;
                width: 18rem;
                height: 18rem;
                border-radius: 50%;
                background: radial-gradient(circle, rgba(163,200,203,0.24), transparent 70%);
            }}

            .fde-kicker {{
                text-transform: uppercase;
                letter-spacing: 0.18em;
                font-size: 0.74rem;
                color: rgba(247,243,234,0.78);
                margin-bottom: 0.7rem;
            }}

            .fde-title {{
                font-family: "Cormorant Garamond", serif;
                font-size: 3rem;
                line-height: 0.95;
                margin: 0 0 0.45rem 0;
                font-weight: 700;
            }}

            .fde-lead {{
                max-width: 48rem;
                color: rgba(247,243,234,0.86);
                font-size: 1rem;
                line-height: 1.55;
                margin: 0;
            }}

            .fde-panel {{
                background: rgba(251, 248, 241, 0.88);
                border: 1px solid rgba(64,83,99,0.1);
                border-radius: 22px;
                padding: 1.15rem 1.2rem;
                box-shadow: 0 12px 36px rgba(24, 50, 74, 0.08);
                margin-bottom: 1rem;
            }}

            .fde-panel h3 {{
                margin: 0 0 0.25rem 0;
                color: var(--fde-navy);
                font-size: 1rem;
            }}

            .fde-panel p {{
                margin: 0;
                color: var(--fde-muted);
                font-size: 0.92rem;
                line-height: 1.5;
            }}

            .fde-kpi-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 0.8rem;
                margin: 0.5rem 0 1.2rem 0;
            }}

            .fde-kpi {{
                background: rgba(251,248,241,0.92);
                border: 1px solid rgba(64,83,99,0.12);
                border-radius: 20px;
                padding: 1rem 1rem 0.95rem 1rem;
                box-shadow: 0 10px 28px rgba(24,50,74,0.07);
                min-height: 118px;
            }}

            .fde-kpi-label {{
                color: var(--fde-slate);
                font-size: 0.82rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 700;
            }}

            .fde-kpi-value {{
                color: var(--fde-navy);
                font-size: 2rem;
                font-weight: 700;
                line-height: 1.05;
                margin: 0.55rem 0 0.3rem 0;
            }}

            .fde-kpi-caption {{
                color: var(--fde-slate);
                font-size: 0.9rem;
                line-height: 1.45;
            }}

            .fde-section-title {{
                font-family: "Cormorant Garamond", serif;
                color: var(--fde-navy);
                font-size: 2rem;
                margin: 0 0 0.15rem 0;
            }}

            .fde-section-text {{
                margin: 0 0 1rem 0;
                color: var(--fde-muted);
                font-size: 0.95rem;
            }}

            .fde-insight {{
                background: linear-gradient(135deg, rgba(47,124,132,0.12), rgba(213,139,61,0.09));
                border: 1px solid rgba(47,124,132,0.18);
                border-radius: 18px;
                padding: 0.95rem 1rem;
                margin-bottom: 0.8rem;
            }}

            .fde-insight strong {{
                color: var(--fde-navy);
            }}

            .fde-summary {{
                padding: 0.8rem 1rem;
                border-radius: 16px;
                background: rgba(163,200,203,0.14);
                border: 1px solid rgba(47,124,132,0.18);
                color: var(--fde-navy);
                margin-bottom: 1rem;
            }}

            .stTabs [data-baseweb="tab-list"] {{
                gap: 0.6rem;
            }}

            .stTabs [data-baseweb="tab"] {{
                height: 2.5rem;
                border-radius: 999px;
                background: rgba(251,248,241,0.9);
                border: 1px solid rgba(64,83,99,0.12);
                padding-inline: 1rem;
            }}

            div[data-testid="stMetric"] {{
                background: rgba(251,248,241,0.86);
                border: 1px solid rgba(64,83,99,0.10);
                border-radius: 18px;
                padding: 0.8rem 0.9rem;
            }}

            @media (max-width: 900px) {{
                .block-container {{
                    padding-top: 1rem;
                    padding-bottom: 1.6rem;
                }}

                .fde-hero {{
                    padding: 1.2rem 1rem;
                    border-radius: 20px;
                }}

                .fde-title {{
                    font-size: 2.2rem;
                }}

                .fde-lead {{
                    font-size: 0.95rem;
                }}

                .fde-section-title {{
                    font-size: 1.6rem;
                }}

                .fde-kpi-grid {{
                    grid-template-columns: 1fr;
                    gap: 0.65rem;
                }}
            }}
        </style>
        """,
    )


def render_hero(title: str, subtitle: str, kicker: str = "Flight Analytics Control Deck") -> None:
    st.html(
        f"""
        <section class="fde-hero">
            <div class="fde-kicker">{html.escape(kicker)}</div>
            <h1 class="fde-title">{html.escape(title)}</h1>
            <p class="fde-lead">{html.escape(subtitle)}</p>
        </section>
        """,
    )


def render_section_header(title: str, text: str) -> None:
    st.html(
        f"""
        <h2 class="fde-section-title">{html.escape(title)}</h2>
        <p class="fde-section-text">{html.escape(text)}</p>
        """,
    )


def render_filter_summary(filters: GlobalFilterState) -> None:
    st.info(filters.active_label())


def render_kpis(cards: list[dict[str, str]]) -> None:
    body = "".join(
        f"""
        <div class="fde-kpi">
            <div class="fde-kpi-label">{html.escape(str(card["label"]))}</div>
            <div class="fde-kpi-value">{html.escape(str(card["value"]))}</div>
            <div class="fde-kpi-caption">{html.escape(str(card["caption"]))}</div>
        </div>
        """
        for card in cards
    )
    st.html(f'<div class="fde-kpi-grid">{body}</div>')


def render_insight(text: str) -> None:
    st.info(text)


def render_page_intro(title: str, description: str) -> None:
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.write(description)


def render_info_panel(title: str, description: str) -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(description)


def render_chart_summary(summary: str) -> None:
    st.caption(f"How to read: {summary}")


def render_detail_table(title: str, detail: dict[str, Any], order: list[str] | None = None) -> None:
    if not detail:
        st.info(f"No {title.lower()} details are available for the current selection.")
        return
    rows: list[dict[str, str]] = []
    keys = order if order is not None else list(detail.keys())
    for key in keys:
        if key not in detail:
            continue
        value = detail[key]
        if value is None or value == "":
            value = "N/A"
        rows.append({"Field": key.replace("_", " ").title(), "Value": str(value)})
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_data_toggle(label: str, frame: pd.DataFrame) -> None:
    with st.expander(label):
        st.dataframe(frame, use_container_width=True, hide_index=True)


def render_sidebar_filters(repo: FlightDelayRepository) -> GlobalFilterState:
    options = repo.get_filter_options()
    st.sidebar.markdown(f"## {APP_TITLE}")
    st.sidebar.caption("Overview first. Zoom and filter. Details on demand.")

    if st.sidebar.button("Reset filters", use_container_width=True):
        for key in [
            "fde_start_date",
            "fde_end_date",
            "fde_month",
            "fde_weekday",
            "fde_airline",
            "fde_origin",
            "fde_dest",
            "fde_route",
            "fde_delay_threshold",
            "fde_cancelled",
            "fde_diverted",
            "fde_distance_group",
            "fde_time_of_day_group",
        ]:
            st.session_state.pop(key, None)
        st.rerun()

    start_default = _to_date(options["start_date"])
    end_default = _to_date(options["end_date"])

    start_date = st.sidebar.date_input("Start date", value=st.session_state.get("fde_start_date", start_default), key="fde_start_date")
    end_date = st.sidebar.date_input("End date", value=st.session_state.get("fde_end_date", end_default), key="fde_end_date")
    ordered_months = [name for _, name in MONTH_NAMES.items() if name in (options["months"] or [])]
    ordered_weekdays = [name for _, name in WEEKDAY_NAMES.items() if name in (options["weekdays"] or [])]

    month = st.sidebar.multiselect("Month", ordered_months, key="fde_month")
    weekday = st.sidebar.multiselect("Weekday", ordered_weekdays, key="fde_weekday")
    airline = st.sidebar.multiselect("Airline", options["airlines"] or [], key="fde_airline")
    origin = st.sidebar.multiselect("Origin airport", options["origins"] or [], key="fde_origin")
    dest = st.sidebar.multiselect("Destination airport", options["destinations"] or [], key="fde_dest")
    route = st.sidebar.multiselect("Route", options["routes"] or [], key="fde_route")
    delay_threshold = st.sidebar.slider("Delay threshold (minutes)", min_value=0, max_value=180, step=15, key="fde_delay_threshold")
    cancelled = st.sidebar.selectbox("Cancellation status", ["All", "Yes", "No"], key="fde_cancelled")
    diverted = st.sidebar.selectbox("Diversion status", ["All", "Yes", "No"], key="fde_diverted")
    distance_group = st.sidebar.multiselect(
        "Distance group",
        [group for group in DISTANCE_GROUP_ORDER if group in (options["distance_groups"] or [])],
        key="fde_distance_group",
    )
    time_of_day_group = st.sidebar.multiselect(
        "Departure time group",
        [group for group in TIME_OF_DAY_ORDER if group in (options["time_of_day_groups"] or [])],
        key="fde_time_of_day_group",
    )

    st.sidebar.metric("Rows available", format_int(repo.get_dataset_overview()["total_loaded_rows"]))

    return GlobalFilterState(
        start_date=_to_date(start_date),
        end_date=_to_date(end_date),
        month=list(month),
        weekday=list(weekday),
        airline=list(airline),
        origin=list(origin),
        dest=list(dest),
        route=list(route),
        delay_threshold=int(delay_threshold),
        cancelled=cancelled,
        diverted=diverted,
        distance_group=list(distance_group),
        time_of_day_group=list(time_of_day_group),
    )


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    return None
