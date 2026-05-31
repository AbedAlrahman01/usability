from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "usability_survey_streamlit_dataset.csv"
DICTIONARY_PATH = BASE_DIR / "usability_survey_data_dictionary.csv"

PROTOTYPE_ORDER = ["Prototype A", "Prototype B"]
TASK_ORDER = ["T1", "T2", "T3", "T4"]
SENTIMENT_ORDER = ["Positive", "Neutral", "Negative"]

COLORS = {
    "Prototype A": "#334155",
    "Prototype B": "#0F766E",
    "Positive": "#0F766E",
    "Neutral": "#64748B",
    "Negative": "#B45309",
    "Accent": "#0F766E",
    "Alert": "#B45309",
    "Muted": "#CBD5E1",
    "Grid": "#D8E0E7",
    "Text": "#1F2937",
}

FILTER_LABELS = {
    "prototype_version": "Prototype",
    "task_id": "Task",
    "device": "Device",
    "data_literacy": "Data literacy",
    "role": "Role",
    "comment_sentiment": "Comment sentiment",
}

RATING_LABELS = {
    "ease_of_use_1_5": "Ease of use",
    "visual_clarity_1_5": "Visual clarity",
    "filter_usability_1_5": "Filter usability",
    "confidence_in_answer_1_5": "Confidence",
    "satisfaction_1_5": "Satisfaction",
    "accessibility_rating_1_5": "Accessibility",
}

SEGMENT_OPTIONS = {
    "Device": "device",
    "Data literacy": "data_literacy",
    "Role": "role",
}

METRIC_OPTIONS = {
    "Usability score": "usability_score_0_100",
    "Task success": "task_success",
    "Completion time": "completion_time_sec",
    "Accessibility rating": "accessibility_rating_1_5",
}

METRIC_FORMATTERS = {
    "Usability score": lambda value: f"{value:.1f}",
    "Task success": lambda value: f"{value:.0%}",
    "Completion time": lambda value: f"{value:.0f} sec",
    "Accessibility rating": lambda value: f"{value:.2f}",
}


