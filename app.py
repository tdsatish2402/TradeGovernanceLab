"""
Trade Governance Lab — WTO discussion analytics dashboard (v3).

v3 redesigns the visualisation layer while preserving the v2 data model and filters:
- Consistent colour system: governance functions / domains / WTO bodies keep the SAME colour
  everywhere (no random Plotly assignment).
- Richer charts: top-N charts are stacked and carry a total-interactions label at the bar end,
  sorted by total activity rather than alphabetically.
- "Colour by" controls on Members and Measures so one chart answers several questions.
- Redesigned Overview that reads as a dashboard (KPIs, summary, top members/measures,
  distributions, latest discussions).
- New Insights tab: deterministic, data-driven observations (no external API).
- Cross-filtering via the global sidebar filters (a Member/Domain/Function selection updates
  every chart on every tab).
- Performance: melted dimension/sub-domain tables are cached once and filtered by row id, so
  filtering stays fast as the dataset grows.
- Publication quality: wrapped labels, no clipping, mobile-responsive, larger fonts, clean
  legends below charts.

All narrative text is generated deterministically from the data in the current view.
"""

import textwrap

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

# ======================================================================================
# Config / theming
# ======================================================================================
st.set_page_config(page_title="Trade Governance Lab", page_icon="🌐", layout="wide")

SHOW_TIME_CHARTS = False          # turn on when more than one year of data exists
NO_MEASURE = "No Specific Measure"
NA_OWNER = "Not applicable"

PRIMARY = "#1F5A7A"               # deep ocean-blue: titles, headings, accents
HEADING = "#234E63"
CHART = "#5B8DA6"                 # neutral single-series bar colour
HEAT_SCALE = ["#F4F7F9", "#BBD0DC", "#7FA9C0", "#4E7E9C", "#2E5C78"]
PALETTE = ["#5B8DA6", "#E0A458", "#7FB685", "#9D8EC4", "#5BA8A0", "#C98BB9", "#8C9EC4",
           "#D4B483", "#6FA8C7", "#B5838D", "#A3B18A", "#C9ADA7", "#7C98B3"]

# --- Fixed colour maps (req 4): same category → same colour, everywhere -----------------
FUNC_COLORS = {
    "Concern Raised": "#5B8DA6",
    "Proposal/Recommendation": "#7FB685",
    "Defence/Explanation": "#9D8EC4",
    "Information Sharing": "#E0A458",
    "Question/Clarification": "#5BA8A0",   # future-proofed
}
FUNC_ORDER = list(FUNC_COLORS)

DOMAIN_COLORS = {
    "Climate & Sustainability": "#5B8DA6",
    "Industrial Policy & Economic Security": "#E0A458",
    "Digital Trade": "#7FB685",
    "National & Economic Security": "#9D8EC4",
}
DOMAIN_ORDER = list(DOMAIN_COLORS)

FORUM_NAMES = {
    "GC": "General Council",
    "CTG": "Council for Trade in Goods",
    "CTD": "Committee on Trade & Development",
    "CTE": "Committee on Trade & Environment",
    "CTF": "Committee on Trade Facilitation",
}
FORUM_COLORS = {
    "General Council": "#5B8DA6",
    "Council for Trade in Goods": "#E0A458",
    "Committee on Trade & Development": "#7FB685",
    "Committee on Trade & Environment": "#9D8EC4",
    "Committee on Trade Facilitation": "#5BA8A0",
}
FORUM_ORDER = list(FORUM_COLORS)

# Columns selectable in the "Colour by" controls.
COLOR_BY = {
    "Governance Function": "Governance function",
    "Domain Family": "Domain Family",
    "WTO Body": "Forum",
    "Measure Owner": "Measure_Owner",
}

PCONF = {"displayModeBar": False, "responsive": True}

