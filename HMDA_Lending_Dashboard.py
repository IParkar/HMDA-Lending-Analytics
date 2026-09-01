"""
HMDA Lending Dashboard - personal project built to learn Snowflake +
Streamlit + Altair together on a real dataset, not a toy example.

Big picture / architecture, for future-me:
    Snowflake (FACT_LOAN_APPLICATIONS table, star schema)
        -> session.sql() pulls a query result into a pandas DataFrame
        -> Altair turns that DataFrame into a chart object
        -> Streamlit renders the chart + surrounding text as a web page

Nothing here is "live" in the sense of auto-refreshing - every time
this script reruns (on save, or when Streamlit detects a change),
it re-executes top to bottom and re-queries Snowflake fresh.
"""

import streamlit as st
import pandas as pd
import altair as alt
from snowflake.snowpark.context import get_active_session

# st.set_page_config() has a hard rule: it MUST be the very first
# Streamlit command that runs in the script. If anything else (even
# st.title) runs before it, Streamlit throws an error or silently
# misbehaves. Learned this the hard way - keep it first, always.
st.set_page_config(page_title="HMDA Lending Dashboard", layout="wide")

# ------------------------------------------------------------
# COLOR PALETTE
# Streamlit's st.bar_chart() only ever draws in one default blue -
# no way to customize it. Altair (a proper charting library) lets
# me set exact hex colors instead, so I picked colors on purpose
# for a financial/lending subject: navy = institutional/trust,
# gold = "look here, this is the finding" highlight color.
# Defining them once as constants means every chart below stays
# consistent, and I only ever change a color in one place.
# ------------------------------------------------------------
NAVY = "#1F3864"
GOLD = "#C9A227"
GRAY = "#9CA3AF"

# get_active_session() is Snowflake-specific magic: because this
# script is running INSIDE Snowflake (Streamlit-in-Snowflake), it
# already knows who I am and what warehouse/database to use - no
# credentials needed in the code at all, unlike the CLI setup
# earlier this week where I had to manage a whole connection.
session = get_active_session()

st.title("California Home Purchase Lending — Denial Rate Patterns")
st.caption("Source: CFPB HMDA public data · California home purchase applications · 2025")

# ------------------------------------------------------------
# WHY THIS PROJECT / KPI GLOSSARY
# These two sections exist because a bunch of charts with no
# framing just looks like "I can query data," not "I understand
# the business question." Naming the KPIs explicitly, before
# showing them, is what makes this read like analysis instead of
# a homework dump.
# ------------------------------------------------------------
st.header("Why This Project")
st.markdown("""
I work in mortgage lending operations, and wanted to explore a question that
sits at the intersection of my day job and fair-lending policy more broadly:
**do lending outcomes differ by applicant demographics in California home
purchase lending, and if so, where?**

I built this as a personal project using public HMDA (Home Mortgage Disclosure
Act) data — the same category of data mortgage lenders are federally required
to report — to practice building an end-to-end pipeline (Snowflake, SQL, a
star schema, and this Streamlit dashboard) on a real, meaningful dataset
rather than a toy example.
""")

st.header("Key Metrics Tracked")
st.markdown("""
- **Denial Rate %** — share of applications denied; the core access/fairness indicator
- **Approval Rate %** — share originated or approved-not-accepted; the positive-framed counterpart to denial rate
- **Withdrawal Rate %** — share withdrawn by the applicant before a decision; signals friction separate from denial
- **Incomplete File Rate %** — share closed for incompleteness; an operational metric, not just an outcome one
- **Application Volume** — total applications per group, to ensure findings aren't based on tiny, unreliable samples
- **Average Loan Amount by Outcome** — whether denied applications skew toward larger or smaller loans
- **Loan-to-Income Ratio** — a rough affordability proxy, since official DTI/LTV aren't in public HMDA data
- **Denial Rate by Income Bracket / Loan Amount Bracket** — controls for the most obvious alternative explanations before attributing a gap to demographics alone
- **Denial Rate by Lender** — checks whether the pattern is concentrated in a few lenders or consistent market-wide
""")

