from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from live_data import fetch_oriel_marks
from risk_graph import build_risk_graph, event_table, neighborhood, layered_layout
from vault_engine import SAMPLE_PORTFOLIO, RISK_FAMILY_HEALTHCARE_BETA, correlation_matrix_frame

st.set_page_config(page_title="CareFi · Risk Graph",page_icon="◈",layout="wide")

CAPITAL_POOLS=[
 {"pool_id":"CARE-HRV-01","eligible_families":["Respiratory Utilization","Healthcare Inflation","Reimbursement","Pharmacy / Specialty"],"geographies":["Texas","National","North Carolina"],"available_capacity":2100000.0,"minimum_basis_grade":"B+"},
 {"pool_id":"CARE-RESP-01","eligible_families":["Respiratory Utilization"],"geographies":["Texas","National","North Carolina"],"available_capacity":1250000.0,"minimum_basis_grade":"B"},
 {"pool_id":"CARE-INF-01","eligible_families":["Healthcare Inflation","Reimbursement"],"geographies":["National"],"available_capacity":1800000.0,"minimum_basis_grade":"A-"},
]

def money(x):
    return "$"+f"{float(x):,.0f}"

@st.cache_data(ttl=900,show_spinner=False)
def graph_state():
    marks=fetch_oriel_marks()
    return build_risk_graph(
        SAMPLE_PORTFOLIO,marks,CAPITAL_POOLS,RISK_FAMILY_HEALTHCARE_BETA,
        correlation_matrix_frame(SAMPLE_PORTFOLIO,1.0),
    )

st.title("CareFi Risk Graph")
st.caption("Healthcare exposure → objective public print → basis → correlated risks → hedge factors → institutional capacity")

graph=graph_state()
s=graph["summary"]
c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Healthcare risks",s["event_count"])
c2.metric("Graph nodes",s["node_count"])
c3.metric("Relationships",s["edge_count"])
c4.metric("Capital routable",f"{s['capital_routable_pct']:.0%}")
c5.metric("Hedge connected",f"{s['hedge_connected_pct']:.0%}")

coords=layered_layout(graph)
edge_x=[]; edge_y=[]; corr_x=[]; corr_y=[]
for e in graph["edges"]:
    if e["source"] not in coords or e["target"] not in coords: continue
    x0,y0=coords[e["source"]]; x1,y1=coords[e["target"]]
    if e["relation"]=="correlated_with":
        corr_x += [x0,x1,None]; corr_y += [y0,y1,None]
    else:
        edge_x += [x0,x1,None]; edge_y += [y0,y1,None]

fig=go.Figure()
fig.add_trace(go.Scatter(x=edge_x,y=edge_y,mode="lines",hoverinfo="skip",line=dict(width=1),showlegend=False))
if corr_x:
    fig.add_trace(go.Scatter(x=corr_x,y=corr_y,mode="lines",hoverinfo="skip",line=dict(width=2,dash="dot"),name="Correlation"))

labels={"public_print":"Public print","geography":"Geography","event":"Healthcare risk","risk_family":"Risk family","hedge":"Hedge factor","capital_pool":"Capital pool"}
for t in ["public_print","geography","event","risk_family","hedge","capital_pool"]:
    subset=[n for n in graph["nodes"] if n["type"]==t and n["id"] in coords]
    if not subset: continue
    hover=[]
    for n in subset:
        if t=="event":
            fv=n.get("fair_value")
            hover.append("<b>"+str(n["label"])+"</b><br>Basis: "+str(n.get("basis_grade","—"))+"<br>Oriel FV: "+(f"{float(fv):.1%}" if fv is not None else "—")+"<br>MEDUSDi beta: "+f"{float(n.get('healthcare_beta',0)):.2f}"+"<br>Connectivity: "+f"{float(n.get('basis_connectivity_score',0)):.0f}/100")
        elif t=="capital_pool":
            hover.append("<b>"+str(n["label"])+"</b><br>Available capacity: "+money(n.get("available_capacity",0)))
        else:
            hover.append("<b>"+str(n["label"])+"</b><br>"+labels[t])
    fig.add_trace(go.Scatter(
        x=[coords[n["id"]][0] for n in subset],
        y=[coords[n["id"]][1] for n in subset],
        mode="markers+text",text=[n["label"] for n in subset],textposition="top center",
        hovertext=hover,hoverinfo="text",marker=dict(size=[22 if t=="event" else 16 for _ in subset],line=dict(width=1)),
        name=labels[t],
    ))

fig.update_xaxes(tickmode="array",tickvals=[0,1,2,3],ticktext=["Public data / geography","Healthcare risks","Risk factors","Capital pools"],showgrid=False,zeroline=False)
fig.update_yaxes(showticklabels=False,showgrid=False,zeroline=False)
fig.update_layout(height=650,margin=dict(l=20,r=20,t=30,b=20),legend_orientation="h",legend_y=-0.12)
st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

st.subheader("Risk graph register")
df=event_table(graph)
if not df.empty:
    df["Oriel FV"]=df["Oriel FV"].map(lambda x:"—" if pd.isna(x) else f"{float(x):.1%}")
    df["MEDUSDi beta"]=df["MEDUSDi beta"].map(lambda x:f"{float(x):.2f}")
    df["Basis connectivity"]=df["Basis connectivity"].map(lambda x:f"{float(x):.0f}/100")
    st.dataframe(df,use_container_width=True,hide_index=True)

events=[n for n in graph["nodes"] if n["type"]=="event"]
lookup={n["label"]:n["id"] for n in events}
st.subheader("Relationship drill-down")
choice=st.selectbox("Healthcare exposure",list(lookup.keys()))
nid=lookup[choice]
node=next(n for n in events if n["id"]==nid)
d1,d2,d3,d4=st.columns(4)
d1.metric("Basis grade",str(node.get("basis_grade","—")))
d2.metric("Connectivity score",f"{float(node.get('basis_connectivity_score',0)):.0f}/100")
d3.metric("MEDUSDi beta",f"{float(node.get('healthcare_beta',0)):.2f}")
d4.metric("Eligible pools",len(node.get("eligible_pools",[])))
st.dataframe(neighborhood(graph,nid),use_container_width=True,hide_index=True)

st.info("The graph is the protocol's relationship layer: it links economic/event exposure to settlement evidence, basis quality, correlation, hedge sensitivity and capacity eligibility. As CareFi accumulates placements and realized outcomes, these edges and scores can be recalibrated from transaction history.")
