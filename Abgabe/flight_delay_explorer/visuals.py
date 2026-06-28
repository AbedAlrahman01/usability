from __future__ import annotations

from typing import Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from flight_delay_explorer.config import COLOR_TOKENS


PALETTE = [
    COLOR_TOKENS["navy"],
    COLOR_TOKENS["teal"],
    COLOR_TOKENS["amber"],
    COLOR_TOKENS["coral"],
    COLOR_TOKENS["sage"],
    COLOR_TOKENS["muted"],
]


def apply_figure_style(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=24, r=24, t=96, b=24),
        font=dict(family="Manrope, sans-serif", color=COLOR_TOKENS["slate"]),
        title=dict(
            x=0.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            pad=dict(b=20),
        ),
        title_font=dict(family="Cormorant Garamond, serif", color=COLOR_TOKENS["navy"], size=24),
        colorway=PALETTE,
        legend=dict(
            title=dict(text="Legend"),
            orientation="h",
            yanchor="bottom",
            y=1.0,
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
            itemclick="toggleothers",
        ),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=COLOR_TOKENS["line"], automargin=True, tickangle=-18),
        yaxis=dict(showgrid=True, gridcolor="rgba(64,83,99,0.08)", zeroline=False, automargin=True),
        bargap=0.18,
        hoverlabel=dict(bgcolor="#18324a", font_color="#f7f3ea"),
    )
    return fig


def bar_chart(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color: str | None = None,
    orientation: str = "v",
    text_auto: str | bool = False,
) -> go.Figure:
    fig = px.bar(
        frame,
        x=x if orientation == "v" else y,
        y=y if orientation == "v" else x,
        color=color,
        orientation=orientation,
        title=title,
        color_discrete_sequence=PALETTE,
        text_auto=text_auto,
    )
    return apply_figure_style(fig)


def line_chart(frame: pd.DataFrame, x: str, y: Sequence[str] | str, title: str) -> go.Figure:
    fig = px.line(frame, x=x, y=y, title=title, markers=True, color_discrete_sequence=PALETTE)
    if isinstance(y, (list, tuple)) and len(y) > 1:
        dash_sequence = ["solid", "dot", "dash", "longdash", "dashdot"]
        for index, trace in enumerate(fig.data):
            trace.update(line=dict(width=3, dash=dash_sequence[index % len(dash_sequence)]))
    else:
        fig.update_traces(line=dict(width=3))
    return apply_figure_style(fig)


def donut_chart(frame: pd.DataFrame, names: str, values: str, title: str) -> go.Figure:
    fig = px.pie(
        frame,
        names=names,
        values=values,
        title=title,
        hole=0.58,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return apply_figure_style(fig)


def histogram_chart(frame: pd.DataFrame, x: str, title: str, nbins: int = 36) -> go.Figure:
    fig = px.histogram(frame, x=x, title=title, nbins=nbins, color_discrete_sequence=[COLOR_TOKENS["teal"]])
    return apply_figure_style(fig)


def heatmap_chart(frame: pd.DataFrame, x: str, y: str, z: str, title: str) -> go.Figure:
    fig = px.density_heatmap(
        frame,
        x=x,
        y=y,
        z=z,
        histfunc="avg",
        color_continuous_scale=[
            [0.0, "#e9f0f2"],
            [0.35, "#a3c8cb"],
            [0.7, "#d58b3d"],
            [1.0, "#cf6a5d"],
        ],
        title=title,
    )
    fig.update_layout(coloraxis_colorbar_title=z.replace("_", " ").title())
    return apply_figure_style(fig)


def stacked_area_chart(frame: pd.DataFrame, x: str, y: Sequence[str], title: str) -> go.Figure:
    long_frame = frame.melt(id_vars=[x], value_vars=list(y), var_name="series", value_name="value")
    fig = px.area(long_frame, x=x, y="value", color="series", title=title, color_discrete_sequence=PALETTE)
    dash_sequence = ["solid", "dot", "dash", "longdash", "dashdot"]
    for index, trace in enumerate(fig.data):
        trace.update(line=dict(width=2, dash=dash_sequence[index % len(dash_sequence)]))
    return apply_figure_style(fig)


def stacked_bar_chart(frame: pd.DataFrame, x: str, y: Sequence[str], title: str) -> go.Figure:
    long_frame = frame.melt(id_vars=[x], value_vars=list(y), var_name="series", value_name="value")
    fig = px.bar(
        long_frame,
        x=x,
        y="value",
        color="series",
        pattern_shape="series",
        title=title,
        color_discrete_sequence=PALETTE,
        pattern_shape_sequence=["", "/", "\\", "x", "."],
    )
    return apply_figure_style(fig)
