"""
Trade Governance Lab — WTO discussion analytics dashboard.

What changed vs the original:
- Navigation moved from the left sidebar to on-page tabs (st.tabs).
- Every tab opens with an auto-generated "AI Summary" that reacts to the active filters.
- Governance dimensions/topics are reshaped from the 5 column-pairs so they actually render.
- Sub-domains are reshaped from the 3 column-pairs and grouped under their Domain Family.
- The "No Specific Measure" rows are now correctly excluded from measure charts.
- Members and Measures tabs gained real profiles (functions, domains, dimensions, forums, timelines).
- A monthly activity timeline now uses the previously unused Date column.
- Layout, fonts and chart sizing tuned to stay clean on phone / tablet / laptop.

Note on the "AI Summary": these narratives are generated deterministically from the data in
the current view (no external API key required), so they always work offline and update live
with the filters. To swap in a real LLM, replace the body of the narrate_* functions with an
API call that receives the same summary statistics.
"""

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

# --------------------------------------------------------------------------------------
# Page config + theming
# --------------------------------------------------------------------------------------
st.set_page_config(page_title="Trade Governance Lab", page_icon="🌐", layout="wide")

PRIMARY = "#9A05A9"
# Sequential-ish palette built around the primary purple, used everywhere for consistency.
PALETTE = ["#9A05A9", "#C13BD6", "#6A1B9A", "#E879F9", "#3F51B5", "#00ACC1", "#F4A261", "#2A9D8F"]

# Map terse WTO forum codes to readable names (code kept in parentheses for the curious).
FORUM_NAMES = {
    "GC": "General Council (GC)",
    "CTG": "Council for Trade in Goods (CTG)",
    "CTD": "Cttee on Trade & Development (CTD)",
    "CTE": "Cttee on Trade & Environment (CTE)",
    "CTF": "Cttee on Trade Facilitation (CTF)",
}