# ==============================================================
# CHART 1: Denial Rate by Race
# ==============================================================
# The core insight query. Denial rate = (denied count / total
# count) * 100. In SQL, CASE WHEN ... THEN 1 ELSE 0 END inside a
# SUM() is a classic pattern for turning "count rows matching a
# condition" into a number I can do arithmetic on - same trick I
# used in the DAX measure earlier in the week, just SQL-flavored.
race_query = """
SELECT
    RACE,
    COUNT(*) AS total_applications,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN_DESC = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE RACE NOT IN ('Free Form Text Only', 'Joint', 'Race Not Available')
GROUP BY RACE
ORDER BY denial_rate_pct DESC
"""
# session.sql(...) sends the query to Snowflake and gets a result
# back; .to_pandas() converts that result into a pandas DataFrame,
# which is the format Streamlit/Altair actually know how to plot.
# This round-trip (SQL string -> Snowflake -> pandas -> chart) is
# the basic shape of every query block in this whole script.
race_df = session.sql(race_query).to_pandas()

# Adding a column here just for color-coding: I want "White" (the
# baseline) to look visually different from every group ABOVE the
# baseline, so the disparity is obvious at a glance instead of
# requiring the viewer to read every number off the axis.
race_df["HIGHLIGHT"] = race_df["RACE"].apply(lambda r: "White (baseline)" if r == "White" else "Above baseline")

st.subheader("Denial Rate by Race")

