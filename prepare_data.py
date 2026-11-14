"""
Step 1 - Build small, dashboard-ready files from the raw PBJ data.
Run this in Colab (paste as one cell). It reads the FULL CSV (not the .xlsx,
which Excel cut off at 1,048,575 rows) and writes two small CSVs that go in
your repo's data/ folder.
"""
import pandas as pd

RAW = "/content/drive/MyDrive/Colab Notebooks/Clipboard Health/PBJ_Daily_Nurse_Staffing_Q2_2024.csv"

cols = ["PROVNUM", "PROVNAME", "CITY", "STATE", "COUNTY_NAME", "WorkDate", "MDScensus",
        "Hrs_RN", "Hrs_LPN", "Hrs_CNA", "Hrs_RN_ctr", "Hrs_LPN_ctr", "Hrs_CNA_ctr"]
df = pd.read_csv(RAW, usecols=cols, dtype={"PROVNUM": str}, encoding="cp1252")
print("Rows:", len(df), "| States:", df["STATE"].nunique())   # expect ~1.3M rows, ~53 states

# Same cleaning as the notebook
df = df[df["MDScensus"] > 0].copy()
df["WorkDate"] = pd.to_datetime(df["WorkDate"].astype(str), format="%Y%m%d")
df["nurse_hrs"] = df["Hrs_RN"] + df["Hrs_LPN"] + df["Hrs_CNA"]
df["contract_hrs"] = df["Hrs_RN_ctr"] + df["Hrs_LPN_ctr"] + df["Hrs_CNA_ctr"]
df["daily_hprd"] = df["nurse_hrs"] / df["MDScensus"]
df["low_day"] = (df["daily_hprd"] < 1.5).astype(int)

# ---- facilities.csv: one row per nursing home for the quarter ----
fac = (df.groupby(["PROVNUM", "PROVNAME", "CITY", "STATE", "COUNTY_NAME"])
         .agg(days_reported=("WorkDate", "nunique"),
              resident_days=("MDScensus", "sum"),
              avg_census=("MDScensus", "mean"),
              nurse_hrs=("nurse_hrs", "sum"),
              rn_hrs=("Hrs_RN", "sum"),
              contract_hrs=("contract_hrs", "sum"),
              days_below_1_5=("low_day", "sum"))
         .reset_index())
# Weighted HPRD = total hours / total resident-days (more accurate than averaging daily ratios)
fac["hprd"] = fac["nurse_hrs"] / fac["resident_days"]
fac["rn_hprd"] = fac["rn_hrs"] / fac["resident_days"]
fac["contract_share"] = (fac["contract_hrs"] / fac["nurse_hrs"]).fillna(0)
fac.round(4).to_csv("facilities.csv", index=False)

# ---- daily_state.csv: one row per state per day (for trend lines) ----
daily = (df.groupby(["STATE", "WorkDate"])
           .agg(resident_days=("MDScensus", "sum"),
                nurse_hrs=("nurse_hrs", "sum"),
                contract_hrs=("contract_hrs", "sum"))
           .reset_index())
daily.to_csv("daily_state.csv", index=False)

print("facilities.csv:", fac.shape, "| daily_state.csv:", daily.shape)

# Download both files to your computer, then add them to the repo's data/ folder
from google.colab import files
files.download("facilities.csv")
files.download("daily_state.csv")
