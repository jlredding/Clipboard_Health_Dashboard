"""
Clipboard Health - Q2 2024 Nursing Home Staffing Dashboard
Run locally:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Nursing Home Staffing - Q2 2024", layout="wide")

DATA = Path(__file__).parent / "data"
TARGET_HPRD = 3.0   # TODO: cite the source for this benchmark in the README


@st.cache_data
def load_data():
    fac = pd.read_csv(DATA / "facilities.csv", dtype={"PROVNUM": str})
    daily = pd.read_csv(DATA / "daily_state.csv", parse_dates=["WorkDate"])
    return fac, daily


fac, daily = load_data()

# ---------------- Sidebar filters ----------------
st.sidebar.header("Filters")
states = sorted(fac["STATE"].unique())
picked = st.sidebar.multiselect("State(s)", states, placeholder="All states")
min_census = st.sidebar.slider("Minimum average census", 0, int(fac["avg_census"].max()), 0)

f = fac[fac["avg_census"] >= min_census]
if picked:
    f = f[f["STATE"].isin(picked)]
d = daily[daily["STATE"].isin(picked)] if picked else daily

st.title("Nursing Home Staffing - Q2 2024")
st.caption("Source: CMS Payroll Based Journal (PBJ) Daily Nurse Staffing, Apr-Jun 2024. "
           "HPRD = nursing hours (RN + LPN + CNA) per resident day.")

if f.empty:
    st.warning("No facilities match these filters.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["National Overview", "Census & Capacity", "Contract Staffing"])

# ---------------- Tab 1: National Overview ----------------
with tab1:
    # KPI cards (weighted by resident-days so big and small homes count fairly)
    hprd = f["nurse_hrs"].sum() / f["resident_days"].sum()
    contract = f["contract_hrs"].sum() / f["nurse_hrs"].sum()
    below = (f["hprd"] < TARGET_HPRD).mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Facilities", f"{len(f):,}")
    c2.metric("Nursing HPRD", f"{hprd:.2f}")
    c3.metric("Contract share of hours", f"{contract:.1%}")
    c4.metric(f"Facilities below {TARGET_HPRD} HPRD", f"{below:.0%}")

    # State map
    by_state = (f.groupby("STATE")
                  .agg(nurse_hrs=("nurse_hrs", "sum"), resident_days=("resident_days", "sum"),
                       facilities=("PROVNUM", "count"))
                  .reset_index())
    by_state["hprd"] = by_state["nurse_hrs"] / by_state["resident_days"]

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Average HPRD by state")
        fig = px.choropleth(by_state, locations="STATE", locationmode="USA-states", scope="usa",
                            color="hprd", color_continuous_scale="RdBu",
                            hover_data={"facilities": True, "hprd": ":.2f"},
                            labels={"hprd": "HPRD"})
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, width="stretch")
    with right:
        st.subheader("Facility distribution")
        fig = px.histogram(f[f["hprd"] <= 10], x="hprd", nbins=60,
                           labels={"hprd": "Facility HPRD (quarter)"})
        fig.add_vline(x=TARGET_HPRD, line_dash="dash", annotation_text=f"{TARGET_HPRD} target")
        fig.update_layout(yaxis_title="Facilities", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader("Daily trend")
    trend = d.groupby("WorkDate")[["nurse_hrs", "resident_days"]].sum().reset_index()
    trend["hprd"] = trend["nurse_hrs"] / trend["resident_days"]
    st.plotly_chart(px.line(trend, x="WorkDate", y="hprd", labels={"hprd": "HPRD", "WorkDate": ""}),
                    width="stretch")

    st.subheader("State ranking")
    st.dataframe(by_state.sort_values("hprd")[["STATE", "facilities", "hprd"]]
                 .rename(columns={"hprd": "HPRD"}).round(2),
                 hide_index=True, width="stretch")

# ---------------- Tab 2: Census & Capacity (next step) ----------------
with tab2:
    st.info("Coming in step 3: HPRD vs. census scatter, smallest vs. largest homes, low-staffing watchlist.")

# ---------------- Tab 3: Contract Staffing (next step) ----------------
with tab3:
    st.info("Coming in step 4: contract share by state, contract share vs. HPRD, savings calculator.")