# Altair charts are built by chaining pieces together:
#   alt.Chart(dataframe)      -> which data to draw from
#   .mark_bar()               -> what shape to draw (bars here)
#   .encode(...)              -> which columns map to which visual
#                                 channel (x position, y position,
#                                 color, tooltip text)
#   .properties(...)          -> chart-level settings like height
# This is different from st.bar_chart(), which just guesses
# everything automatically and can't be told to use a specific
# color scheme - Altair trades a bit more typing for real control.
race_chart = alt.Chart(race_df).mark_bar().encode(
    x=alt.X("RACE:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
    # :N tells Altair "treat this as a Nominal (categorical) field,
    # not a number" - Altair needs this type hint to know how to
    # draw the axis correctly.
    y=alt.Y("DENIAL_RATE_PCT:Q", title="Denial Rate (%)"),
    # :Q = Quantitative (a real number to measure against an axis)
    color=alt.Color("HIGHLIGHT:N",
                     scale=alt.Scale(domain=["White (baseline)", "Above baseline"], range=[GRAY, GOLD]),
                     legend=alt.Legend(title=None)),
    # domain/range is how you manually pair category values to
    # specific colors, instead of letting Altair auto-assign them.
    tooltip=["RACE", "DENIAL_RATE_PCT", "TOTAL_APPLICATIONS"]
    # tooltip = what shows up on hover; a nice free feature
    # st.bar_chart() doesn't give you.
).properties(height=350)

st.altair_chart(race_chart, use_container_width=True)
st.dataframe(
    race_df[["RACE", "TOTAL_APPLICATIONS", "DENIAL_RATE_PCT"]]
        .rename(columns={"RACE": "Race", "TOTAL_APPLICATIONS": "Applications", "DENIAL_RATE_PCT": "Denial Rate %"}),
    # hide_index=True drops the default 0,1,2,3... row-number
    # column pandas adds automatically - it was just visual noise.
    # width="stretch" replaces the older use_container_width=True,
    # which Streamlit is deprecating - same effect, new name.
    hide_index=True, width="stretch",
)

# A chart with no interpretation just shows numbers; the sentence
# below is where I actually state the finding in plain English -
# this is the difference between "here is data" and "here is what
# the data means."
st.info(
    "White applicants show a 16.6% denial rate vs. 22-24% for Black, American "
    "Indian/Alaska Native, and Native Hawaiian/Pacific Islander applicants — "
    "a consistent 6-8 point gap across every minority group with sufficient "
    "sample size (all above 3,000 applications)."
)

# ==============================================================
# CHART 2: Application Outcome Funnel (KPI cards, not a chart)
# ==============================================================
# HMDA's action_taken field has more than just "approved/denied" -
# applications can also be withdrawn by the applicant or closed
# for incompleteness. Showing all four together as a "funnel"
# gives a fuller operational picture, not just the headline metric.
funnel_query = """
SELECT
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN IN (1,2) THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN = 3 THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN = 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS withdrawal_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN = 5 THEN 1 ELSE 0 END) / COUNT(*), 1) AS incomplete_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
"""
# action_taken codes, from the CFPB data dictionary (memorized
# these earlier in the week so I don't have to look them up every
# time): 1 = Originated, 2 = Approved not accepted, 3 = Denied,
# 4 = Withdrawn, 5 = Incomplete.
funnel_df = session.sql(funnel_query).to_pandas()

st.subheader("Application Outcome Funnel — All Applications")
# st.columns(4) splits the page into 4 equal side-by-side sections.
# st.metric() draws a big-number "KPI card" style widget - good for
# a handful of top-line numbers someone should see instantly
# without having to read a chart.
col1, col2, col3, col4 = st.columns(4)
col1.metric("Approval Rate", f"{funnel_df['APPROVAL_RATE_PCT'][0]}%")
col2.metric("Denial Rate", f"{funnel_df['DENIAL_RATE_PCT'][0]}%")
col3.metric("Withdrawal Rate", f"{funnel_df['WITHDRAWAL_RATE_PCT'][0]}%")
col4.metric("Incomplete Rate", f"{funnel_df['INCOMPLETE_RATE_PCT'][0]}%")
# [0] grabs the first (only) row of a one-row result - funnel_df
# only ever has one row since there's no GROUP BY in that query.

# ==============================================================
# CHART 3: Average Loan Amount by Outcome
# ==============================================================
# Question: do denied applications tend to be for bigger or
# smaller loans than approved ones? A simple GROUP BY + AVG
# answers this directly.
loan_by_outcome_query = """
SELECT
    ACTION_TAKEN_DESC,
    COUNT(*) AS total_applications,
    ROUND(AVG(LOAN_AMOUNT), 0) AS avg_loan_amount
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE LOAN_AMOUNT IS NOT NULL
GROUP BY ACTION_TAKEN_DESC
ORDER BY avg_loan_amount DESC
"""
loan_outcome_df = session.sql(loan_by_outcome_query).to_pandas()

st.subheader("Average Loan Amount by Outcome")
# Reusing the same NAVY color everywhere a chart ISN'T the
# highlighted "finding" chart - keeps a visual hierarchy where
# gold means "pay attention here" and navy means "supporting info."
loan_outcome_chart = alt.Chart(loan_outcome_df).mark_bar(color=NAVY).encode(
    x=alt.X("ACTION_TAKEN_DESC:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
    y=alt.Y("AVG_LOAN_AMOUNT:Q", title="Avg Loan Amount ($)"),
    tooltip=["ACTION_TAKEN_DESC", "AVG_LOAN_AMOUNT", "TOTAL_APPLICATIONS"]
).properties(height=350)
st.altair_chart(loan_outcome_chart, use_container_width=True)
st.dataframe(
    loan_outcome_df.rename(columns={
        "ACTION_TAKEN_DESC": "Outcome", "TOTAL_APPLICATIONS": "Applications", "AVG_LOAN_AMOUNT": "Avg Loan Amount ($)"
    }),
    hide_index=True, width="stretch",
)

# ==============================================================
# CHART 4: Denial Rate by Loan Amount Bracket
# ==============================================================
# CASE WHEN ... is doing "bucketing" here - turning a continuous
# number (loan_amount) into a small number of readable groups.
# Same pattern I used for income brackets in the SQL earlier this
# week - continuous numbers are hard to group by directly (every
# loan amount is basically unique), so bucketing makes GROUP BY
# actually useful.
loan_bracket_query = """
SELECT
    CASE
        WHEN LOAN_AMOUNT < 300000 THEN 'Under $300K'
        WHEN LOAN_AMOUNT < 600000 THEN '$300K-$600K'
        WHEN LOAN_AMOUNT < 1000000 THEN '$600K-$1M'
        ELSE '$1M+'
    END AS loan_bracket,
    COUNT(*) AS total_applications,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN_DESC = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE LOAN_AMOUNT IS NOT NULL
GROUP BY loan_bracket
ORDER BY MIN(LOAN_AMOUNT)
-- ordering by MIN(loan_amount) instead of alphabetically on the
-- bracket label, so "Under $300K" comes before "$1M+" instead of
-- sorting like text (which would put "$1M+" first alphabetically)
"""
loan_bracket_df = session.sql(loan_bracket_query).to_pandas()

st.subheader("Denial Rate by Loan Amount Bracket")
loan_bracket_chart = alt.Chart(loan_bracket_df).mark_bar(color=NAVY).encode(
    x=alt.X("LOAN_BRACKET:N", sort=None, title=None),
    # sort=None here means "keep the order the data already came
    # in" (i.e. respect the SQL's ORDER BY), instead of Altair
    # re-sorting it alphabetically or by value on its own.
    y=alt.Y("DENIAL_RATE_PCT:Q", title="Denial Rate (%)"),
    tooltip=["LOAN_BRACKET", "DENIAL_RATE_PCT", "TOTAL_APPLICATIONS"]
).properties(height=350)
st.altair_chart(loan_bracket_chart, use_container_width=True)
st.dataframe(
    loan_bracket_df.rename(columns={"LOAN_BRACKET": "Loan Bracket", "TOTAL_APPLICATIONS": "Applications", "DENIAL_RATE_PCT": "Denial Rate %"}),
    hide_index=True, width="stretch",
)

# ==============================================================
# CHART 5: Average Loan-to-Income Ratio by Race
# ==============================================================
# I don't have official DTI (debt-to-income) or LTV (loan-to-
# value) data - those aren't in public HMDA. Loan-to-income
# (loan_amount / income) is a rough, DIY stand-in affordability
# signal I can compute myself from what I do have. Worth being
# upfront that this is an approximation, not the real underwriting
# metric a lender would actually use.
lti_query = """
SELECT
    RACE,
    ROUND(AVG(LOAN_AMOUNT / NULLIF(INCOME, 0)), 2) AS avg_loan_to_income_ratio
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE INCOME > 0 AND LOAN_AMOUNT IS NOT NULL
  AND RACE NOT IN ('Free Form Text Only', 'Joint', 'Race Not Available')
GROUP BY RACE
ORDER BY avg_loan_to_income_ratio DESC
"""
# NULLIF(INCOME, 0) is a safety guard: if INCOME were ever exactly
# 0, dividing by it would throw a divide-by-zero error. NULLIF
# turns a 0 into NULL instead, and dividing by NULL just gives
# NULL (which SQL quietly skips in an AVG) rather than crashing
# the whole query. Cheap insurance against a data edge case.
lti_df = session.sql(lti_query).to_pandas()

st.subheader("Average Loan-to-Income Ratio by Race")
st.caption("Rough affordability proxy: loan amount ÷ income. Not official DTI/LTV, which aren't available in public HMDA data.")
lti_chart = alt.Chart(lti_df).mark_bar(color=NAVY).encode(
    x=alt.X("RACE:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
    y=alt.Y("AVG_LOAN_TO_INCOME_RATIO:Q", title="Avg Loan-to-Income Ratio"),
    tooltip=["RACE", "AVG_LOAN_TO_INCOME_RATIO"]
).properties(height=350)
st.altair_chart(lti_chart, use_container_width=True)
st.dataframe(
    lti_df.rename(columns={"RACE": "Race", "AVG_LOAN_TO_INCOME_RATIO": "Avg Loan-to-Income Ratio"}),
    hide_index=True, width="stretch",
)

# ==============================================================
# CHART 6: Denial Rate by County (Top 10 by Volume)
# ==============================================================
# HAVING COUNT(*) > 500 filters OUT small counties with too few
# applications to trust their denial rate percentage (a county
# with 5 applications and 2 denials would show "40% denial rate,"
# which is technically true but statistically meaningless noise).
# HAVING is like WHERE, but it filters AFTER GROUP BY runs -
# WHERE can't reference COUNT(*) directly, HAVING can.
geo_query = """
SELECT
    COUNTY_CODE,
    COUNT(*) AS total_applications,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN_DESC = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
GROUP BY COUNTY_CODE
HAVING COUNT(*) > 500
ORDER BY total_applications DESC
LIMIT 10
"""
geo_df = session.sql(geo_query).to_pandas()

# HMDA only stores counties as FIPS codes (a federal numeric ID
# standard), not names - "06037" means nothing to a reader at a
# glance. Since I only have 10 codes to deal with here, a manual
# lookup dictionary is simpler than joining a full FIPS reference
# table just for this.
FIPS_TO_COUNTY = {
    "06001": "Alameda", "06013": "Contra Costa", "06029": "Kern", "06037": "Los Angeles",
    "06059": "Orange", "06065": "Riverside", "06067": "Sacramento", "06071": "San Bernardino",
    "06073": "San Diego", "06085": "Santa Clara",
}
geo_df["COUNTY_CODE"] = geo_df["COUNTY_CODE"].astype(str)
# .map() looks up each COUNTY_CODE value in the dictionary above;
# .fillna(...) means "if a code isn't in my dictionary, just show
# the raw code instead of a blank" - a safety fallback so the app
# never silently drops a row just because I didn't map its code.
geo_df["COUNTY_NAME"] = geo_df["COUNTY_CODE"].map(FIPS_TO_COUNTY).fillna(geo_df["COUNTY_CODE"])

st.subheader("Top 10 Counties by Application Volume — Denial Rate")
geo_chart = alt.Chart(geo_df).mark_bar(color=NAVY).encode(
    x=alt.X("COUNTY_NAME:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
    y=alt.Y("DENIAL_RATE_PCT:Q", title="Denial Rate (%)"),
    tooltip=["COUNTY_NAME", "DENIAL_RATE_PCT", "TOTAL_APPLICATIONS"]
).properties(height=350)
st.altair_chart(geo_chart, use_container_width=True)
st.dataframe(
    geo_df[["COUNTY_NAME", "TOTAL_APPLICATIONS", "DENIAL_RATE_PCT"]]
        .rename(columns={"COUNTY_NAME": "County", "TOTAL_APPLICATIONS": "Applications", "DENIAL_RATE_PCT": "Denial Rate %"}),
    hide_index=True, width="stretch",
)

# ==============================================================
# CHART 7: Denial Rate by Race, Split by Income Bracket
# ==============================================================
# This is the "control" chart - it exists to answer the obvious
# pushback to Chart 1: "isn't this just about income, not race?"
# By grouping by BOTH race AND income_bracket, I can check whether
# the racial gap survives even when comparing people in the same
# income range to each other.
income_query = """
SELECT
    RACE,
    CASE WHEN INCOME < 100 THEN 'Under $100K' ELSE '$100K+' END AS income_bracket,
    COUNT(*) AS total_applications,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN_DESC = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE INCOME >= 0
-- INCOME >= 0 excludes the 825 rows with negative placeholder
-- income values found during Day 2's data quality check - those
-- aren't real income figures, just missing-data codes.
  AND RACE NOT IN ('Free Form Text Only', 'Joint', 'Race Not Available')
GROUP BY RACE, income_bracket
HAVING COUNT(*) > 200
ORDER BY RACE, income_bracket
"""
income_df = session.sql(income_query).to_pandas()

st.subheader("Denial Rate by Race, Split by Income Bracket")
# xOffset is what turns this into a GROUPED bar chart (two bars
# side by side per race) instead of stacking them or overlapping -
# it nudges each income_bracket's bar sideways within its race's
# slot on the x-axis.
income_chart = alt.Chart(income_df).mark_bar().encode(
    x=alt.X("RACE:N", title=None, axis=alt.Axis(labelAngle=-30)),
    y=alt.Y("DENIAL_RATE_PCT:Q", title="Denial Rate (%)"),
    color=alt.Color("INCOME_BRACKET:N",
                     scale=alt.Scale(domain=["Under $100K", "$100K+"], range=[GOLD, NAVY]),
                     legend=alt.Legend(title="Income Bracket")),
    xOffset="INCOME_BRACKET:N",
    tooltip=["RACE", "INCOME_BRACKET", "DENIAL_RATE_PCT", "TOTAL_APPLICATIONS"]
).properties(height=350)
st.altair_chart(income_chart, use_container_width=True)
st.dataframe(
    income_df.rename(columns={
        "RACE": "Race", "INCOME_BRACKET": "Income Bracket",
        "TOTAL_APPLICATIONS": "Applications", "DENIAL_RATE_PCT": "Denial Rate %"
    }),
    hide_index=True, width="stretch",
)
st.info(
    "The racial gap in denial rates persists within both income brackets, "
    "suggesting income alone does not explain the disparity — though credit "
    "score, DTI, and LTV (not present in public HMDA data) may still be "
    "contributing factors."
)

# ==============================================================
# CHART 8: Denial Rate by Lender (Top 10 by Volume)
# ==============================================================
# Checks whether the race disparity is a market-wide pattern, or
# driven by just a handful of outlier lenders. HMDA identifies
# lenders only by LEI (Legal Entity Identifier) - a global ID
# code, not a company name - so the x-axis shows codes, not
# recognizable brand names. That's a real limitation of the
# source data, not something my pipeline is doing wrong.
lender_query = """
SELECT
    LENDER_ID,
    COUNT(*) AS total_applications,
    ROUND(100.0 * SUM(CASE WHEN ACTION_TAKEN_DESC = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
GROUP BY LENDER_ID
HAVING COUNT(*) > 1000
ORDER BY total_applications DESC
LIMIT 10
"""
lender_df = session.sql(lender_query).to_pandas()

st.subheader("Top 10 Lenders by Volume — Denial Rate")
st.caption("Lenders identified by LEI (Legal Entity Identifier) — HMDA's standard lender ID.")
lender_chart = alt.Chart(lender_df).mark_bar(color=NAVY).encode(
    x=alt.X("LENDER_ID:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-45)),
    y=alt.Y("DENIAL_RATE_PCT:Q", title="Denial Rate (%)"),
    tooltip=["LENDER_ID", "DENIAL_RATE_PCT", "TOTAL_APPLICATIONS"]
).properties(height=350)
st.altair_chart(lender_chart, use_container_width=True)
st.dataframe(
    lender_df.rename(columns={"LENDER_ID": "Lender (LEI)", "TOTAL_APPLICATIONS": "Applications", "DENIAL_RATE_PCT": "Denial Rate %"}),
    hide_index=True, width="stretch",
)

# ==============================================================
# LIMITATIONS & NEXT STEPS
# ==============================================================
# This section is doing real work, not just being polite. A raw
# statistical disparity is NOT the same thing as proof of
# discrimination - there are legitimate underwriting factors
# (credit score, DTI, LTV) that this public dataset doesn't
# include at all. Saying that clearly, in the dashboard itself,
# is what separates "I found a number" from "I understand what
# the number does and doesn't prove."
st.header("Limitations & Next Steps")
st.markdown("""
**What this analysis does NOT show:** raw denial rate differences do not by
themselves prove discrimination — factors like credit score, debt-to-income
ratio, and loan-to-value ratio (not available in public HMDA data) also
legitimately affect underwriting decisions. The income-bracket and
loan-to-income breakdowns are partial controls, not complete ones.

**What I'd build next:**
- Extend to additional states or years to see if the pattern holds more broadly
- Add credit score and DTI as additional controls, if that data becomes available
- Automate this as a scheduled Snowflake Task for ongoing monitoring rather than a one-time analysis

**Known data limitations:**
- 825 rows (0.07%) with placeholder negative income values were excluded from income-based analysis
- 'Free Form Text Only', 'Joint', and 'Race Not Available' race categories were excluded from race breakdowns
- Public HMDA LAR data does not include an application date/month field, so month-over-month trend analysis is not possible with this dataset — only annual granularity is available
- Lenders are identified by LEI (Legal Entity Identifier) codes rather than company names, per HMDA's standard reporting format
""")