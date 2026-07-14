"""
Trade Governance Lab — WTO discussion analytics dashboard.

This revision:
- Per-tab focus filters are multiselect and default to "all" (leave empty = everything).
- Metric ribbons hide any dimension that collapses to a single value (no more useless "1 Member").
- Softer, eye-friendly chart palette; bright purple reserved for titles/headings only.
- Title and sub-title centred; sub-title reworded and resized.
- Hierarchy treemaps replaced with clean colour-grouped bars (simpler, readable on mobile).
- Plotly modebar hidden so the chart toolbar no longer overlaps titles on phones.
- Axis labels protected from clipping (horizontal orientation + auto-margins).
- "Over time" charts gated behind SHOW_TIME_CHARTS — flip on once multi-year data exists.

The "AI Summary" boxes are generated deterministically from the data in the current view
(no API key needed) and update live with the filters. Swap the narrate text for a real LLM
call later if desired.
"""

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

# --------------------------------------------------------------------------------------
# Config / theming
# --------------------------------------------------------------------------------------
st.set_page_config(page_title="Trade Governance Lab", page_icon="🌐", layout="wide")

SHOW_TIME_CHARTS = False          # turn on when more than one year of data is available
NO_MEASURE = "No Specific Measure"

# Deep ocean-blue: titles, headings, accents (replaces the previous jarring magenta).
PRIMARY = "#1F5A7A"
HEADING = "#234E63"
# Charts: muted, harmonious palette that is easy on the eye.
CHART = "#5B8DA6"                 # single-series bars / heatmap accent (soft steel-blue)
PALETTE = ["#5B8DA6", "#E0A458", "#7FB685", "#9D8EC4", "#5BA8A0", "#C98BB9", "#8C9EC4", "#D4B483"]
HEAT_SCALE = ["#F4F7F9", "#BBD0DC", "#7FA9C0", "#4E7E9C", "#2E5C78"]

# WTO bodies shown by their full names (no bracketed codes, "Committee" spelled out).
FORUM_NAMES = {
    "GC": "GC",
    "CTG": "CTG",
    "CTD": "CTD",
    "CTE": "CTE",
    "CTF": "CTF",
}

PCONF = {"displayModeBar": False, "responsive": True}   # hide plotly toolbar → no title overlap