st.set_page_config(
    page_title="Usability Study Results",
    page_icon="bar_chart",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Serif:wght@500;600&display=swap');

        :root {
            --bg: #F5F2EA;
            --surface: #FFFFFF;
            --surface-soft: rgba(255, 255, 255, 0.72);
            --stroke: #D8E0E7;
            --text: #1F2937;
            --muted: #5B6776;
            --accent: #0F766E;
            --alert: #B45309;
        }

        html, body, [class*="css"] {
            font-family: 'Source Sans 3', sans-serif;
            color: var(--text);
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.08), transparent 26%),
                linear-gradient(180deg, #F1EBDD 0%, #F5F2EA 28%, #FAF8F4 100%);
        }

        [data-testid="stSidebar"] {
            background: #F6F1E7;
            border-right: 1px solid rgba(31, 41, 55, 0.08);
        }

        .block-container {
            max-width: 1320px;
            padding-top: 2.1rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3 {
            font-family: 'IBM Plex Serif', serif;
            letter-spacing: -0.02em;
        }

        h1 {
            margin-bottom: 0.3rem;
        }

        .eyebrow {
            color: var(--accent);
            font-size: 0.84rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .intro-copy {
            max-width: 66rem;
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.55;
            margin-bottom: 1.15rem;
        }

        .context-grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            margin-bottom: 1.2rem;
        }

        .context-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(31, 41, 55, 0.08);
            border-radius: 18px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
            padding: 1rem 1.05rem;
        }

        .context-card h3 {
            font-family: 'IBM Plex Serif', serif;
            font-size: 1.02rem;
            margin: 0 0 0.45rem 0;
        }

        .context-card p {
            color: var(--muted);
            line-height: 1.5;
            margin: 0;
        }

        .scope-banner {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin: 0.6rem 0 1.25rem 0;
        }

        .scope-pill {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(31, 41, 55, 0.1);
            border-radius: 999px;
            color: var(--text);
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            font-size: 0.92rem;
            line-height: 1.2;
            padding: 0.45rem 0.85rem;
        }

        .scope-pill strong {
            color: var(--accent);
        }

        div[data-testid="metric-container"] {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(31, 41, 55, 0.08);
            border-radius: 18px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
            padding: 0.9rem 1rem;
        }

        div[data-testid="metric-container"] label {
            color: var(--muted);
        }

        .section-lead {
            color: var(--muted);
            margin-top: -0.2rem;
            margin-bottom: 0.85rem;
            max-width: 64rem;
        }

        .insight-card {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(31, 41, 55, 0.08);
            border-left: 5px solid var(--accent);
            border-radius: 16px;
            margin-bottom: 0.7rem;
            padding: 0.9rem 1rem 0.95rem 1rem;
        }

        .insight-card h4 {
            font-size: 0.88rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin: 0 0 0.3rem 0;
            color: var(--accent);
        }

        .insight-card p {
            margin: 0;
            line-height: 1.45;
        }

        .quote-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(31, 41, 55, 0.08);
            border-radius: 16px;
            min-height: 170px;
            padding: 1rem;
        }

        .quote-card .quote-label {
            color: var(--muted);
            font-size: 0.84rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            margin-bottom: 0.45rem;
            text-transform: uppercase;
        }

        .quote-card blockquote {
            margin: 0;
            font-size: 1.02rem;
            line-height: 1.55;
            color: var(--text);
        }

        .method-note {
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid rgba(31, 41, 55, 0.08);
            border-radius: 16px;
            padding: 0.9rem 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(DATASET_PATH)
    data_dictionary = pd.read_csv(DICTIONARY_PATH)

    numeric_columns = [
        "task_success",
        "completion_time_sec",
        "clicks",
        "errors",
        "help_needed",
        "ease_of_use_1_5",
        "visual_clarity_1_5",
        "filter_usability_1_5",
        "confidence_in_answer_1_5",
        "satisfaction_1_5",
        "accessibility_rating_1_5",
        "avg_rating_1_5",
        "usability_score_0_100",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["prototype_version"] = pd.Categorical(
        data["prototype_version"], categories=PROTOTYPE_ORDER, ordered=True
    )
    data["task_id"] = pd.Categorical(data["task_id"], categories=TASK_ORDER, ordered=True)
    data["comment_sentiment"] = pd.Categorical(
        data["comment_sentiment"], categories=SENTIMENT_ORDER, ordered=True
    )
    data["task_label"] = data["task_id"].astype(str) + " • " + data["task_name"]

    return data, data_dictionary


def build_filter_options(data: pd.DataFrame) -> dict[str, list[str]]:
    return {
        "prototype_version": [value for value in PROTOTYPE_ORDER if value in data["prototype_version"].astype(str).unique()],
        "task_id": [value for value in TASK_ORDER if value in data["task_id"].astype(str).unique()],
        "device": sorted(data["device"].dropna().unique().tolist()),
        "data_literacy": sorted(data["data_literacy"].dropna().unique().tolist()),
        "role": sorted(data["role"].dropna().unique().tolist()),
        "comment_sentiment": [value for value in SENTIMENT_ORDER if value in data["comment_sentiment"].astype(str).unique()],
    }


def initialize_filter_state(options: dict[str, list[str]]) -> None:
    for column, values in options.items():
        state_key = f"filter_{column}"
        if state_key not in st.session_state:
            st.session_state[state_key] = values.copy()


def reset_filters(options: dict[str, list[str]]) -> None:
    for column, values in options.items():
        st.session_state[f"filter_{column}"] = values.copy()


def apply_filters(data: pd.DataFrame, options: dict[str, list[str]]) -> pd.DataFrame:
    filtered = data.copy()
    for column in options:
        selected = st.session_state.get(f"filter_{column}", [])
        if not selected:
            return filtered.iloc[0:0].copy()
        filtered = filtered[filtered[column].astype(str).isin(selected)]
    return filtered


def format_task_option(task_id: str, data: pd.DataFrame) -> str:
    task_name = (
        data.loc[data["task_id"].astype(str) == task_id, "task_name"].dropna().drop_duplicates().tolist()
    )
    if not task_name:
        return task_id
    return f"{task_id} - {task_name[0]}"


def active_filter_markup(data: pd.DataFrame, options: dict[str, list[str]]) -> str:
    pills = [
        f"<span class='scope-pill'><strong>{data['participant_id'].nunique():,}</strong> participants</span>",
        f"<span class='scope-pill'><strong>{len(data):,}</strong> task records</span>",
    ]

    for column, label in FILTER_LABELS.items():
        selected = st.session_state.get(f"filter_{column}", [])
        if len(selected) == len(options[column]):
            continue
        display_values = selected
        if column == "task_id":
            display_values = [format_task_option(task_id, data) for task_id in selected]
        joined_values = ", ".join(escape(value) for value in display_values) if display_values else "None"
        pills.append(
            f"<span class='scope-pill'><strong>{escape(label)}:</strong> {joined_values}</span>"
        )

    if len(pills) == 2:
        pills.append("<span class='scope-pill'><strong>Scope:</strong> Full study sample</span>")

    return "<div class='scope-banner'>" + "".join(pills) + "</div>"


def render_page_intro(full_data: pd.DataFrame, filtered_data: pd.DataFrame) -> None:
    participant_count = full_data["participant_id"].nunique()
    record_count = len(full_data)
    task_count = full_data["task_id"].nunique()
    is_filtered = len(filtered_data) != len(full_data)

    scope_text = (
        f"The current view is filtered to {filtered_data['participant_id'].nunique():,} participants and {len(filtered_data):,} task records."
        if is_filtered
        else "The current view shows the full study sample."
    )

    st.markdown("<div class='eyebrow'>Comparative Usability Study</div>", unsafe_allow_html=True)
    st.title("Usability Study Results: Prototype A vs Prototype B")
    st.markdown(
        "<p class='intro-copy'>This dashboard summarizes the results of a side-by-side usability test. It is built to answer one question clearly: did Prototype B improve task success, speed, and perceived usability compared with Prototype A, and where does friction still remain?</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='context-grid'>
            <div class='context-card'>
                <h3>What this dashboard covers</h3>
                <p>{escape(f'The study includes {participant_count:,} participants, {record_count:,} task records, and {task_count} core tasks. It combines behavioral outcomes such as task success, time, errors, and help needed with satisfaction ratings and participant comments.')}</p>
            </div>
            <div class='context-card'>
                <h3>How to read the evidence</h3>
                <p>Start with the headline comparison, then move to the hardest tasks, the user groups with the weakest results, and finally the comments that explain why those problems appeared.</p>
            </div>
            <div class='context-card'>
                <h3>How to interpret the current view</h3>
                <p>{escape(scope_text)} Filters update every chart and table together, so always read the findings as the visible sample on the page.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def prototype_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    summary = (
        data.groupby("prototype_version", observed=True)
        .agg(
            records=("participant_id", "size"),
            participants=("participant_id", pd.Series.nunique),
            task_success=("task_success", "mean"),
            completion_time_sec=("completion_time_sec", "mean"),
            errors=("errors", "mean"),
            help_needed=("help_needed", "mean"),
            avg_rating_1_5=("avg_rating_1_5", "mean"),
            usability_score_0_100=("usability_score_0_100", "mean"),
        )
        .reset_index()
    )
    return summary.sort_values("prototype_version")


def delta_between_prototypes(summary: pd.DataFrame, metric: str) -> float | None:
    if summary.empty or set(summary["prototype_version"]) != set(PROTOTYPE_ORDER):
        return None

    indexed = summary.set_index("prototype_version")
    return float(indexed.loc["Prototype B", metric] - indexed.loc["Prototype A", metric])


def rating_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    melted = (
        data.groupby("prototype_version", observed=True)[list(RATING_LABELS)]
        .mean()
        .reset_index()
        .melt(
            id_vars="prototype_version",
            value_vars=list(RATING_LABELS),
            var_name="metric",
            value_name="value",
        )
    )
    melted["metric_label"] = melted["metric"].map(RATING_LABELS)
    melted["metric_label"] = pd.Categorical(
        melted["metric_label"], categories=list(RATING_LABELS.values()), ordered=True
    )
    return melted.sort_values(["metric_label", "prototype_version"])


def task_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    summary = (
        data.groupby(["task_id", "task_name", "prototype_version"], observed=True)
        .agg(
            task_success=("task_success", "mean"),
            completion_time_sec=("completion_time_sec", "mean"),
            usability_score_0_100=("usability_score_0_100", "mean"),
            errors=("errors", "mean"),
        )
        .reset_index()
    )
    summary["task_label"] = summary["task_id"].astype(str) + " • " + summary["task_name"]

    overall_order = (
        summary.groupby("task_label", observed=True)
        .agg(task_success=("task_success", "mean"), completion_time_sec=("completion_time_sec", "mean"))
        .sort_values(["task_success", "completion_time_sec"], ascending=[True, False])
        .index.tolist()
    )
    summary["task_label"] = pd.Categorical(summary["task_label"], categories=overall_order, ordered=True)
    return summary.sort_values(["task_label", "prototype_version"])


def segment_summary(data: pd.DataFrame, segment_column: str, metric_column: str) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    summary = (
        data.groupby([segment_column, "prototype_version"], observed=True)
        .agg(value=(metric_column, "mean"), records=("participant_id", "size"))
        .reset_index()
        .rename(columns={segment_column: "segment"})
    )
    ascending = metric_column == "completion_time_sec"
    order = (
        summary.groupby("segment", observed=True)["value"]
        .mean()
        .sort_values(ascending=ascending)
        .index.tolist()
    )
    summary["segment"] = pd.Categorical(summary["segment"], categories=order, ordered=True)
    return summary.sort_values(["segment", "prototype_version"])


def issue_summary(data: pd.DataFrame, negative_only: bool = False) -> pd.DataFrame:
    base = data.copy()
    if negative_only:
        base = base[base["comment_sentiment"].astype(str) == "Negative"]

    issues = base[base["most_confusing_element"].fillna("None") != "None"]
    if issues.empty:
        return pd.DataFrame(columns=["most_confusing_element", "mentions"])

    summary = (
        issues.groupby("most_confusing_element", observed=True)
        .size()
        .reset_index(name="mentions")
        .sort_values(["mentions", "most_confusing_element"], ascending=[False, True])
    )
    return summary.head(7)


def sentiment_summary(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    summary = (
        data.groupby(["prototype_version", "comment_sentiment"], observed=True)
        .size()
        .reset_index(name="mentions")
    )
    summary["comment_sentiment"] = pd.Categorical(
        summary["comment_sentiment"], categories=SENTIMENT_ORDER, ordered=True
    )
    return summary.sort_values(["comment_sentiment", "prototype_version"])


def select_comment_samples(data: pd.DataFrame) -> dict[str, str]:
    samples: dict[str, str] = {}
    for sentiment in SENTIMENT_ORDER:
        subset = data[data["comment_sentiment"].astype(str) == sentiment]
        if subset.empty:
            samples[sentiment] = "No comments in this category for the current filter selection."
            continue
        top_comment = subset["open_comment"].value_counts().index[0]
        samples[sentiment] = top_comment
    return samples


def generate_insights(data: pd.DataFrame) -> list[tuple[str, str]]:
    insights: list[tuple[str, str]] = []
    proto = prototype_summary(data)
    if set(proto["prototype_version"].astype(str)) == set(PROTOTYPE_ORDER):
        delta_success = delta_between_prototypes(proto, "task_success")
        delta_time = delta_between_prototypes(proto, "completion_time_sec")
        delta_score = delta_between_prototypes(proto, "usability_score_0_100")
        insights.append(
            (
                "Overall result",
                f"Compared with Prototype A, Prototype B improves task success by {delta_success * 100:.1f} percentage points, changes average completion time by {delta_time:.1f} seconds, and lifts the usability score by {delta_score:.1f} points.",
            )
        )

    task = task_summary(data)
    if not task.empty:
        hardest = (
            task.groupby("task_label", observed=True)
            .agg(task_success=("task_success", "mean"), completion_time_sec=("completion_time_sec", "mean"))
            .sort_values(["task_success", "completion_time_sec"], ascending=[True, False])
            .reset_index()
            .iloc[0]
        )
        insights.append(
            (
                "Current bottleneck",
                f"{hardest['task_label']} is the hardest task in the current view, with {hardest['task_success'] * 100:.0f}% success and an average completion time of {hardest['completion_time_sec']:.0f} seconds.",
            )
        )

    devices = segment_summary(data, "device", "usability_score_0_100")
    literacy = segment_summary(data, "data_literacy", "usability_score_0_100")
    if not devices.empty and not literacy.empty:
        weakest_device = (
            devices.groupby("segment", observed=True)["value"].mean().sort_values().reset_index().iloc[0]
        )
        weakest_literacy = (
            literacy.groupby("segment", observed=True)["value"].mean().sort_values().reset_index().iloc[0]
        )
        insights.append(
            (
                "Users facing the most friction",
                f"{weakest_device['segment']} users and {str(weakest_literacy['segment']).lower()} data-literacy users record the weakest usability scores in the current selection, matching comments about readability, filtering clarity, and dense layouts.",
            )
        )

    negative_issues = issue_summary(data, negative_only=True)
    if not negative_issues.empty:
        top_issue = negative_issues.iloc[0]
        insights.append(
            (
                "Top confusion point",
                f"{top_issue['most_confusing_element']} is the issue mentioned most often in negative comments, making it the clearest candidate for redesign or clearer labeling.",
            )
        )

    return insights[:4]


def style_figure(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.92)",
        font={"family": "Source Sans 3, sans-serif", "size": 14, "color": COLORS["Text"]},
        legend_title_text="",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 18, "r": 18, "t": 56, "b": 18},
    )
    fig.update_xaxes(showline=False, gridcolor=COLORS["Grid"], zeroline=False)
    fig.update_yaxes(showline=False, gridcolor="rgba(0,0,0,0)", zeroline=False)
    return fig


def build_rating_chart(data: pd.DataFrame) -> go.Figure:
    summary = rating_summary(data)
    fig = px.bar(
        summary,
        x="value",
        y="metric_label",
        color="prototype_version",
        orientation="h",
        barmode="group",
        text="value",
        color_discrete_map={prototype: COLORS[prototype] for prototype in PROTOTYPE_ORDER},
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
    fig.update_xaxes(range=[0, 5], title="Average rating (1-5)", dtick=1)
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(RATING_LABELS.values()))
    fig.update_layout(title="Average ratings across key usability dimensions")
    return style_figure(fig, height=430)


def build_task_chart(data: pd.DataFrame) -> go.Figure:
    summary = task_summary(data)
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        horizontal_spacing=0.14,
        subplot_titles=("Task success rate", "Average completion time"),
    )

    for prototype in PROTOTYPE_ORDER:
        subset = summary[summary["prototype_version"].astype(str) == prototype]
        if subset.empty:
            continue
        fig.add_trace(
            go.Bar(
                x=subset["task_success"] * 100,
                y=subset["task_label"].astype(str),
                orientation="h",
                name=prototype,
                marker_color=COLORS[prototype],
                text=[f"{value:.0f}%" for value in subset["task_success"] * 100],
                textposition="outside",
                cliponaxis=False,
                legendgroup=prototype,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=subset["completion_time_sec"],
                y=subset["task_label"].astype(str),
                orientation="h",
                name=prototype,
                marker_color=COLORS[prototype],
                text=[f"{value:.0f} sec" for value in subset["completion_time_sec"]],
                textposition="outside",
                cliponaxis=False,
                legendgroup=prototype,
                showlegend=False,
            ),
            row=1,
            col=2,
        )

    fig.update_xaxes(title="Task success rate", ticksuffix="%", range=[0, 100], row=1, col=1)
    fig.update_xaxes(title="Average completion time (seconds)", row=1, col=2)
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=summary["task_label"].astype(str).drop_duplicates().tolist())
    fig.update_layout(title="Task outcomes by prototype")
    return style_figure(fig, height=500)


