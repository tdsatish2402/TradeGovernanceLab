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
    "GC": "General Council",
    "CTG": "Council for Trade in Goods",
    "CTD": "Committee on Trade & Development",
    "CTE": "Committee on Trade & Environment",
    "CTF": "Committee on Trade Facilitation",
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


df = load_data()

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

if filtered.empty:
    st.warning("No rows match the current filters. Use **Reset filters** in the sidebar.")
    st.stop()

tab_overview, tab_gov, tab_dom, tab_mem, tab_meas, tab_exp = st.tabs(
    ["📊 Overview", "🏛️ Governance", "🗂️ Domains", "👥 Members", "📑 Measures", "🔎 Explorer"]
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

    c1, c2 = st.columns(2)
    show(c1, hbar(vc(real_measures["Measure"], 10), "Most-discussed measures"), "ov_measures")
    pie = px.pie(dom, values="count", names="label", title="Domain family share", hole=0.5,
                 color_discrete_sequence=PALETTE)
    pie.update_traces(textposition="inside", texttemplate="%{percent:.0%}",
                      insidetextorientation="horizontal", sort=False)
    pie.update_layout(height=440, margin=dict(t=50, b=110, l=20, r=20),
                      uniformtext_minsize=11, uniformtext_mode="hide",
                      legend=dict(orientation="h", yanchor="top", y=-0.08, x=0.5,
                                  xanchor="center", font=dict(size=12)))
    show(c2, pie, "ov_domain")

    c3, c4 = st.columns(2)
    show(c3, hbar(funcs, "How members engage (governance functions)"), "ov_funcs")
    show(c4, hbar(vc(filtered["Forum"]), "Activity by WTO body"), "ov_forum")

    if SHOW_TIME_CHARTS:
        tl = (filtered.dropna(subset=["Month"])
              .groupby(["Month", "Governance function"]).size().reset_index(name="count"))
        if not tl.empty:
            fig = px.area(tl, x="Month", y="count", color="Governance function",
                          title="Interactions over time", color_discrete_sequence=PALETTE)
            fig.update_layout(height=340, xaxis_title=None, yaxis_title="Interactions")
            show(st, fig, "ov_time")

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

    c3, c4 = st.columns(2)
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
    show(c4, fig, "gov_bodyengage")

# ======================================================================================
# DOMAINS
# ======================================================================================
with tab_dom:
    sub_long_all = melt_subdomains(filtered)
    fam = vc(filtered["Domain Family"])
    subs = vc(sub_long_all["Sub-Domain"], 1)

    summary = (f"Discussion spans <b>{filtered['Domain Family'].nunique()} domain families</b> and "
               f"<b>{sub_long_all['Sub-Domain'].nunique()} sub-domains</b>. ")
    if not fam.empty:
        summary += (f"<b>{fam.iloc[0]['label']}</b> is the largest family "
                    f"({pct(fam.iloc[0]['count'], len(filtered))}% of interactions). ")
    if not subs.empty:
        summary += f"The most discussed sub-domain is <b>{subs.iloc[0]['label']}</b>. "
    summary += "Use the focus filter to narrow to one or more families."
    ai_summary(summary)

    # Cleaner than a treemap: sub-domains as bars, coloured by their family.
    sub_fam = sub_long_all.groupby(["Domain Family", "Sub-Domain"]).size().reset_index(name="count")
    if not sub_fam.empty:
        show(st, grouped_hbar(sub_fam, "Sub-Domain", "Domain Family",
                              "Sub-domains (coloured by domain family)", top=16), "dom_subfam")

    st.markdown("#### Focus on domain families")
    fam_opts = sorted(filtered["Domain Family"].dropna().unique())
    fam_sel = st.multiselect("Domain families (leave empty for all)", fam_opts, key="dom_sel")
    frows = filtered if not fam_sel else filtered[filtered["Domain Family"].isin(fam_sel)]
    fsub = sub_long_all if not fam_sel else sub_long_all[sub_long_all["Domain Family"].isin(fam_sel)]
    scope = "all families" if not fam_sel else (fam_sel[0] if len(fam_sel) == 1 else f"{len(fam_sel)} families")

    c1, c2 = st.columns(2)
    show(c1, hbar(vc(fsub["Sub-Domain"], 12), f"Sub-domains · {scope}"), "dom_subs")
    show(c2, hbar(vc(frows["Governance function"]), "How it is discussed"), "dom_func")

    c3, c4 = st.columns(2)
    show(c3, hbar(vc(frows["Participant"], 10), "Most engaged members"), "dom_members")
    show(c4, hbar(vc(frows["Forum"]), "Where it is discussed"), "dom_forum")

# ======================================================================================
# MEMBERS
# ======================================================================================
with tab_mem:
    members = vc(filtered["Participant"], 15)
    summary = f"{members_phrase(filtered)} appear in this view. "
    if filtered["Participant"].nunique() > 1 and not members.empty:
        lead = members.iloc[0]
        summary += (f"<b>{lead['label']}</b> is the most active "
                    f"({lead['count']} interactions, {pct(lead['count'], len(filtered))}% of the total). ")
    summary += ("Use the focus filter for a profile: the domains members engage, how they engage, "
                "the governance dimensions they emphasise, and their measures.")
    ai_summary(summary)

    show(st, hbar(members, "Most active members"), "mem_active")

    top_names = members["label"].head(10).tolist()
    sub = filtered[filtered["Participant"].isin(top_names)]
    cross = pd.crosstab(sub["Domain Family"], sub["Participant"])
    if cross.size and cross.shape[1] > 1:
        show(st, heatmap(cross, "Domain family × member (top members)", height=360, tickangle=-30),
             "mem_heat")

    st.markdown("#### Member profile")
    mem_opts = sorted(filtered["Participant"].dropna().unique())
    mem_sel = st.multiselect("Members (leave empty for all)", mem_opts, key="mem_sel")
    mdata = filtered if not mem_sel else filtered[filtered["Participant"].isin(mem_sel)]
    mdims = melt_pairs(mdata, ("Governance Dimension", "Governance Topic"), 5)

    metric_strip(mdata)

    c1, c2 = st.columns(2)
    show(c1, hbar(vc(mdata["Domain Family"]), "Domains engaged"), "mem_dom")
    show(c2, hbar(vc(mdata["Governance function"]), "How they engage"), "mem_func")

    c3, c4 = st.columns(2)
    show(c3, hbar(vc(mdims["Dimension"]), "Governance dimensions emphasised"), "mem_dims")
    show(c4, hbar(vc(mdata["Forum"]), "Bodies where active"), "mem_forum")

    real = mdata[mdata["Measure"] != NO_MEASURE]
    if not real.empty:
        show(st, hbar(vc(real["Measure"], 10), "Measures engaged with"), "mem_meas")

    with st.expander("Read the underlying interaction summaries"):
        cols_show = [c for c in ["Date", "Participant", "Forum", "Domain Family",
                                 "Governance function", "Measure", "Interaction_Summary"]
                     if c in mdata.columns]
        st.dataframe(mdata[cols_show].sort_values("Date"), width="stretch", hide_index=True)

# ======================================================================================
# MEASURES
# ======================================================================================
with tab_meas:
    real_measures = filtered[filtered["Measure"] != NO_MEASURE]
    owners = vc(filtered[filtered["Measure_Owner"] != "Not applicable"]["Measure_Owner"], 12)
    mtop = vc(real_measures["Measure"], 1)

    summary = f"<b>{real_measures['Measure'].nunique()} named measures</b> are under discussion. "
    if not mtop.empty:
        summary += f"The most contested is <b>{mtop.iloc[0]['label']}</b>. "
    if not owners.empty:
        summary += (f"<b>{owners.iloc[0]['label']}</b> owns the most measures under scrutiny. "
                    "Use the focus filter to study specific measures.")
    ai_summary(summary)

    c1, c2 = st.columns(2)
    show(c1, hbar(vc(real_measures["Measure"], 12), "Most-discussed measures"), "meas_top")
    show(c2, hbar(owners, "Measure owners (under scrutiny)"), "meas_owners")

    st.markdown("#### Focus on measures")
    opts = sorted(real_measures["Measure"].dropna().unique())
    if opts:
        sel = st.multiselect("Measures (leave empty for all)", opts, key="meas_sel")
        mdata = real_measures if not sel else filtered[filtered["Measure"].isin(sel)]

        owner_val = mdata["Measure_Owner"].mode()
        cstats = st.columns(4)
        cstats[0].metric("Interactions", len(mdata))
        cstats[1].metric("Members engaged", mdata["Participant"].nunique())
        cstats[2].metric("Bodies", mdata["Forum"].nunique())
        cstats[3].metric("Top owner", owner_val.iloc[0] if not owner_val.empty else "—")

        c1, c2 = st.columns(2)
        show(c1, hbar(vc(mdata["Participant"], 12), "Who engages these measures"), "meas_who")
        show(c2, hbar(vc(mdata["Governance function"]), "How they are engaged"), "meas_how")

        c3, c4 = st.columns(2)
        show(c3, hbar(vc(mdata["Domain Family"]), "Domain framing"), "meas_dom")
        show(c4, hbar(vc(mdata["Forum"]), "Where they are discussed"), "meas_forum")
    else:
        st.info("No named measures in the current view — adjust the filters.")

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
