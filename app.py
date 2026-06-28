import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Trade Governance Lab", page_icon="🌐", layout="wide")

PRIMARY = "#9A05A9"

@st.cache_data
def load_data():
    df = pd.read_excel("WTO_Database.xlsx", sheet_name="Database")
    df.columns = df.columns.str.strip()
    return df

df = load_data()

st.sidebar.title("Trade Governance Lab")

body_filter = st.sidebar.multiselect("WTO Body", sorted(df["WTO_Forum"].dropna().unique()))
member_filter = st.sidebar.multiselect("Member", sorted(df["Participant"].dropna().unique()))
domain_filter = st.sidebar.multiselect("Domain Family", sorted(df["Domain Family"].dropna().unique()))

filtered = df.copy()
if body_filter:
    filtered = filtered[filtered["WTO_Forum"].isin(body_filter)]
if member_filter:
    filtered = filtered[filtered["Participant"].isin(member_filter)]
if domain_filter:
    filtered = filtered[filtered["Domain Family"].isin(domain_filter)]

page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Governance", "Domains", "Members", "Measures", "Explorer"],
)

def metric_row(data):
    cols = st.columns(6)
    metrics = [
        ("Governance interactions", len(data)),
        ("WTO bodies", data["WTO_Forum"].nunique()),
        ("Members", data["Participant"].nunique()),
        ("Measures", data["Measure"].nunique()),
        ("Governance functions", data["Governance function"].nunique()),
        ("Domain families", data["Domain Family"].nunique()),
    ]
    for c, (label, value) in zip(cols, metrics):
        c.metric(label, value)

if page == "Overview":
    st.title("Trade Governance Lab")
    st.caption("Understanding what is being governed in WTO discussions.")
    metric_row(filtered)

    c1, c2 = st.columns(2)

    measures = (
        filtered[filtered["Measure"] != "No specific measure"]["Measure"]
        .value_counts()
        .head(10)
        .reset_index()
    )
    measures.columns = ["Measure", "Count"]
    c1.plotly_chart(px.bar(measures, x="Count", y="Measure", orientation="h"), use_container_width=True)

    owners = filtered["Measure_Owner"].value_counts().head(10).reset_index()
    owners.columns = ["Owner", "Count"]
    c2.plotly_chart(px.bar(owners, x="Count", y="Owner", orientation="h"), use_container_width=True)

    c1, c2 = st.columns(2)

    funcs = filtered["Governance function"].value_counts().reset_index()
    funcs.columns = ["Function", "Count"]
    c1.plotly_chart(px.bar(funcs, x="Count", y="Function", orientation="h"), use_container_width=True)

    dom = filtered["Domain Family"].value_counts().reset_index()
    dom.columns = ["Domain", "Count"]
    c2.plotly_chart(px.pie(dom, values="Count", names="Domain"), use_container_width=True)

    if not funcs.empty:
        top = funcs.iloc[0]
        pct = round(top["Count"] / len(filtered) * 100, 1)
        st.success(f"Insight: Most governance activity concerns **{top['Function']}**, representing **{pct}%** of all interactions.")

elif page == "Governance":
    st.title("Governance")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.histogram(filtered, y="Governance function"), use_container_width=True)

    hierarchy = filtered.groupby(["Governance Dimension 1", "Governance Topic 1"]).size().reset_index(name="Count")
    c2.plotly_chart(px.treemap(hierarchy, path=["Governance Dimension 1", "Governance Topic 1"], values="Count"), use_container_width=True)

    heat = pd.crosstab(filtered["Governance function"], filtered["Domain Family"])
    st.plotly_chart(px.imshow(heat, aspect="auto", text_auto=True), use_container_width=True)
    st.plotly_chart(px.histogram(filtered, x="WTO_Forum", color="Governance function"), use_container_width=True)

elif page == "Domains":
    st.title("Domains")
    st.plotly_chart(px.treemap(filtered, path=["Domain Family", "Sub-Domain 1"]), use_container_width=True)

    fam = st.selectbox("Choose Domain Family", sorted(filtered["Domain Family"].dropna().unique()))
    subset = filtered[filtered["Domain Family"] == fam]
    c1, c2 = st.columns(2)

    issues = subset["Sub-Domain 1"].value_counts().reset_index()
    issues.columns = ["Issue", "Count"]
    c1.plotly_chart(px.bar(issues, x="Count", y="Issue", orientation="h"), use_container_width=True)

    gf = subset["Governance function"].value_counts().reset_index()
    gf.columns = ["Function", "Count"]
    c2.plotly_chart(px.bar(gf, x="Count", y="Function", orientation="h"), use_container_width=True)

elif page == "Members":
    st.title("Member Profile")
    member = st.selectbox("Select Member", sorted(filtered["Participant"].dropna().unique()))
    data = filtered[filtered["Participant"] == member]
    metric_row(data)
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.histogram(data, y="Measure"), use_container_width=True)
    c2.plotly_chart(px.histogram(data, y="Domain Family"), use_container_width=True)
    st.plotly_chart(px.histogram(data, x="WTO_Forum", color="Governance function"), use_container_width=True)

elif page == "Measures":
    st.title("Measure Profile")
    measure = st.selectbox("Select Measure", sorted(filtered["Measure"].dropna().unique()))
    data = filtered[filtered["Measure"] == measure]
    metric_row(data)
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.histogram(data, y="Participant"), use_container_width=True)
    c2.plotly_chart(px.histogram(data, y="Governance function"), use_container_width=True)
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.histogram(data, y="Domain Family"), use_container_width=True)
    c2.plotly_chart(px.histogram(data, y="WTO_Forum"), use_container_width=True)

else:
    st.title("Explorer")
    search = st.text_input("Search")
    table = filtered.copy()
    if search:
        mask = table.astype(str).apply(lambda s: s.str.contains(search, case=False, na=False))
        table = table[mask.any(axis=1)]
    st.dataframe(table, use_container_width=True, height=650)
    st.download_button("Download filtered data", table.to_csv(index=False), "trade_governance_lab.csv", "text/csv")