# A single plotly template so every chart shares the same look.
_base = pio.templates["plotly_white"]
pio.templates["tgl"] = _base
pio.templates["tgl"].layout.update(
    colorway=PALETTE,
    font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=13, color="#1f2333"),
    margin=dict(l=10, r=10, t=48, b=10),
    title=dict(font=dict(size=16)),
    legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0),
)
pio.templates.default = "tgl"

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }}
      h1, h2, h3 {{ color: #1b1233; }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 4px; flex-wrap: wrap; }}
      .stTabs [data-baseweb="tab"] {{
          font-weight: 600; padding: 8px 16px; border-radius: 10px 10px 0 0;
      }}
      .stTabs [aria-selected="true"] {{
          background: {PRIMARY}14; color: {PRIMARY}; border-bottom: 3px solid {PRIMARY};
      }}
      div[data-testid="stMetricValue"] {{ color: {PRIMARY}; font-size: 1.7rem; }}
      .ai-box {{
          background: linear-gradient(135deg, {PRIMARY}0F, {PRIMARY}05);
          border: 1px solid {PRIMARY}33; border-left: 5px solid {PRIMARY};
          border-radius: 12px; padding: 14px 18px; margin: 6px 0 18px 0; font-size: 0.96rem;
          line-height: 1.55;
      }}
      .ai-box .tag {{
          display:inline-block; font-size:0.7rem; font-weight:700; letter-spacing:.06em;
          text-transform:uppercase; color:{PRIMARY}; margin-bottom:6px;
      }}
      @media (max-width: 640px) {{
          .block-container {{ padding-left: 0.6rem; padding-right: 0.6rem; }}
          div[data-testid="stMetricValue"] {{ font-size: 1.25rem; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------------------
# Data loading + reshaping helpers
# --------------------------------------------------------------------------------------
NO_MEASURE = "No Specific Measure"


@st.cache_data
def load_data():
    df = pd.read_excel("WTO_Database.xlsx", sheet_name="Database")
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["Forum"] = df["WTO_Forum"].map(FORUM_NAMES).fillna(df["WTO_Forum"])
    return df


def melt_pairs(data, base, n, value_names=("Dimension", "Topic")):
    """Stack the N indexed column-pairs (e.g. 'Governance Dimension 1..5') into long form,
    carrying the row id so we can cross-tabulate against other fields."""
    parts = []
    keep = [c for c in ["Participant", "Forum", "Domain Family", "Governance function"] if c in data.columns]
    for i in range(1, n + 1):
        a, b = f"{base[0]} {i}", f"{base[1]} {i}"
        if a in data.columns and b in data.columns:
            sub = data[[*keep, a, b]].copy()
            sub.columns = [*keep, value_names[0], value_names[1]]
            parts.append(sub)
    if not parts:
        return pd.DataFrame(columns=[*keep, *value_names])
    out = pd.concat(parts, ignore_index=True)
    return out.dropna(subset=[value_names[0]])


def melt_subdomains(data):
    """Stack Sub-Domain 1..3 alongside Domain Family."""
    parts = []
    keep = [c for c in ["Participant", "Forum", "Domain Family", "Governance function"] if c in data.columns]
    for i in range(1, 4):
        col = f"Sub-Domain {i}"
        if col in data.columns:
            sub = data[[*keep, col]].copy()
            sub.columns = [*keep, "Sub-Domain"]
            parts.append(sub)
    if not parts:
        return pd.DataFrame(columns=[*keep, "Sub-Domain"])
    out = pd.concat(parts, ignore_index=True)
    return out.dropna(subset=["Sub-Domain"])


def vc(series, top=None):
    """value_counts -> tidy DataFrame with named columns."""
    s = series.dropna()
    out = s.value_counts()
    if top:
        out = out.head(top)
    out = out.reset_index()
    out.columns = ["label", "count"]
    return out


def hbar(data, ycol, xcol, title, color=None, height=None):
    """Horizontal bar with biggest value on top — the format used throughout."""
    data = data.sort_values(xcol)
    h = height or max(240, 36 * len(data) + 80)
    fig = px.bar(data, x=xcol, y=ycol, orientation="h", title=title,
                 color=color, color_discrete_sequence=PALETTE)
    if color is None:
        fig.update_traces(marker_color=PRIMARY)
    fig.update_layout(height=h, yaxis_title=None, xaxis_title=None, showlegend=color is not None)
    return fig


def ai_summary(text):
    st.markdown(f"<div class='ai-box'><span class='tag'>🤖 AI Summary</span><br>{text}</div>",
                unsafe_allow_html=True)


def pct(part, whole):
    return 0 if not whole else round(part / whole * 100, 1)


df = load_data()

# --------------------------------------------------------------------------------------
# Global filters (sidebar collapses cleanly on mobile)
# --------------------------------------------------------------------------------------
st.sidebar.title("🌐 Filters")
st.sidebar.caption("Apply across every tab.")

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
if st.sidebar.button("Reset filters", width='stretch', key='chart_22'):
    st.rerun()

# --------------------------------------------------------------------------------------
# Header + shared metric row
# --------------------------------------------------------------------------------------
st.title("Trade Governance Lab")
st.caption("What WTO members are governing — measures, domains, and the way concerns are raised.")


def metric_row(data):
    cols = st.columns(6)
    metrics = [
        ("Interactions", len(data), "One member intervention on one document/topic."),
        ("WTO bodies", data["Forum"].nunique(), "Distinct WTO councils/committees involved."),
        ("Members", data["Participant"].nunique(), "Distinct members taking part."),
        ("Measures", data["Measure"].nunique(), "Named policy measures discussed."),
        ("Functions", data["Governance function"].nunique(),
         "How members engage: Concern Raised, Proposal/Recommendation, Defence/Explanation, Information Sharing."),
        ("Domain families", data["Domain Family"].nunique(), "Top-level subject areas."),
    ]
    for c, (label, value, help_text) in zip(cols, metrics):
        c.metric(label, value, help=help_text)


if filtered.empty:
    st.warning("No rows match the current filters. Use **Reset filters** in the sidebar.")
    st.stop()

# --------------------------------------------------------------------------------------
# Tabs (now on the dashboard, not the sidebar)
# --------------------------------------------------------------------------------------
tab_overview, tab_gov, tab_dom, tab_mem, tab_meas, tab_exp = st.tabs(
    ["📊 Overview", "🏛️ Governance", "🗂️ Domains", "👥 Members", "📑 Measures", "🔎 Explorer"]
)

# ======================================================================================
# OVERVIEW
# ======================================================================================
with tab_overview:
    metric_row(filtered)

    funcs = vc(filtered["Governance function"])
    dom = vc(filtered["Domain Family"])
    top_member = vc(filtered["Participant"], 1)
    real_measures = filtered[filtered["Measure"] != NO_MEASURE]
    top_measure = vc(real_measures["Measure"], 1)

    top_func = funcs.iloc[0] if not funcs.empty else None
    top_dom_row = dom.iloc[0] if not dom.empty else None
    summary = (
        f"This view covers <b>{len(filtered)} interactions</b> from "
        f"<b>{filtered['Participant'].nunique()} members</b> across "
        f"<b>{filtered['Forum'].nunique()} WTO bodies</b>. "
    )
    if top_func is not None:
        summary += (f"The dominant mode of engagement is <b>{top_func['label']}</b> "
                    f"({pct(top_func['count'], len(filtered))}% of activity). ")
    if top_dom_row is not None:
        summary += f"Discussion is concentrated in <b>{top_dom_row['label']}</b>. "
    if not top_measure.empty:
        summary += (f"The most-debated named measure is <b>{top_measure.iloc[0]['label']}</b>, "
                    f"and the most active member is <b>{top_member.iloc[0]['label']}</b>.")
    ai_summary(summary)

    c1, c2 = st.columns(2)
    # Most discussed measures — NO_MEASURE excluded (the original bug), top 10.
    m = vc(real_measures["Measure"], 10)
    c1.plotly_chart(hbar(m, "label", "count", "Most-discussed measures"), width='stretch', key='chart_1')
    # Domain family split.
    fig = px.pie(dom, values="count", names="label", title="Domain family share", hole=0.45,
                 color_discrete_sequence=PALETTE)
    fig.update_layout(height=380)
    c2.plotly_chart(fig, width='stretch', key='chart_2')

    c3, c4 = st.columns(2)
    c3.plotly_chart(hbar(funcs, "label", "count", "Governance functions (how members engage)"),
                    width='stretch', key='chart_12')
    forum = vc(filtered["Forum"])
    c4.plotly_chart(hbar(forum, "label", "count", "Activity by WTO body"), width='stretch', key='chart_3')

    # Timeline — uses the previously unused Date column.
    tl = (filtered.dropna(subset=["Month"])
          .groupby(["Month", "Governance function"]).size().reset_index(name="count"))
    if not tl.empty:
        fig = px.area(tl, x="Month", y="count", color="Governance function",
                      title="Interactions over time", color_discrete_sequence=PALETTE)
        fig.update_layout(height=340, xaxis_title=None, yaxis_title="Interactions")
        st.plotly_chart(fig, width='stretch', key='chart_4')

# ======================================================================================
# GOVERNANCE
# ======================================================================================
with tab_gov:
    gov_long = melt_pairs(filtered, ("Governance Dimension", "Governance Topic"), 5)

    dims = vc(gov_long["Dimension"])
    topics = vc(gov_long["Topic"], 12)
    top_dim = dims.iloc[0] if not dims.empty else None
    top_topic = topics.iloc[0] if not topics.empty else None
    summary = (
        f"Across these interactions, members invoked <b>{len(gov_long)} governance considerations</b> "
        f"spanning <b>{gov_long['Dimension'].nunique()} dimensions</b>. "
    )
    if top_dim is not None:
        summary += (f"The most prominent dimension is <b>{top_dim['label']}</b> "
                    f"({pct(top_dim['count'], len(gov_long))}% of all considerations). ")
    if top_topic is not None:
        summary += f"The single most-raised topic is <b>{top_topic['label']}</b>. "
    summary += ("The heatmap below shows which governance functions attach to which domains — "
                "e.g. where concerns cluster versus where proposals are made.")
    ai_summary(summary)

    c1, c2 = st.columns(2)
    c1.plotly_chart(hbar(vc(filtered["Governance function"]), "label", "count",
                         "Governance functions"), width='stretch', key='chart_23')
    c2.plotly_chart(hbar(dims, "label", "count", "Governance dimensions raised"),
                    width='stretch', key='chart_13')

    # Dimension -> Topic treemap (reshaped, so it is no longer blank).
    hier = (gov_long.groupby(["Dimension", "Topic"]).size().reset_index(name="count"))
    if not hier.empty:
        fig = px.treemap(hier, path=[px.Constant("All"), "Dimension", "Topic"], values="count",
                         color="Dimension", color_discrete_sequence=PALETTE,
                         title="Governance dimensions → topics")
        fig.update_layout(height=460, margin=dict(t=48, l=8, r=8, b=8))
        fig.update_traces(root_color="white")
        st.plotly_chart(fig, width='stretch', key='chart_5')

    c3, c4 = st.columns(2)
    heat = pd.crosstab(filtered["Governance function"], filtered["Domain Family"])
    if heat.size:
        fig = px.imshow(heat, aspect="auto", text_auto=True,
                        color_continuous_scale=["#FFFFFF", PRIMARY],
                        title="Function × domain family")
        fig.update_layout(height=380, xaxis_title=None, yaxis_title=None, coloraxis_showscale=False)
        c3.plotly_chart(fig, width='stretch', key='chart_6')

    stacked = filtered.groupby(["Forum", "Governance function"]).size().reset_index(name="count")
    fig = px.bar(stacked, x="Forum", y="count", color="Governance function",
                 title="How each body engages", color_discrete_sequence=PALETTE)
    fig.update_layout(height=380, xaxis_title=None, yaxis_title="Interactions")
    c4.plotly_chart(fig, width='stretch', key='chart_7')

# ======================================================================================
# DOMAINS
# ======================================================================================
with tab_dom:
    sub_long = melt_subdomains(filtered)
    fam = vc(filtered["Domain Family"])
    subs = vc(sub_long["Sub-Domain"], 1)
    top_fam = fam.iloc[0] if not fam.empty else None
    summary = (
        f"Discussion spans <b>{filtered['Domain Family'].nunique()} domain families</b> and "
        f"<b>{sub_long['Sub-Domain'].nunique()} sub-domains</b>. "
    )
    if top_fam is not None:
        summary += (f"<b>{top_fam['label']}</b> is the largest family "
                    f"({pct(top_fam['count'], len(filtered))}% of interactions). ")
    if not subs.empty:
        summary += f"The most discussed sub-domain overall is <b>{subs.iloc[0]['label']}</b>. "
    summary += "Use the selector to drill into a family and see its sub-domains and who is driving them."
    ai_summary(summary)

    # Family -> Sub-domain treemap so the Domain Family heads are explicit.
    hier = sub_long.groupby(["Domain Family", "Sub-Domain"]).size().reset_index(name="count")
    if not hier.empty:
        fig = px.treemap(hier, path=[px.Constant("All domains"), "Domain Family", "Sub-Domain"],
                         values="count", color="Domain Family", color_discrete_sequence=PALETTE,
                         title="Domain families → sub-domains")
        fig.update_layout(height=460, margin=dict(t=48, l=8, r=8, b=8))
        fig.update_traces(root_color="white")
        st.plotly_chart(fig, width='stretch', key='chart_8')

    st.markdown("#### Drill into a domain family")
    fam_choice = st.selectbox("Domain family", sorted(filtered["Domain Family"].dropna().unique()))
    fsub = sub_long[sub_long["Domain Family"] == fam_choice]
    frows = filtered[filtered["Domain Family"] == fam_choice]

    c1, c2 = st.columns(2)
    c1.plotly_chart(hbar(vc(fsub["Sub-Domain"], 12), "label", "count",
                         f"Sub-domains in {fam_choice}"), width='stretch', key='chart_24')
    c2.plotly_chart(hbar(vc(frows["Governance function"]), "label", "count",
                         "How it is discussed"), width='stretch', key='chart_25')

    c3, c4 = st.columns(2)
    c3.plotly_chart(hbar(vc(frows["Participant"], 10), "label", "count",
                         "Most engaged members"), width='stretch', key='chart_26')
    c4.plotly_chart(hbar(vc(frows["Forum"]), "label", "count", "Where it is discussed"),
                    width='stretch', key='chart_14')

# ======================================================================================
# MEMBERS
# ======================================================================================
with tab_mem:
    members = vc(filtered["Participant"], 15)
    summary = (
        f"<b>{filtered['Participant'].nunique()} members</b> appear in this view. "
    )
    if not members.empty:
        lead = members.iloc[0]
        summary += (f"<b>{lead['label']}</b> is the most active "
                    f"({lead['count']} interactions, {pct(lead['count'], len(filtered))}% of the total). ")
    summary += ("Pick a member below for a full profile: the domains they engage, how they engage "
                "(concern vs proposal), the governance dimensions they emphasise, and their measures.")
    ai_summary(summary)

    st.plotly_chart(hbar(members, "label", "count", "Most active members"), width='stretch', key='chart_9')

    # Member-by-domain heatmap (top members) — quick comparison across the field.
    top_names = members["label"].head(10).tolist()
    cross = pd.crosstab(
        filtered[filtered["Participant"].isin(top_names)]["Participant"],
        filtered[filtered["Participant"].isin(top_names)]["Domain Family"],
    )
    if cross.size:
        fig = px.imshow(cross, aspect="auto", text_auto=True,
                        color_continuous_scale=["#FFFFFF", PRIMARY],
                        title="Top members × domain family")
        fig.update_layout(height=420, xaxis_title=None, yaxis_title=None, coloraxis_showscale=False)
        st.plotly_chart(fig, width='stretch', key='chart_10')

    st.markdown("#### Member profile")
    member = st.selectbox("Select member", sorted(filtered["Participant"].dropna().unique()))
    mdata = filtered[filtered["Participant"] == member]
    mdims = melt_pairs(mdata, ("Governance Dimension", "Governance Topic"), 5)

    cols = st.columns(4)
    cols[0].metric("Interactions", len(mdata))
    cols[1].metric("Domains touched", mdata["Domain Family"].nunique())
    cols[2].metric("Bodies active in", mdata["Forum"].nunique())
    cols[3].metric("Measures engaged", mdata[mdata["Measure"] != NO_MEASURE]["Measure"].nunique())

    c1, c2 = st.columns(2)
    c1.plotly_chart(hbar(vc(mdata["Domain Family"]), "label", "count", "Domains engaged"),
                    width='stretch', key='chart_15')
    c2.plotly_chart(hbar(vc(mdata["Governance function"]), "label", "count", "How they engage"),
                    width='stretch', key='chart_16')

    c3, c4 = st.columns(2)
    c3.plotly_chart(hbar(vc(mdims["Dimension"]), "label", "count", "Governance dimensions emphasised"),
                    width='stretch', key='chart_17')
    c4.plotly_chart(hbar(vc(mdata["Forum"]), "label", "count", "Bodies where active"),
                    width='stretch', key='chart_18')

    real = mdata[mdata["Measure"] != NO_MEASURE]
    if not real.empty:
        st.plotly_chart(hbar(vc(real["Measure"], 10), "label", "count", "Measures engaged with"),
                        width='stretch', key='chart_19')

    with st.expander(f"Read {member}'s interaction summaries"):
        cols_show = [c for c in ["Date", "Forum", "Domain Family", "Governance function",
                                 "Measure", "Interaction_Summary"] if c in mdata.columns]
        st.dataframe(mdata[cols_show].sort_values("Date"), width='stretch', hide_index=True)

# ======================================================================================
# MEASURES
# ======================================================================================
with tab_meas:
    real_measures = filtered[filtered["Measure"] != NO_MEASURE]
    owners = vc(filtered[filtered["Measure_Owner"] != "Not applicable"]["Measure_Owner"], 12)
    mtop = vc(real_measures["Measure"], 1)
    summary = (
        f"<b>{real_measures['Measure'].nunique()} named measures</b> are under discussion "
        f"(beyond general interventions). "
    )
    if not mtop.empty:
        summary += f"The most contested is <b>{mtop.iloc[0]['label']}</b>. "
    if not owners.empty:
        summary += (f"<b>{owners.iloc[0]['label']}</b> owns the most measures under scrutiny. "
                    "Select a measure below to see who engages it and how.")
    ai_summary(summary)

    c1, c2 = st.columns(2)
    c1.plotly_chart(hbar(vc(real_measures["Measure"], 12), "label", "count",
                         "Most-discussed measures"), width='stretch', key='chart_27')
    c2.plotly_chart(hbar(owners, "label", "count", "Measure owners (under scrutiny)"),
                    width='stretch', key='chart_20')

    st.markdown("#### Drill into a measure")
    options = sorted(real_measures["Measure"].dropna().unique())
    if options:
        measure = st.selectbox("Select measure", options)
        mdata = filtered[filtered["Measure"] == measure]

        cols = st.columns(4)
        cols[0].metric("Interactions", len(mdata))
        cols[1].metric("Members engaged", mdata["Participant"].nunique())
        cols[2].metric("Bodies", mdata["Forum"].nunique())
        owner_val = mdata["Measure_Owner"].mode()
        cols[3].metric("Owner", owner_val.iloc[0] if not owner_val.empty else "—")

        c1, c2 = st.columns(2)
        c1.plotly_chart(hbar(vc(mdata["Participant"], 12), "label", "count",
                             "Who engages this measure"), width='stretch', key='chart_28')
        c2.plotly_chart(hbar(vc(mdata["Governance function"]), "label", "count",
                             "How it is engaged"), width='stretch', key='chart_29')

        c3, c4 = st.columns(2)
        c3.plotly_chart(hbar(vc(mdata["Domain Family"]), "label", "count", "Domain framing"),
                        width='stretch', key='chart_21')
        tl = mdata.dropna(subset=["Month"]).groupby("Month").size().reset_index(name="count")
        if not tl.empty:
            fig = px.bar(tl, x="Month", y="count", title="Discussion over time")
            fig.update_traces(marker_color=PRIMARY)
            fig.update_layout(height=max(240, 36 * 6), xaxis_title=None, yaxis_title="Interactions")
            c4.plotly_chart(fig, width='stretch', key='chart_11')
    else:
        st.info("No named measures in the current view — adjust the filters.")

# ======================================================================================
# EXPLORER
# ======================================================================================
with tab_exp:
    ai_summary(
        "The full filtered dataset. Search across every field, scan the records, and download "
        f"the current <b>{len(filtered)}-row</b> view as CSV for your own analysis."
    )
    search = st.text_input("Search all columns")
    table = filtered.copy()
    if search:
        mask = table.astype(str).apply(lambda s: s.str.contains(search, case=False, na=False))
        table = table[mask.any(axis=1)]
    st.caption(f"Showing {len(table)} rows.")
    st.dataframe(table, width='stretch', height=620, hide_index=True)
    st.download_button("⬇️ Download filtered data (CSV)", table.to_csv(index=False),
                       "trade_governance_lab.csv", "text/csv", width='stretch', key='chart_30')