def build_segment_chart(data: pd.DataFrame, segment_label: str, metric_label: str) -> go.Figure:
    segment_column = SEGMENT_OPTIONS[segment_label]
    metric_column = METRIC_OPTIONS[metric_label]
    summary = segment_summary(data, segment_column, metric_column)

    fig = px.bar(
        summary,
        x="value",
        y="segment",
        color="prototype_version",
        orientation="h",
        barmode="group",
        text="value",
        color_discrete_map={prototype: COLORS[prototype] for prototype in PROTOTYPE_ORDER},
    )
    fig.update_layout(title=f"{metric_label} by {segment_label.lower()} and prototype")

    if metric_label == "Task success":
        fig.update_traces(texttemplate="%{text:.0%}", textposition="outside", cliponaxis=False)
        fig.update_xaxes(title="Task success rate", ticksuffix="%", range=[0, 1])
    elif metric_label == "Completion time":
        fig.update_traces(texttemplate="%{text:.0f} sec", textposition="outside", cliponaxis=False)
        fig.update_xaxes(title="Average completion time (seconds)")
    elif metric_label == "Accessibility rating":
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside", cliponaxis=False)
        fig.update_xaxes(title="Average rating (1-5)", range=[0, 5], dtick=1)
    else:
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
        fig.update_xaxes(title="Usability score (0-100)", range=[0, 100])

    fig.update_yaxes(title=None)
    return style_figure(fig, height=470)


