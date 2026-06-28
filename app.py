
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Trade Governance Lab", layout="wide")
PLOTLY_CONFIG={"displayModeBar":False,"scrollZoom":False,"doubleClick":False,"showAxisDragHandles":False,"responsive":True}

st.markdown("""
<style>
.block-container{max-width:1450px;padding-top:1rem;}
h1,h2,h3{color:#9A05A9}
[data-testid="metric-container"]{background:white;border-left:6px solid #9A05A9;padding:14px;border-radius:12px;}
</style>
""",unsafe_allow_html=True)

@st.cache_data
def load_data():
    df=pd.read_excel("WTO_Database.xlsx")
    return df.loc[:,~df.columns.astype(str).str.contains("^Unnamed")]

try:
    df=load_data()
except Exception:
    st.error("Place WTO_Database.xlsx beside app.py"); st.stop()

def first(opts):
    for c in opts:
        if c in df.columns: return c
    return None

forum=first(["WTO Forum","WTO_Forum"])
participant=first(["Participant"])
measure=first(["Measure"])
function=first(["Governance Function","Engagement_Function"])
owner=first(["Measure Owner","Measure_Owner"])

st.markdown("<h1 style='text-align:center'>Trade Governance Lab</h1><h4 style='text-align:center;color:gray'>Evidence and Analytics on Governance in the World Trade Organization</h4>",unsafe_allow_html=True)

filtered=df.copy()
st.sidebar.header("Filters")
for label,col in [("WTO Body",forum),("Participant",participant),("Measure",measure),("Measure Owner",owner),("Governance Function",function)]:
    if col:
        vals=sorted(filtered[col].dropna().astype(str).unique())
        sel=st.sidebar.multiselect(label,vals)
        if sel:
            filtered=filtered[filtered[col].astype(str).isin(sel)]

search=st.sidebar.text_input("Search")
if search:
    mask=filtered.astype(str).apply(lambda s:s.str.contains(search,case=False,na=False))
    filtered=filtered[mask.any(axis=1)]

cols=st.columns(6)
items=[("Interactions",len(filtered)),
("Bodies",filtered[forum].nunique() if forum else "-"),
("Participants",filtered[participant].nunique() if participant else "-"),
("Measures",filtered[measure].nunique() if measure else "-"),
("Owners",filtered[owner].nunique() if owner else "-"),
("Functions",filtered[function].nunique() if function else "-")]
for c,(t,v) in zip(cols,items): c.metric(t,v)

tabs=st.tabs(["Overview","Governance","Domains","Members","Explorer"])
with tabs[0]:
    if measure:
        fig=px.bar(filtered[measure].value_counts().head(15).sort_values(),orientation="h",title="Most Discussed Measures")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=PLOTLY_CONFIG)
with tabs[1]:
    if function:
        vc=filtered[function].value_counts().reset_index(); vc.columns=["Function","Count"]
        fig=px.bar(vc,x="Count",y="Function",orientation="h",title="Governance Functions")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=PLOTLY_CONFIG)
with tabs[2]:
    dcols=[c for c in filtered.columns if "Domain" in c]
    if dcols:
        vals=pd.concat([filtered[c].dropna().rename("Domain") for c in dcols])
        vc=vals.value_counts().reset_index(); vc.columns=["Domain","Count"]
        fig=px.treemap(vc,path=["Domain"],values="Count",title="Policy Domains")
        st.plotly_chart(fig,use_container_width=True,config=PLOTLY_CONFIG)
with tabs[3]:
    if participant:
        fig=px.bar(filtered[participant].value_counts().head(20).sort_values(),orientation="h",title="Most Active Participants")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig,use_container_width=True,config=PLOTLY_CONFIG)
with tabs[4]:
    st.dataframe(filtered,use_container_width=True)
    st.download_button("Download CSV",filtered.to_csv(index=False),"trade_governance_lab.csv","text/csv")