# Shared plotly template.
pio.templates["tgl"] = pio.templates["plotly_white"]
pio.templates["tgl"].layout.update(
    colorway=PALETTE,
    font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=13, color="#33384a"),
    margin=dict(l=12, r=18, t=54, b=14),
    title=dict(font=dict(size=15, color="#2b2740"), x=0, xanchor="left"),
    xaxis=dict(automargin=True),
    yaxis=dict(automargin=True),
    legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5, title_text=""),
)
pio.templates.default = "tgl"

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.4rem; padding-bottom: 2rem; max-width: 1500px; }}
      h1,h2,h3,h4 {{ color: {HEADING}; }}
      .app-title {{ text-align:center; color:{PRIMARY}; font-weight:700; width:100%;
                    font-size: clamp(1.6rem, 3.6vw, 2.3rem); line-height:1.5;
                    margin: 0 0 4px 0; padding: 8px 6px 2px 6px; overflow:visible; }}
      .app-sub {{ text-align:center; color:#6b6680; font-size: clamp(.92rem, 1.8vw, 1.05rem);
                  font-weight:400; margin: 0 auto 18px auto; max-width: 760px; padding: 0 6px; }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 4px; flex-wrap: wrap; justify-content:center; }}
      .stTabs [data-baseweb="tab"] {{ font-weight:600; padding:8px 16px; border-radius:10px 10px 0 0; }}
      .stTabs [aria-selected="true"] {{ background:{PRIMARY}12; color:{PRIMARY};
                                        border-bottom:3px solid {PRIMARY}; }}
      div[data-testid="stMetricValue"] {{ color:{PRIMARY}; font-size:1.6rem; }}
      .ai-box {{ background: linear-gradient(135deg,{PRIMARY}0D,{PRIMARY}04);
                 border:1px solid {PRIMARY}2E; border-left:5px solid {PRIMARY};
                 border-radius:12px; padding:14px 18px; margin:6px 0 18px 0;
                 font-size:.96rem; line-height:1.55; }}
      .ai-box .tag {{ display:inline-block; font-size:.7rem; font-weight:700; letter-spacing:.06em;
                      text-transform:uppercase; color:{PRIMARY}; margin-bottom:6px; }}
      @media (max-width: 640px) {{
          .block-container {{ padding-left:.6rem; padding-right:.6rem; }}
          div[data-testid="stMetricValue"] {{ font-size:1.2rem; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_excel("WTO_Database.xlsx", sheet_name="Database")
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    return df


def add_forum_labels(df):
    # Done OUTSIDE the cached loader so edits to FORUM_NAMES take effect immediately
    # (st.cache_data does not track changes to module-level globals used inside it).
    df = df.copy()
    df["Forum"] = df["WTO_Forum"].map(FORUM_NAMES).fillna(df["WTO_Forum"])
    return df


def melt_pairs(data, base, n, names=("Dimension", "Topic")):
    keep = [c for c in ["Participant", "Forum", "Domain Family", "Governance function"] if c in data.columns]
    parts = []
    for i in range(1, n + 1):
        a, b = f"{base[0]} {i}", f"{base[1]} {i}"
        if a in data.columns and b in data.columns:
            sub = data[[*keep, a, b]].copy()
            sub.columns = [*keep, names[0], names[1]]
            parts.append(sub)
    if not parts:
        return pd.DataFrame(columns=[*keep, *names])
    return pd.concat(parts, ignore_index=True).dropna(subset=[names[0]])


def melt_subdomains(data):
    keep = [c for c in ["Participant", "Forum", "Domain Family", "Governance function"] if c in data.columns]
    parts = []
    for i in range(1, 4):
        col = f"Sub-Domain {i}"
        if col in data.columns:
            sub = data[[*keep, col]].copy()
            sub.columns = [*keep, "Sub-Domain"]
            parts.append(sub)
    if not parts:
        return pd.DataFrame(columns=[*keep, "Sub-Domain"])
    return pd.concat(parts, ignore_index=True).dropna(subset=["Sub-Domain"])


def vc(series, top=None):
    out = series.dropna().value_counts()
    if top:
        out = out.head(top)
    out = out.reset_index()
    out.columns = ["label", "count"]
    return out


def pct(part, whole):
    return 0 if not whole else round(part / whole * 100, 1)


# --------------------------------------------------------------------------------------
# Chart helpers
# --------------------------------------------------------------------------------------
def show(container, fig, key):
    container.plotly_chart(fig, width="stretch", config=PCONF, key=key)


def int_axis(fig, maxval, axis="x"):
    """Force whole-number ticks on a count axis (interaction counts are never fractional)."""
    upd = fig.update_xaxes if axis == "x" else fig.update_yaxes
    if maxval is None or maxval <= 1:
        upd(tickformat="d", dtick=1, rangemode="tozero")
    elif maxval <= 10:
        upd(tickformat="d", dtick=1)
    else:
        upd(tickformat="d")           # auto ticks already land on integers for larger ranges
    return fig


def hbar(data, title, height=None):
    """Single-series horizontal bar, biggest on top, muted colour."""
    data = data.sort_values("count")
    h = height or max(220, 34 * len(data) + 90)
    fig = px.bar(data, x="count", y="label", orientation="h", title=title)
    fig.update_traces(marker_color=CHART)
    fig.update_layout(height=h, yaxis_title=None, xaxis_title=None, showlegend=False)
    int_axis(fig, data["count"].max() if len(data) else 0)
    return fig


def grouped_hbar(data, ycol, color, title, top=15, height=None):
    """Horizontal bar coloured by a parent category — replaces the hierarchy treemaps."""
    data = data.sort_values("count").tail(top)
    h = height or max(260, 30 * len(data) + 120)
    fig = px.bar(data, x="count", y=ycol, color=color, orientation="h",
                 title=title, color_discrete_sequence=PALETTE)
    fig.update_layout(height=h, yaxis_title=None, xaxis_title=None, barmode="stack",
                      legend_title_text="", margin=dict(t=50, b=80, l=10, r=18),
                      legend=dict(orientation="h", yanchor="top", y=-0.12, x=0.5, xanchor="center"))
    totals = data.groupby(ycol)["count"].sum().max() if len(data) else 0
    int_axis(fig, totals)
    return fig


def heatmap(matrix, title, height=380, tickangle=-18):
    fig = px.imshow(matrix, aspect="auto", text_auto=True,
                    color_continuous_scale=HEAT_SCALE, title=title)
    fig.update_layout(height=height, xaxis_title=None, yaxis_title=None,
                      coloraxis_showscale=False)
    fig.update_xaxes(tickangle=tickangle)
    return fig


def ai_summary(text):
    st.markdown(f"<div class='ai-box'><span class='tag'>🤖 AI Summary</span><br>{text}</div>",
                unsafe_allow_html=True)


HELP = {
    "Interactions": "One member intervention on one document/topic.",
    "Members": "Distinct members taking part.",
    "WTO bodies": "Distinct WTO councils/committees involved.",
    "Domain families": "Top-level subject areas.",
    "Measures": "Named policy measures discussed.",
    "Functions": "How members engage: Concern Raised, Proposal/Recommendation, "
                 "Defence/Explanation, Information Sharing.",
}


def metric_strip(data):
    """Show metrics, but drop any dimension that collapses to a single value (keeps the ribbon
    meaningful — e.g. when one member is selected, the 'Members' tile disappears)."""
    raw = [
        ("Interactions", len(data)),
        ("Members", data["Participant"].nunique()),
        ("WTO bodies", data["Forum"].nunique()),
        ("Domain families", data["Domain Family"].nunique()),
        ("Measures", data[data["Measure"] != NO_MEASURE]["Measure"].nunique()),
        ("Functions", data["Governance function"].nunique()),
    ]
    visible = [(l, v) for l, v in raw if l == "Interactions" or v > 1]
    cols = st.columns(len(visible))
    for c, (label, value) in zip(cols, visible):
        c.metric(label, value, help=HELP.get(label))


def members_phrase(data):
    n = data["Participant"].nunique()
    if n == 1:
        return f"<b>{data['Participant'].dropna().iloc[0]}</b>"
    return f"<b>{n} members</b>"


def bodies_phrase(data):
    n = data["Forum"].nunique()
    if n == 1:
        return f"the <b>{data['Forum'].dropna().iloc[0]}</b>"
    return f"<b>{n} WTO bodies</b>"


df = add_forum_labels(load_data())

# --------------------------------------------------------------------------------------
# Global filters (sidebar, multiselect, empty = all)
# --------------------------------------------------------------------------------------
st.sidebar.title("🌐 Filters")
st.sidebar.caption("Leave a filter empty to include everything. Applies across all tabs.")

body_filter = st.sidebar.multiselect("WTO Body", sorted(df["Forum"].dropna().unique()))
member_filter = st.sidebar.multiselect("Member", sorted(df["Participant"].dropna().unique()))
domain_filter = st.sidebar.multiselect("Domain Family", sorted(df["Domain Family"].dropna().unique()))
func_filter = st.sidebar.multiselect("Governance Function", sorted(df["Governance function"].dropna().unique()))

filtered = df.copy()
if body_filter:
    filtered = filtered[filtered["Forum"].isin(body_filter)]
if member_filter:
    filtered = filtered[filtered["Participant"].isin(member_filter)]
if domain_filter:
    filtered = filtered[filtered["Domain Family"].isin(domain_filter)]
if func_filter:
    filtered = filtered[filtered["Governance function"].isin(func_filter)]

st.sidebar.markdown("---")
st.sidebar.metric("Rows in current view", f"{len(filtered)} / {len(df)}")
if st.sidebar.button("Reset filters", width="stretch", key="reset_btn"):
    st.rerun()

# --------------------------------------------------------------------------------------
# Centred header
# --------------------------------------------------------------------------------------
st.markdown("<div class='app-title'>Trade Governance Lab</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='app-sub'>How WTO members engage with trade-policy topics across different WTO bodies.</div>",
    unsafe_allow_html=True,
)

st.caption(
    "**WTO Body legend:** "
    "**GC** = General Council · "
    "**CTG** = Council for Trade in Goods · "
    "**CTD** = Committee on Trade and Development · "
    "**CTE** = Committee on Trade and Environment · "
    "**CTF** = Committee on Trade Facilitation"
)
st.info("**Last updated:** 14 July 2026   |   **Period covered:** 1 Jan 2026 to 15 Jun 2026")


if filtered.empty:
    st.warning("No rows match the current filters. Use **Reset filters** in the sidebar.")
    st.stop()

tab_overview, tab_bodies, tab_gov, tab_dom, tab_mem, tab_meas, tab_exp = st.tabs(
    ["📊 Overview", "🏢 WTO Bodies", "🏛️ Governance", "🗂️ Domains", "👥 Members", "📑 Measures", "🔎 Explorer"]
)

# ======================================================================================
# OVERVIEW
# ======================================================================================
with tab_overview:
    metric_strip(filtered)

    funcs = vc(filtered["Governance function"])
    dom = vc(filtered["Domain Family"])
    real_measures = filtered[filtered["Measure"] != NO_MEASURE]
    top_measure = vc(real_measures["Measure"], 1)
    top_member = vc(filtered["Participant"], 1)

    summary = (f"This view covers <b>{len(filtered)} interactions</b> from "
               f"{members_phrase(filtered)} across {bodies_phrase(filtered)}. ")
    if not funcs.empty:
        summary += (f"The dominant mode of engagement is <b>{funcs.iloc[0]['label']}</b> "
                    f"({pct(funcs.iloc[0]['count'], len(filtered))}% of activity). ")
    if not dom.empty:
        summary += f"Discussion is concentrated in <b>{dom.iloc[0]['label']}</b>. "
    if not top_measure.empty:
        summary += f"The most-debated named measure is <b>{top_measure.iloc[0]['label']}</b>"
        if filtered["Participant"].nunique() > 1 and not top_member.empty:
            summary += f", and the most active member is <b>{top_member.iloc[0]['label']}</b>"
        summary += "."
    ai_summary(summary)


    st.markdown("### Explore the dataset")

    view = st.radio(
        "Analyse interactions by",
        [
            "Measures",
            "Members",
            "Domain Families",
                        "WTO Bodies",
        ],
        horizontal=True,
        key="overview_selector",
    )

    if view == "Measures":
        fig = hbar(vc(real_measures["Measure"], 12), "Top measures (by interactions)")
    elif view == "Members":
        fig = hbar(vc(filtered["Participant"], 12), "Top members (by interactions)")
    elif view == "Domain Families":
        fig = hbar(vc(filtered["Domain Family"]), "Domain family share")
    else:
        fig = hbar(vc(filtered["Forum"]), "Activity by WTO body")

    show(st, fig, "overview_dynamic_chart")

    with st.expander("Show underlying data"):
        display_cols = [
            c for c in [
                "Date",
                "Participant",
                "Forum",
                "Domain Family",
                "Governance function",
                "Measure",
                "Interaction_Summary",
            ]
            if c in filtered.columns
        ]
        st.dataframe(
            filtered[display_cols].sort_values("Date"),
            width="stretch",
            hide_index=True,
        )

# ======================================================================================
# GOVERNANCE
# ======================================================================================
with tab_gov:
    gov_long = melt_pairs(filtered, ("Governance Dimension", "Governance Topic"), 5)
    dims = vc(gov_long["Dimension"])
    topics = vc(gov_long["Topic"], 1)

    summary = (f"Members invoked <b>{len(gov_long)} governance considerations</b> across "
               f"<b>{gov_long['Dimension'].nunique()} dimensions</b>. ")
    if not dims.empty:
        summary += (f"The most prominent dimension is <b>{dims.iloc[0]['label']}</b> "
                    f"({pct(dims.iloc[0]['count'], max(len(gov_long), 1))}% of considerations). ")
    if not topics.empty:
        summary += f"The single most-raised topic is <b>{topics.iloc[0]['label']}</b>. "
    summary += ("The heatmap shows how each governance function maps onto each domain family.")
    ai_summary(summary)

    c1, c2 = st.columns(2)
    show(c1, hbar(vc(filtered["Governance function"]), "Governance functions"), "gov_func")
    show(c2, hbar(dims, "Governance dimensions raised"), "gov_dims")

    # Cleaner than a treemap: topics as bars, coloured by their parent dimension.
    topic_dim = gov_long.groupby(["Dimension", "Topic"]).size().reset_index(name="count")
    if not topic_dim.empty:
        show(st, grouped_hbar(topic_dim, "Topic", "Dimension",
                              "Governance topics (coloured by dimension)", top=14), "gov_topics")

    c3 = st.container()
    # Domain families (long names) on the y-axis where they have room; functions angled on x.
    heat = pd.crosstab(filtered["Domain Family"], filtered["Governance function"])
    if heat.size:
        show(c3, heatmap(heat, "Domain family × governance function"), "gov_heat")

    # Horizontal stacked → forum names no longer clipped; titles cleared to avoid overlap.
    stacked = filtered.groupby(["Forum", "Governance function"]).size().reset_index(name="count")
    fig = px.bar(stacked, y="Forum", x="count", color="Governance function", orientation="h",
                 title="How each body engages", color_discrete_sequence=PALETTE)
    fig.update_layout(height=430, barmode="stack", xaxis_title=None, yaxis_title=None,
                      legend_title_text="", margin=dict(t=50, b=120, l=10, r=18),
                      legend=dict(orientation="h", yanchor="top", y=-0.32, x=0.5, xanchor="center"))
    int_axis(fig, stacked.groupby("Forum")["count"].sum().max() if len(stacked) else 0)

    with st.expander("Read the underlying interactions"):
        cols_show = [
            c
            for c in [
                "Date",
                "Participant",
                "Forum",
                "Domain Family",
                "Governance function",
                "Measure",
                "Interaction_Summary",
            ]
            if c in bdata.columns
        ]
        st.dataframe(
            bdata[cols_show].sort_values("Date"),
            width="stretch",
            hide_index=True,
        )


# ======================================================================================
# EXPLORER
# ======================================================================================
with tab_exp:
    ai_summary("The full filtered dataset. Search across every field, scan the records, and "
               f"download the current <b>{len(filtered)}-row</b> view as CSV for your own analysis.")
    search = st.text_input("Search all columns")
    table = filtered.copy()
    if search:
        mask = table.astype(str).apply(lambda s: s.str.contains(search, case=False, na=False))
        table = table[mask.any(axis=1)]
    st.caption(f"Showing {len(table)} rows.")
    st.dataframe(table, width="stretch", height=620, hide_index=True)
    st.download_button("⬇️ Download filtered data (CSV)", table.to_csv(index=False),
                       "trade_governance_lab.csv", "text/csv", width="stretch", key="dl_btn")