def build_issue_chart(data: pd.DataFrame, negative_only: bool = False) -> go.Figure | None:
    summary = issue_summary(data, negative_only=negative_only)
    if summary.empty:
        return None

    summary = summary.iloc[::-1].copy()
    bar_color = COLORS["Alert"] if negative_only else COLORS["Accent"]
    title = "Confusion points mentioned in negative comments" if negative_only else "Most frequently cited points of confusion"

    fig = px.bar(
        summary,
        x="mentions",
        y="most_confusing_element",
        orientation="h",
        text="mentions",
    )
    fig.update_traces(marker_color=bar_color, textposition="outside", cliponaxis=False)
    fig.update_layout(title=title, showlegend=False)
    fig.update_xaxes(title="Number of mentions")
    fig.update_yaxes(title=None)
    return style_figure(fig, height=380)


def build_sentiment_chart(data: pd.DataFrame) -> go.Figure:
    summary = sentiment_summary(data)
    fig = px.bar(
        summary,
        x="mentions",
        y="comment_sentiment",
        color="prototype_version",
        orientation="h",
        barmode="group",
        text="mentions",
        color_discrete_map={prototype: COLORS[prototype] for prototype in PROTOTYPE_ORDER},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(title="Number of comments")
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=SENTIMENT_ORDER[::-1])
    fig.update_layout(title="Comment sentiment split by prototype")
    return style_figure(fig, height=380)


