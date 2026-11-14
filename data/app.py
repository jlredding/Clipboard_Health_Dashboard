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
GAP_HPRD = 0.5      # below this for the whole quarter = almost certainly missing hours, not real staffing


@st.cache_data
def load_data():
    fac = pd.read_csv(DATA / "facilities.csv", dtype={"PROVNUM": str})
    daily = pd.read_csv(DATA / "daily_state.csv", parse_dates=["WorkDate"])
    # Size bands = census quartiles, computed once on all facilities so they don't shift with filters
    fac["size_band"] = pd.qcut(fac["avg_census"], 4,
                               labels=["Small (Q1)", "Mid-small (Q2)", "Mid-large (Q3)", "Large (Q4)"])
    fac["reporting_gap"] = fac["hprd"] < GAP_HPRD
    return fac, daily


fac, daily = load_data()

# ---------------- Sidebar filters ----------------
st.sidebar.header("Filters")
states = sorted(fac["STATE"].unique())
picked = st.sidebar.multiselect("State(s)", states, placeholder="All states")
min_census = st.sidebar.slider("Minimum average census", 0, int(fac["avg_census"].max()), 0)
hide_gaps = st.sidebar.checkbox(f"Exclude likely reporting gaps (HPRD < {GAP_HPRD})", value=True,
                                help=f"{int(fac['reporting_gap'].sum())} facilities report almost no nursing "
                                     "hours for the whole quarter - almost certainly missing data.")

f = fac[fac["avg_census"] >= min_census]
if hide_gaps:
    f = f[~f["reporting_gap"]]
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
    c3.metric("Contract share", f"{contract:.1%}")
    c4.metric(f"Below {TARGET_HPRD} HPRD", f"{below:.0%}")

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

# ---------------- Tab 2: Census & Capacity ----------------
with tab2:
    r = f["avg_census"].corr(f["hprd"])
    st.subheader("Do bigger facilities staff each resident differently?")
    st.caption(f"Each dot is one facility (quarter averages). Correlation between census and HPRD: "
               f"r = {r:.2f}. Size barely predicts how many nursing hours each resident gets.")
    plot = f[f["hprd"] <= 8]
    fig = px.scatter(plot, x="avg_census", y="hprd", color="size_band", opacity=0.45,
                     hover_name="PROVNAME", hover_data={"STATE": True, "avg_census": ":.0f", "hprd": ":.2f",
                                                        "size_band": False},
                     labels={"avg_census": "Average daily census (residents)", "hprd": "HPRD",
                             "size_band": "Size band"},
                     category_orders={"size_band": list(fac["size_band"].cat.categories)})
    fig.add_hline(y=TARGET_HPRD, line_dash="dash", annotation_text=f"{TARGET_HPRD} target")
    fig.update_traces(marker_size=5)
    st.plotly_chart(fig, width="stretch")
    if len(plot) < len(f):
        st.caption(f"{len(f) - len(plot)} facilities above 8 HPRD are hidden from the chart.")

    st.subheader("Staffing by facility size")
    band = (f.groupby("size_band", observed=True)
              .agg(facilities=("PROVNUM", "count"), median_census=("avg_census", "median"),
                   nurse_hrs=("nurse_hrs", "sum"), resident_days=("resident_days", "sum"),
                   below=("hprd", lambda x: (x < TARGET_HPRD).mean()))
              .reset_index())
    band["hprd"] = band["nurse_hrs"] / band["resident_days"]
    b1, b2 = st.columns(2)
    with b1:
        fig = px.bar(band, x="size_band", y="hprd", text_auto=".2f",
                     labels={"size_band": "", "hprd": "HPRD"}, title="Average HPRD")
        fig.add_hline(y=TARGET_HPRD, line_dash="dash")
        st.plotly_chart(fig, width="stretch")
    with b2:
        fig = px.bar(band, x="size_band", y="below", text_auto=".0%",
                     labels={"size_band": "", "below": "Share of facilities"},
                     title=f"Share of facilities below {TARGET_HPRD} HPRD")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Largest vs. smallest facilities")
    n = st.slider("How many of each", 5, 20, 10)
    cols = {"PROVNAME": "Facility", "STATE": "State", "avg_census": "Avg census", "hprd": "HPRD"}
    l, s_ = st.columns(2)
    for col, label, rows in [(l, "Largest", f.nlargest(n, "avg_census")),
                             (s_, "Smallest", f.nsmallest(n, "avg_census"))]:
        with col:
            fig = px.bar(rows.sort_values("avg_census"), x="avg_census", y="PROVNAME", orientation="h",
                         color="hprd", color_continuous_scale="RdBu", range_color=[2, 5],
                         hover_data={"STATE": True, "hprd": ":.2f"},
                         labels={"avg_census": "Avg census", "PROVNAME": "", "hprd": "HPRD"},
                         title=f"{label} {n} by census")
            fig.update_layout(height=120 + 28 * n)
            st.plotly_chart(fig, width="stretch")

    st.subheader("Low-staffing watchlist")
    st.caption("Facilities with frequent days under 1.5 HPRD. Very low quarter-wide HPRD usually means "
               "hours weren't reported, so those are flagged separately.")
    min_days = st.slider("Minimum days under 1.5 HPRD (out of 91)", 1, 91, 10)
    pool = fac[fac["avg_census"] >= min_census]
    if picked:
        pool = pool[pool["STATE"].isin(picked)]
    watch = pool[pool["days_below_1_5"] >= min_days].copy()
    watch["Flag"] = watch["reporting_gap"].map({True: "Likely reporting gap", False: "Possible strain"})
    w1, w2 = st.columns(2)
    w1.metric("Possible strain", f"{(watch['Flag'] == 'Possible strain').sum():,}")
    w2.metric("Likely reporting gaps", f"{(watch['Flag'] == 'Likely reporting gap').sum():,}")
    st.dataframe(watch.sort_values("days_below_1_5", ascending=False)
                 [["Flag", "PROVNAME", "CITY", "STATE", "avg_census", "hprd", "days_below_1_5"]]
                 .rename(columns={"PROVNAME": "Facility", "CITY": "City", "STATE": "State",
                                  "avg_census": "Avg census", "hprd": "HPRD",
                                  "days_below_1_5": "Days < 1.5"}).round(2),
                 hide_index=True, width="stretch")

# ---------------- Tab 3: Contract Staffing (next step) ----------------
with tab3:
    st.info("Coming in step 4: contract share by state, contract share vs. HPRD, savings calculator.")