pio.templates["tgl"] = pio.templates["plotly_white"]
pio.templates["tgl"].layout.update(
    colorway=PALETTE,
    font=dict(family="Inter, Segoe UI, system-ui, sans-serif", size=14, color="#33384a"),
    margin=dict(l=12, r=24, t=56, b=16),
    title=dict(font=dict(size=16, color="#2b2740"), x=0, xanchor="left"),
    xaxis=dict(automargin=True),
    yaxis=dict(automargin=True),
    legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5, title_text=""),
)
pio.templates.default = "tgl"

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.4rem; padding-bottom: 2rem; max-width: 1500px; }}
      h1,h2,h3,h4 {{ color: {HEADING}; }}
      .app-title {{ text-align:center; color:{PRIMARY}; font-weight:700; width:100%;
                    font-size: clamp(1.7rem, 3.6vw, 2.4rem); line-height:1.5;
                    margin: 0 0 4px 0; padding: 8px 6px 2px 6px; }}
      .app-sub {{ text-align:center; color:#6b6680; font-size: clamp(.95rem, 1.8vw, 1.08rem);
                  font-weight:400; margin: 0 auto 16px auto; max-width: 820px; padding: 0 6px; }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 4px; flex-wrap: wrap; justify-content:center; }}
      .stTabs [data-baseweb="tab"] {{ font-weight:600; padding:8px 15px; border-radius:10px 10px 0 0; }}
      .stTabs [aria-selected="true"] {{ background:{PRIMARY}12; color:{PRIMARY};
                                        border-bottom:3px solid {PRIMARY}; }}
      div[data-testid="stMetricValue"] {{ color:{PRIMARY}; font-size:1.7rem; }}
      .ai-box {{ background: linear-gradient(135deg,{PRIMARY}0D,{PRIMARY}04);
                 border:1px solid {PRIMARY}2E; border-left:5px solid {PRIMARY};
                 border-radius:12px; padding:14px 18px; margin:6px 0 18px 0;
                 font-size:.97rem; line-height:1.55; }}
      .ai-box .tag {{ display:inline-block; font-size:.7rem; font-weight:700; letter-spacing:.06em;
                      text-transform:uppercase; color:{PRIMARY}; margin-bottom:6px; }}
      .insight {{ background:#fff; border:1px solid #e6e9ee; border-radius:12px;
                  padding:14px 18px; margin:0 0 12px 0; font-size:.98rem; line-height:1.55;
                  border-left:5px solid {CHART}; }}
      .insight b {{ color:{PRIMARY}; }}
      @media (max-width: 640px) {{
          .block-container {{ padding-left:.6rem; padding-right:.6rem; }}
          div[data-testid="stMetricValue"] {{ font-size:1.3rem; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ======================================================================================
# Data (cached) + cached melted tables (perf: melt once, filter by row id)
# ======================================================================================
@st.cache_data
def load_base():
    df = pd.read_excel("WTO_Database.xlsx", sheet_name="Database")
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["rid"] = np.arange(len(df))
    return df


def get_df():
    # Forum labelling done outside the cache so name edits always take effect.
    df = load_base().copy()
    df["Forum"] = df["WTO_Forum"].map(FORUM_NAMES).fillna(df["WTO_Forum"])
    return df


KEEP = ["rid", "Participant", "Forum", "Domain Family", "Governance function", "Measure_Owner"]


@st.cache_data
def get_gov_long(forum_sig):
    df = get_df()
    parts = []
    for i in range(1, 6):
        a, b = f"Governance Dimension {i}", f"Governance Topic {i}"
        if a in df.columns and b in df.columns:
            sub = df[[*KEEP, a, b]].copy()
            sub.columns = [*KEEP, "Dimension", "Topic"]
            parts.append(sub)
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=[*KEEP, "Dimension", "Topic"])
    return out.dropna(subset=["Dimension"])


@st.cache_data
def get_sub_long(forum_sig):
    df = get_df()
    parts = []
    for i in range(1, 4):
        col = f"Sub-Domain {i}"
        if col in df.columns:
            sub = df[[*KEEP, col]].copy()
            sub.columns = [*KEEP, "Sub-Domain"]
            parts.append(sub)
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=[*KEEP, "Sub-Domain"])
    return out.dropna(subset=["Sub-Domain"])


FORUM_SIG = tuple(sorted(FORUM_NAMES.items()))
df = get_df()

# Owners get a stable colour map built once from the data (alphabetical → palette).
_owners = sorted([o for o in df["Measure_Owner"].dropna().unique() if o != NA_OWNER])
OWNER_COLORS = {o: PALETTE[i % len(PALETTE)] for i, o in enumerate(_owners)}
OWNER_COLORS[NA_OWNER] = "#D9DEE3"

COLOR_MAPS = {
    "Governance function": FUNC_COLORS,
    "Domain Family": DOMAIN_COLORS,
    "Forum": FORUM_COLORS,
    "Measure_Owner": OWNER_COLORS,
}
CAT_ORDERS = {
    "Governance function": FUNC_ORDER,
    "Domain Family": DOMAIN_ORDER,
    "Forum": FORUM_ORDER,
}

# ======================================================================================
# Helpers
# ======================================================================================
def wrap(s, width=28):
    return "<br>".join(textwrap.wrap(str(s), width)) or str(s)


def pct(part, whole):
    return 0 if not whole else round(part / whole * 100, 1)


def int_axis(fig, maxval, axis="x"):
    upd = fig.update_xaxes if axis == "x" else fig.update_yaxes
    if maxval is None or maxval <= 1:
        upd(tickformat="d", dtick=1, rangemode="tozero")
    elif maxval <= 10:
        upd(tickformat="d", dtick=1)
    else:
        upd(tickformat="d")
    return fig


def show(container, fig, key):
    container.plotly_chart(fig, width="stretch", config=PCONF, key=key)


def _empty(title):
    fig = px.bar(pd.DataFrame({"x": [], "y": []}), x="x", y="y", title=title)
    fig.update_layout(height=240, annotations=[dict(text="No data in current view",
                      x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                      font=dict(color="#8a8fa0"))])
    return fig


def count_bar(data, cat, title, top=None, colored=True, height=None):
    """Single-series horizontal bar: sorted by count, value labels, fixed colours if available."""
    if data.empty:
        return _empty(title)
    d = data[cat].value_counts()
    if top:
        d = d.head(top)
    d = d.reset_index()
    d.columns = [cat, "count"]
    d["_y"] = d[cat].map(wrap)
    d = d.sort_values("count")
    order = d["_y"].tolist()
    cmap = COLOR_MAPS.get(cat) if colored else None
    if cmap:
        fig = px.bar(d, x="count", y="_y", orientation="h", color=cat,
                     color_discrete_map=cmap, category_orders={"_y": order}, title=title)
        fig.update_layout(showlegend=False)
    else:
        fig = px.bar(d, x="count", y="_y", orientation="h",
                     category_orders={"_y": order}, title=title)
        fig.update_traces(marker_color=CHART)
    fig.update_traces(texttemplate="%{x}", textposition="outside", cliponaxis=False,
                      textfont_size=12)
    h = height or max(220, 32 * len(d) + 90)
    fig.update_layout(height=h, yaxis_title=None, xaxis_title=None)
    int_axis(fig, d["count"].max())
    fig.update_xaxes(range=[0, d["count"].max() * 1.14])
    return fig


def stacked_bar(data, cat, color_col, title, top=12, height=None):
    """Horizontal stacked bar by `color_col`, sorted by total, with a total label per bar."""
    if data.empty:
        return _empty(title)
    grp = data.groupby([cat, color_col], dropna=False).size().reset_index(name="count")
    grp[color_col] = grp[color_col].fillna("—")
    totals = grp.groupby(cat)["count"].sum().sort_values(ascending=False)
    keep = totals.head(top).index.tolist()
    grp = grp[grp[cat].isin(keep)].copy()
    label_map = {c: wrap(c) for c in keep}
    grp["_y"] = grp[cat].map(label_map)
    order_plot = [label_map[c] for c in reversed(keep)]   # largest on top
    cat_orders = {"_y": order_plot}
    if color_col in CAT_ORDERS:
        cat_orders[color_col] = CAT_ORDERS[color_col]
    fig = px.bar(grp, x="count", y="_y", color=color_col, orientation="h",
                 color_discrete_map=COLOR_MAPS.get(color_col), category_orders=cat_orders,
                 title=title)
    mx = totals.max()
    for c in keep:
        fig.add_annotation(x=totals[c], y=label_map[c], text=f"<b>{int(totals[c])}</b>",
                           showarrow=False, xanchor="left", xshift=6,
                           font=dict(size=12, color="#33384a"))
    h = height or max(240, 32 * len(keep) + 120)
    fig.update_layout(height=h, barmode="stack", yaxis_title=None, xaxis_title=None,
                      legend_title_text="", margin=dict(t=56, b=96, l=10, r=46),
                      legend=dict(orientation="h", yanchor="top", y=-0.14, x=0.5, xanchor="center"))
    int_axis(fig, mx)
    fig.update_xaxes(range=[0, mx * 1.14])
    return fig


def heatmap(matrix, title, height=380, tickangle=-18):
    fig = px.imshow(matrix, aspect="auto", text_auto=True,
                    color_continuous_scale=HEAT_SCALE, title=title)
    fig.update_layout(height=height, xaxis_title=None, yaxis_title=None, coloraxis_showscale=False)
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
    return f"<b>{data['Participant'].dropna().iloc[0]}</b>" if n == 1 else f"<b>{n} members</b>"


def bodies_phrase(data):
    n = data["Forum"].nunique()
    return f"the <b>{data['Forum'].dropna().iloc[0]}</b>" if n == 1 else f"<b>{n} WTO bodies</b>"


def color_by_control(key, options=("Governance Function", "Domain Family", "WTO Body", "Measure Owner")):
    choice = st.radio("Colour by", list(options), horizontal=True, key=key)
    return COLOR_BY[choice]


# ======================================================================================
# Filters (global → cross-filter every tab)
# ======================================================================================
st.sidebar.title("🌐 Filters")
st.sidebar.caption("These cross-filter every chart on every tab. Leave empty to include all.")

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

# Filter the cached melted tables by row id (fast even on large data).
_ids = set(filtered["rid"])
gov_long = get_gov_long(FORUM_SIG)
gov_f = gov_long[gov_long["rid"].isin(_ids)]
sub_long = get_sub_long(FORUM_SIG)
sub_f = sub_long[sub_long["rid"].isin(_ids)]

# ======================================================================================
# Header
# ======================================================================================
st.markdown("<div class='app-title'>Trade Governance Lab</div>", unsafe_allow_html=True)
st.markdown("<div class='app-sub'>How WTO members engage with trade-policy topics across "
            "different WTO bodies.</div>", unsafe_allow_html=True)

if filtered.empty:
    st.warning("No rows match the current filters. Use **Reset filters** in the sidebar.")
    st.stop()

tabs = st.tabs(["📊 Overview", "🏛️ Governance", "🗂️ Domains", "👥 Members",
                "📑 Measures", "💡 Insights", "🔎 Explorer"])
(tab_overview, tab_gov, tab_dom, tab_mem, tab_meas, tab_ins, tab_exp) = tabs

# ======================================================================================
# OVERVIEW (dashboard layout)
# ======================================================================================
with tab_overview:
    metric_strip(filtered)

    funcs = filtered["Governance function"].value_counts()
    dom = filtered["Domain Family"].value_counts()
    real_measures = filtered[filtered["Measure"] != NO_MEASURE]
    top_measure = real_measures["Measure"].value_counts()
    top_member = filtered["Participant"].value_counts()

    summary = (f"This view covers <b>{len(filtered)} interactions</b> from "
               f"{members_phrase(filtered)} across {bodies_phrase(filtered)}. ")
    if len(funcs):
        summary += (f"The dominant mode of engagement is <b>{funcs.index[0]}</b> "
                    f"({pct(funcs.iloc[0], len(filtered))}% of activity). ")
    if len(dom):
        summary += f"Discussion is concentrated in <b>{dom.index[0]}</b>. "
    if len(top_measure):
        summary += f"The most-debated named measure is <b>{top_measure.index[0]}</b>"
        if filtered["Participant"].nunique() > 1 and len(top_member):
            summary += f", and the most active member is <b>{top_member.index[0]}</b>"
        summary += "."
    ai_summary(summary)

    c1, c2 = st.columns(2)
    show(c1, stacked_bar(filtered, "Participant", "Governance function",
                         "Top members (by interactions)", top=10), "ov_members")
    show(c2, stacked_bar(real_measures, "Measure", "Governance function",
                         "Top measures (by interactions)", top=10), "ov_measures")

    c3, c4 = st.columns(2)
    pie = px.pie(dom.reset_index().set_axis(["label", "count"], axis=1),
                 values="count", names="label", title="Domain family share", hole=0.5,
                 color="label", color_discrete_map=DOMAIN_COLORS)
    pie.update_traces(textposition="inside", texttemplate="%{percent:.0%}",
                      insidetextorientation="horizontal", sort=False)
    pie.update_layout(height=440, margin=dict(t=50, b=110, l=20, r=20),
                      uniformtext_minsize=11, uniformtext_mode="hide",
                      legend=dict(orientation="h", yanchor="top", y=-0.08, x=0.5, xanchor="center"))
    show(c3, pie, "ov_domain")
    show(c4, count_bar(filtered, "Governance function", "How members engage"), "ov_funcs")

    st.markdown("#### Latest discussions")
    latest = filtered.sort_values("Date", ascending=False).head(12)
    cols_show = [c for c in ["Date", "Participant", "Forum", "Domain Family",
                             "Governance function", "Measure", "Interaction_Summary"]
                 if c in latest.columns]
    st.dataframe(
        latest[cols_show], width="stretch", hide_index=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", width="small"),
            "Interaction_Summary": st.column_config.TextColumn("Summary", width="large"),
        },
    )

# ======================================================================================
# GOVERNANCE
# ======================================================================================
with tab_gov:
    dims = gov_f["Dimension"].value_counts()
    topics = gov_f["Topic"].value_counts()
    summary = (f"Members invoked <b>{len(gov_f)} governance considerations</b> across "
               f"<b>{gov_f['Dimension'].nunique()} dimensions</b>. ")
    if len(dims):
        summary += (f"The most prominent dimension is <b>{dims.index[0]}</b> "
                    f"({pct(dims.iloc[0], max(len(gov_f), 1))}% of considerations). ")
    if len(topics):
        summary += f"The single most-raised topic is <b>{topics.index[0]}</b>. "
    summary += "The heatmap shows how each governance function maps onto each domain family."
    ai_summary(summary)

    c1, c2 = st.columns(2)
    show(c1, count_bar(filtered, "Governance function", "Governance functions"), "gov_func")
    show(c2, count_bar(gov_f, "Dimension", "Governance dimensions raised", colored=False), "gov_dims")

    show(tab_gov, stacked_bar(gov_f, "Topic", "Dimension",
                              "Governance topics (by dimension)", top=14), "gov_topics")

    c3, c4 = st.columns(2)
    heat = pd.crosstab(filtered["Domain Family"], filtered["Governance function"])
    if heat.size:
        show(c3, heatmap(heat, "Domain family × governance function"), "gov_heat")
    show(c4, stacked_bar(filtered, "Forum", "Governance function",
                         "How each body engages", top=8), "gov_bodyengage")

# ======================================================================================
# DOMAINS
# ======================================================================================
with tab_dom:
    fam = filtered["Domain Family"].value_counts()
    subs = sub_f["Sub-Domain"].value_counts()
    summary = (f"Discussion spans <b>{filtered['Domain Family'].nunique()} domain families</b> and "
               f"<b>{sub_f['Sub-Domain'].nunique()} sub-domains</b>. ")
    if len(fam):
        summary += (f"<b>{fam.index[0]}</b> is the largest family "
                    f"({pct(fam.iloc[0], len(filtered))}% of interactions). ")
    if len(subs):
        summary += f"The most discussed sub-domain is <b>{subs.index[0]}</b>. "
    summary += "Use the focus filter to narrow to one or more families."
    ai_summary(summary)

    c1, c2 = st.columns(2)
    show(c1, stacked_bar(filtered, "Domain Family", "Governance function",
                         "Domain families (by interactions)", top=8), "dom_fam")
    show(c2, stacked_bar(sub_f, "Sub-Domain", "Domain Family",
                         "Sub-domains (by domain family)", top=14), "dom_sub")

    st.markdown("#### Focus on domain families")
    fam_opts = sorted(filtered["Domain Family"].dropna().unique())
    fam_sel = st.multiselect("Domain families (leave empty for all)", fam_opts, key="dom_sel")
    frows = filtered if not fam_sel else filtered[filtered["Domain Family"].isin(fam_sel)]
    fsub = sub_f if not fam_sel else sub_f[sub_f["Domain Family"].isin(fam_sel)]
    scope = "all families" if not fam_sel else (fam_sel[0] if len(fam_sel) == 1 else f"{len(fam_sel)} families")

    c3, c4 = st.columns(2)
    show(c3, count_bar(fsub, "Sub-Domain", f"Sub-domains · {scope}", top=12, colored=False), "dom_subs2")
    show(c4, count_bar(frows, "Participant", "Most engaged members", top=10, colored=False), "dom_members")

# ======================================================================================
# MEMBERS
# ======================================================================================
with tab_mem:
    members = filtered["Participant"].value_counts()
    summary = f"{members_phrase(filtered)} appear in this view. "
    if filtered["Participant"].nunique() > 1 and len(members):
        summary += (f"<b>{members.index[0]}</b> is the most active "
                    f"({members.iloc[0]} interactions, {pct(members.iloc[0], len(filtered))}% of the total). ")
    summary += "Use the colour control to recolour the chart, or the focus filter for a profile."
    ai_summary(summary)

    color_col = color_by_control("mem_colorby")
    show(tab_mem, stacked_bar(filtered, "Participant", color_col,
                              "Most active members", top=15), "mem_active")

    top_names = members.head(10).index.tolist()
    sub = filtered[filtered["Participant"].isin(top_names)]
    cross = pd.crosstab(sub["Domain Family"], sub["Participant"])
    if cross.size and cross.shape[1] > 1:
        show(tab_mem, heatmap(cross, "Domain family × member (top members)", height=360, tickangle=-30),
             "mem_heat")

    st.markdown("#### Member profile")
    mem_opts = sorted(filtered["Participant"].dropna().unique())
    mem_sel = st.multiselect("Members (leave empty for all)", mem_opts, key="mem_sel")
    mdata = filtered if not mem_sel else filtered[filtered["Participant"].isin(mem_sel)]
    mdims = gov_f[gov_f["rid"].isin(set(mdata["rid"]))]

    metric_strip(mdata)
    c1, c2 = st.columns(2)
    show(c1, count_bar(mdata, "Domain Family", "Domains engaged"), "mem_dom")
    show(c2, count_bar(mdata, "Governance function", "How they engage"), "mem_func")
    c3, c4 = st.columns(2)
    show(c3, count_bar(mdims, "Dimension", "Governance dimensions emphasised", colored=False), "mem_dims")
    show(c4, count_bar(mdata, "Forum", "Bodies where active"), "mem_forum")

    real = mdata[mdata["Measure"] != NO_MEASURE]
    if not real.empty:
        show(tab_mem, count_bar(real, "Measure", "Measures engaged with", top=10, colored=False), "mem_meas")

    with st.expander("Read the underlying interaction summaries"):
        cs = [c for c in ["Date", "Participant", "Forum", "Domain Family",
                          "Governance function", "Measure", "Interaction_Summary"] if c in mdata.columns]
        st.dataframe(mdata[cs].sort_values("Date"), width="stretch", hide_index=True,
                     column_config={"Interaction_Summary": st.column_config.TextColumn("Summary", width="large")})

# ======================================================================================
# MEASURES
# ======================================================================================
with tab_meas:
    real_measures = filtered[filtered["Measure"] != NO_MEASURE]
    owners = filtered[filtered["Measure_Owner"] != NA_OWNER]["Measure_Owner"].value_counts()
    mtop = real_measures["Measure"].value_counts()
    summary = f"<b>{real_measures['Measure'].nunique()} named measures</b> are under discussion. "
    if len(mtop):
        summary += f"The most contested is <b>{mtop.index[0]}</b>. "
    if len(owners):
        summary += (f"<b>{owners.index[0]}</b> owns the most measures under scrutiny. "
                    "Use the colour control or focus filter to dig in.")
    ai_summary(summary)

    color_col = color_by_control("meas_colorby")
    show(tab_meas, stacked_bar(real_measures, "Measure", color_col,
                               "Most-discussed measures", top=14), "meas_top")

    c1, c2 = st.columns(2)
    show(c1, count_bar(filtered[filtered["Measure_Owner"] != NA_OWNER], "Measure_Owner",
                       "Measure owners (under scrutiny)", top=12, colored=False), "meas_owners")
    show(c2, count_bar(real_measures, "Forum", "Where measures are discussed"), "meas_forum")

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
        c3, c4 = st.columns(2)
        show(c3, count_bar(mdata, "Participant", "Who engages these measures", top=12, colored=False), "meas_who")
        show(c4, count_bar(mdata, "Governance function", "How they are engaged"), "meas_how")
    else:
        st.info("No named measures in the current view — adjust the filters.")

# ======================================================================================
# INSIGHTS (deterministic, data-driven)
# ======================================================================================
def generate_insights(data, gdata):
    out = []
    n = len(data)
    if n == 0:
        return ["No data in the current view."]

    funcs = data["Governance function"].value_counts()
    doms = data["Domain Family"].value_counts()
    forums = data["Forum"].value_counts()
    members = data["Participant"].value_counts()

    # 1) Lead member profile
    if len(members):
        m = members.index[0]
        md = data[data["Participant"] == m]
        f = md["Governance function"].value_counts()
        d = md["Domain Family"].value_counts()
        b = md["Forum"].value_counts()
        out.append(
            f"<b>{m}</b> accounts for <b>{pct(members.iloc[0], n)}%</b> of all interactions "
            f"({members.iloc[0]} of {n}). Most of its participation concerns "
            f"<b>{f.index[0]}</b> in <b>{d.index[0]}</b> discussions"
            + (f" within the <b>{b.index[0]}</b>." if len(b) else "."))

    # 2) Dominant vs least-used engagement mode
    if len(funcs) >= 2:
        out.append(
            f"Engagement is led by <b>{funcs.index[0]}</b> ({pct(funcs.iloc[0], n)}%), "
            f"while <b>{funcs.index[-1]}</b> is the least common ({pct(funcs.iloc[-1], n)}%). "
            "This suggests members are more inclined to "
            + ("flag problems than to table proposals."
               if funcs.index[0] == "Concern Raised" else "engage in this mode than others."))

    # 3) Most contested domain (highest Concern-Raised share)
    if len(doms):
        rows = []
        for dom in doms.index:
            dd = data[data["Domain Family"] == dom]
            share = pct((dd["Governance function"] == "Concern Raised").sum(), len(dd))
            rows.append((dom, share, len(dd)))
        rows.sort(key=lambda r: r[1], reverse=True)
        dom, share, cnt = rows[0]
        out.append(f"<b>{dom}</b> is the most contested area — <b>{share}%</b> of its "
                   f"{cnt} interactions are concerns rather than proposals or information-sharing.")

    # 4) Most proposal-oriented body
    if len(forums):
        rows = []
        for fo in forums.index:
            fd = data[data["Forum"] == fo]
            share = pct((fd["Governance function"] == "Proposal/Recommendation").sum(), len(fd))
            rows.append((fo, share, len(fd)))
        rows.sort(key=lambda r: r[1], reverse=True)
        fo, share, cnt = rows[0]
        if share > 0:
            out.append(f"The <b>{fo}</b> is the most proposal-oriented forum: "
                       f"<b>{share}%</b> of its activity is proposals or recommendations.")

    # 5) Similar governance profiles among active members
    top_m = members.head(8).index.tolist()
    if len(top_m) >= 2:
        mat = pd.crosstab(data[data["Participant"].isin(top_m)]["Participant"],
                          data["Governance function"])
        norm = mat.div(mat.sum(axis=1), axis=0).fillna(0)
        names = norm.index.tolist()
        best = None
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = norm.iloc[i].values, norm.iloc[j].values
                denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
                cos = float(a @ b / denom)
                if best is None or cos > best[0]:
                    best = (cos, names[i], names[j])
        if best and best[0] > 0.85:
            a, b = best[1], best[2]
            da = data[data["Participant"] == a]["Governance function"].value_counts()
            out.append(f"<b>{a}</b> and <b>{b}</b> exhibit similar governance profiles, "
                       f"both concentrating on <b>{da.index[0]}</b>.")

    # 6) Governance dimension headline
    if len(gdata):
        gd = gdata["Dimension"].value_counts()
        gt = gdata["Topic"].value_counts()
        out.append(f"Across governance considerations, the <b>{gd.index[0]}</b> dimension dominates, "
                   f"with <b>{gt.index[0]}</b> the single most-raised topic.")
    return out


with tab_ins:
    st.markdown("#### Automatically generated observations")
    st.caption("Generated deterministically from the data in the current view — no external AI. "
               "Adjust the sidebar filters to regenerate.")
    for text in generate_insights(filtered, gov_f):
        st.markdown(f"<div class='insight'>{text}</div>", unsafe_allow_html=True)

# ======================================================================================
# EXPLORER
# ======================================================================================
with tab_exp:
    ai_summary("The full filtered dataset. Search across every field, sort by any column "
               f"(click a header), and download the current <b>{len(filtered)}-row</b> view.")
    search = st.text_input("Search all columns")
    table = filtered.drop(columns=["rid", "Month"], errors="ignore").copy()
    if search:
        mask = table.astype(str).apply(lambda s: s.str.contains(search, case=False, na=False))
        table = table[mask.any(axis=1)]
    st.caption(f"Showing {len(table)} rows. Click a column header to sort; click a cell to expand long text.")
    st.dataframe(table, width="stretch", height=560, hide_index=True,
                 column_config={"Interaction_Summary": st.column_config.TextColumn("Summary", width="large")})
    st.download_button("⬇️ Download filtered data (CSV)", table.to_csv(index=False),
                       "trade_governance_lab.csv", "text/csv", width="stretch", key="dl_btn")

    with st.expander("Read interaction summaries (current view)"):
        for _, row in table.head(60).iterrows():
            who = row.get("Participant", "")
            summ = row.get("Interaction_Summary", "")
            if str(summ).strip():
                st.markdown(f"**{who}** — {summ}")
        if len(table) > 60:
            st.caption(f"Showing the first 60 of {len(table)} — refine filters or search to see specific records.")