def render_insight_cards(insights: list[tuple[str, str]]) -> None:
    for title, body in insights:
        st.markdown(
            f"<div class='insight-card'><h4>{escape(title)}</h4><p>{escape(body)}</p></div>",
            unsafe_allow_html=True,
        )


def render_quote_cards(samples: dict[str, str]) -> None:
    columns = st.columns(3)
    for column, sentiment in zip(columns, SENTIMENT_ORDER, strict=True):
        with column:
            st.markdown(
                f"<div class='quote-card'><div class='quote-label'>{escape(sentiment)}</div><blockquote>{escape(samples[sentiment])}</blockquote></div>",
                unsafe_allow_html=True,
            )


def render_method_expander(data_dictionary: pd.DataFrame, full_data: pd.DataFrame) -> None:
    with st.expander("Study scope and metric definitions", expanded=False):
        st.markdown(
            f"<div class='method-note'>This dashboard summarizes a comparative usability study of Prototype A and Prototype B. The full dataset contains {full_data['participant_id'].nunique():,} participants, {len(full_data):,} task records, and {full_data['task_name'].nunique()} distinct task types. Each record combines behavioral measures such as task success, completion time, errors, and help needed with participant ratings and open comments.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("#### Metric definitions and raw fields")
        st.dataframe(data_dictionary, use_container_width=True)
        st.caption(
            f"Study scope: {full_data['participant_id'].nunique()} participants, {len(full_data)} task records, {full_data['task_name'].nunique()} distinct task types."
        )


def render_overview(data: pd.DataFrame) -> None:
    st.markdown("## Executive summary")
    st.markdown(
        "<p class='section-lead'>Start here for the headline result. This section compares the two prototypes at a glance before you drill into specific tasks, user groups, or comments.</p>",
        unsafe_allow_html=True,
    )

    summary = prototype_summary(data)
    success_delta = delta_between_prototypes(summary, "task_success")
    score_delta = delta_between_prototypes(summary, "usability_score_0_100")
    time_delta = delta_between_prototypes(summary, "completion_time_sec")
    rating_delta = delta_between_prototypes(summary, "avg_rating_1_5")

    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric(
            "Task success",
            f"{data['task_success'].mean():.0%}",
            delta=f"{success_delta * 100:+.1f} pp vs A" if success_delta is not None else None,
        )
    with metric_columns[1]:
        st.metric(
            "Usability score",
            f"{data['usability_score_0_100'].mean():.1f} / 100",
            delta=f"{score_delta:+.1f} vs A" if score_delta is not None else None,
        )
    with metric_columns[2]:
        st.metric(
            "Average completion time",
            f"{data['completion_time_sec'].mean():.0f} sec",
            delta=f"{time_delta:+.1f} sec vs A" if time_delta is not None else None,
            delta_color="inverse",
        )
    with metric_columns[3]:
        st.metric(
            "Average rating",
            f"{data['avg_rating_1_5'].mean():.2f} / 5",
            delta=f"{rating_delta:+.2f} vs A" if rating_delta is not None else None,
        )

    chart_column, insight_column = st.columns([1.6, 1], gap="large")
    with chart_column:
        st.plotly_chart(
            build_rating_chart(data),
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
        )
        st.caption(
            "Use this chart to compare how participants rated the two prototypes across the main usability dimensions."
        )
        with st.expander("Open the supporting prototype summary table", expanded=False):
            table = summary.copy()
            table["task_success"] = table["task_success"].map(lambda value: f"{value:.0%}")
            table["completion_time_sec"] = table["completion_time_sec"].map(lambda value: f"{value:.0f} sec")
            table["errors"] = table["errors"].map(lambda value: f"{value:.2f}")
            table["help_needed"] = table["help_needed"].map(lambda value: f"{value:.0%}")
            table["avg_rating_1_5"] = table["avg_rating_1_5"].map(lambda value: f"{value:.2f}")
            table["usability_score_0_100"] = table["usability_score_0_100"].map(lambda value: f"{value:.1f}")
            st.dataframe(table, use_container_width=True)

    with insight_column:
        st.markdown("### Headline findings")
        render_insight_cards(generate_insight_cards(data))


def generate_insight_cards(data: pd.DataFrame) -> list[tuple[str, str]]:
    insights = generate_insights(data)
    if insights:
        return insights
    return [("Current scope", "Select a broader range of records to restore comparison insights.")]


def render_task_section(data: pd.DataFrame) -> None:
    st.markdown("## Where users struggled")
    st.markdown(
        "<p class='section-lead'>This section shows task-level performance. Tasks are ordered from hardest to easiest so the biggest usability problems stay visible first.</p>",
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        build_task_chart(data),
        use_container_width=True,
        config={"displayModeBar": False, "responsive": True},
    )
    hardest_task = (
        task_summary(data)
        .groupby("task_label", observed=True)
        .agg(task_success=("task_success", "mean"), completion_time_sec=("completion_time_sec", "mean"))
        .sort_values(["task_success", "completion_time_sec"], ascending=[True, False])
        .reset_index()
        .iloc[0]
    )
    st.info(
        f"Current bottleneck: {hardest_task['task_label']} has the weakest results in the current view, with {hardest_task['task_success'] * 100:.0f}% success and an average completion time of {hardest_task['completion_time_sec']:.0f} seconds."
    )
    with st.expander("Open the task results table", expanded=False):
        table = task_summary(data).copy()
        table["task_success"] = table["task_success"].map(lambda value: f"{value:.0%}")
        table["completion_time_sec"] = table["completion_time_sec"].map(lambda value: f"{value:.0f} sec")
        table["usability_score_0_100"] = table["usability_score_0_100"].map(lambda value: f"{value:.1f}")
        table["errors"] = table["errors"].map(lambda value: f"{value:.2f}")
        st.dataframe(
            table[[
                "prototype_version",
                "task_label",
                "task_success",
                "completion_time_sec",
                "usability_score_0_100",
                "errors",
            ]],
            use_container_width=True,
        )


def render_segment_section(data: pd.DataFrame) -> None:
    st.markdown("## Which users struggled most")
    st.markdown(
        "<p class='section-lead'>Use this section to see whether the overall result holds across devices, roles, and data-literacy levels, or whether certain user groups experienced more friction than others.</p>",
        unsafe_allow_html=True,
    )

    control_columns = st.columns([1.2, 1.2, 2.2])
    with control_columns[0]:
        segment_label = st.radio(
            "Compare user group by",
            options=list(SEGMENT_OPTIONS),
            horizontal=False,
        )
    with control_columns[1]:
        metric_label = st.radio(
            "Show metric",
            options=list(METRIC_OPTIONS),
            index=0,
            horizontal=False,
        )
    with control_columns[2]:
        segment_column = SEGMENT_OPTIONS[segment_label]
        metric_column = METRIC_OPTIONS[metric_label]
        segment_table = segment_summary(data, segment_column, metric_column)
        if not segment_table.empty:
            if metric_label == "Completion time":
                weakest = segment_table.groupby("segment", observed=True)["value"].mean().sort_values(ascending=False).index[0]
                helper_text = f"Slowest group in the current view: {weakest}."
            else:
                weakest = segment_table.groupby("segment", observed=True)["value"].mean().sort_values().index[0]
                helper_text = f"Lowest {metric_label.lower()} in the current view: {weakest}."
            st.markdown(f"<div class='method-note'>{escape(helper_text)}</div>", unsafe_allow_html=True)

    st.plotly_chart(
        build_segment_chart(data, segment_label, metric_label),
        use_container_width=True,
        config={"displayModeBar": False, "responsive": True},
    )
    with st.expander("Open the subgroup comparison table", expanded=False):
        table = segment_summary(data, SEGMENT_OPTIONS[segment_label], METRIC_OPTIONS[metric_label]).copy()
        formatter = METRIC_FORMATTERS[metric_label]
        table["value"] = table["value"].map(formatter)
        st.dataframe(table.rename(columns={"value": metric_label}), use_container_width=True)


def render_issue_section(data: pd.DataFrame) -> None:
    st.markdown("## Why users struggled")
    st.markdown(
        "<p class='section-lead'>Performance metrics show where friction happened. This section adds the reasons behind those outcomes by summarizing reported confusion points and showing representative participant comments.</p>",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")
    issue_fig = build_issue_chart(data, negative_only=False)
    with left:
        if issue_fig is not None:
            st.plotly_chart(issue_fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})
        else:
            st.info("No confusing element was reported in the current selection.")
    with right:
        negative_issue_fig = build_issue_chart(data, negative_only=True)
        if negative_issue_fig is not None:
            st.plotly_chart(
                negative_issue_fig,
                use_container_width=True,
                config={"displayModeBar": False, "responsive": True},
            )
        else:
            st.plotly_chart(
                build_sentiment_chart(data),
                use_container_width=True,
                config={"displayModeBar": False, "responsive": True},
            )

    st.markdown("### Representative participant comments")
    render_quote_cards(select_comment_samples(data))

    with st.expander("Open the filtered comments table", expanded=False):
        comments_table = data[[
            "prototype_version",
            "task_label",
            "device",
            "data_literacy",
            "comment_sentiment",
            "most_confusing_element",
            "open_comment",
        ]].copy()
        st.dataframe(comments_table, use_container_width=True)


def render_detail_section(data: pd.DataFrame) -> None:
    st.markdown("## Underlying records")
    st.markdown(
        "<p class='section-lead'>Use this table when you need the task-level records behind the summary charts or want to export the currently visible sample.</p>",
        unsafe_allow_html=True,
    )
    display_columns = [
        "participant_id",
        "prototype_version",
        "task_label",
        "device",
        "role",
        "data_literacy",
        "task_success",
        "completion_time_sec",
        "errors",
        "help_needed",
        "avg_rating_1_5",
        "usability_score_0_100",
        "most_confusing_element",
        "comment_sentiment",
    ]
    detail_table = data[display_columns].copy()
    detail_table["task_success"] = detail_table["task_success"].map(lambda value: f"{value:.0%}")
    detail_table["completion_time_sec"] = detail_table["completion_time_sec"].map(lambda value: f"{value:.0f} sec")
    detail_table["help_needed"] = detail_table["help_needed"].map(lambda value: f"{value:.0%}")
    detail_table["avg_rating_1_5"] = detail_table["avg_rating_1_5"].map(lambda value: f"{value:.2f}")
    detail_table["usability_score_0_100"] = detail_table["usability_score_0_100"].map(lambda value: f"{value:.1f}")

    st.dataframe(detail_table, use_container_width=True, height=360)
    st.download_button(
        label="Download the current records as CSV",
        data=data.to_csv(index=False).encode("utf-8"),
        file_name="filtered_usability_records.csv",
        mime="text/csv",
    )


def render_sidebar(full_data: pd.DataFrame, options: dict[str, list[str]]) -> None:
    st.sidebar.markdown("## Filter the study")
    st.sidebar.caption("Choose which participants, tasks, and comments to include. Every chart and table on the page updates together.")
    st.sidebar.button("Reset all filters", use_container_width=True, on_click=reset_filters, args=(options,))

    for column, label in FILTER_LABELS.items():
        multiselect_kwargs = {
            "key": f"filter_{column}",
            "help": f"Limit the dashboard to selected {label.lower()} values.",
        }
        if column == "task_id":
            multiselect_kwargs["format_func"] = lambda value, source=full_data: format_task_option(value, source)

        st.sidebar.multiselect(label, options[column], **multiselect_kwargs)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Study question")
    st.sidebar.write("Does Prototype B outperform Prototype A overall, and where does friction still remain?")
    st.sidebar.markdown("### How to read this page")
    st.sidebar.write("1. Start with the executive summary for the headline comparison.")
    st.sidebar.write("2. Review the task section to find the hardest user journeys.")
    st.sidebar.write("3. Use user groups and comments to explain why those patterns appear.")


def main() -> None:
    inject_styles()
    data, data_dictionary = load_data()
    options = build_filter_options(data)
    initialize_filter_state(options)
    render_sidebar(data, options)

    filtered = apply_filters(data, options)

    render_page_intro(data, filtered)

    if filtered.empty:
        st.warning("No records match the current filter selection. Reset the filters to restore the full study sample.")
        st.stop()

    st.markdown(active_filter_markup(filtered, options), unsafe_allow_html=True)
    render_method_expander(data_dictionary, data)
    render_overview(filtered)
    render_task_section(filtered)
    render_segment_section(filtered)
    render_issue_section(filtered)
    render_detail_section(filtered)


if __name__ == "__main__":
    main()