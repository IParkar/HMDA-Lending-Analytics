# California Home Purchase Lending — Denial Rate Analysis

A personal data engineering + analytics project examining whether lending outcomes differ by applicant demographics in California home purchase mortgage applications, built end-to-end on **Snowflake**.

> **Why this project exists:** I work in mortgage lending operations and wanted hands-on practice building a real data pipeline — from raw public data to a deployed, interactive dashboard — rather than following a tutorial dataset. Fair-lending analysis is a genuinely meaningful question in this industry, so it made for a better learning vehicle than a toy example.

**Headline finding:** White applicants show a 16.6% denial rate, compared to 22–24% for Black, American Indian/Alaska Native, and Native Hawaiian/Pacific Islander applicants — a consistent 6–8 point gap that persists even when controlling for income bracket.

---

## Architecture

```
CFPB HMDA public data (CSV)
        │
        ▼
Snowflake CLI (snow stage copy + COPY INTO)
        │
        ▼
RAW schema  →  CLEAN schema (typed, filtered, human-readable)
        │
        ▼
Star schema: FACT_LOAN_APPLICATIONS + DIM_LENDER / DIM_GEOGRAPHY / DIM_APPLICANT
        │
        ▼
Streamlit-in-Snowflake dashboard (Altair charts) + Power BI (Import mode)
```

## Tech stack

| Layer | Tool |
|---|---|
| Data warehouse | Snowflake (trial account, AWS-hosted) |
| Data loading | Snowflake CLI (`snow` commands) |
| Transformation | SQL (staging → cleaning → star schema) |
| Visualization | Streamlit-in-Snowflake + Altair, and Power BI |
| Version control | Git / GitHub |

---

## How to reproduce this from scratch

### 1. Set up Snowflake trial + database objects

Sign up at signup.snowflake.com, choosing AWS as the cloud provider. Then in a Snowsight worksheet:

```sql
CREATE DATABASE HMDA_DB;
CREATE SCHEMA HMDA_DB.RAW;
CREATE SCHEMA HMDA_DB.CLEAN;
CREATE WAREHOUSE HMDA_WH WITH WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE;
```

### 2. Get the data

Download from the [CFPB HMDA Data Browser](https://ffiec.cfpb.gov/data-browser/), filtered to California + Home Purchase loan purpose.

### 3. Install and configure Snowflake CLI

Install via Homebrew (Mac) or the Windows installer from snowflake.com/developers/downloads. Then connect:

```
snow connection add
```

When prompted, enter:

```
Connection name: hmda_trial
Account: <your account identifier — found in Snowsight under your profile icon>
User: <your username>
Password: <your password>
Role: ACCOUNTADMIN
Warehouse: HMDA_WH
Database: HMDA_DB
Schema: RAW
```

Verify it works:

```
snow connection test --connection hmda_trial
```

### 4. Create a file format and stage

```
snow sql -q 'CREATE FILE FORMAT IF NOT EXISTS HMDA_DB.RAW.hmda_csv_format TYPE=CSV PARSE_HEADER=TRUE;' --connection hmda_trial

snow sql -q 'CREATE STAGE IF NOT EXISTS HMDA_DB.RAW.hmda_stage;' --connection hmda_trial
```

### 5. Upload the CSV to the stage

```
snow stage copy "C:\path\to\your\downloaded_file.csv" "@HMDA_DB.RAW.hmda_stage" --connection hmda_trial
```

### 6. Auto-create the table from the file's structure, then load it

```
snow sql -q "CREATE TABLE HMDA_DB.RAW.HMDA_RAW_CA USING TEMPLATE (SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*)) FROM TABLE(INFER_SCHEMA(LOCATION=>'@HMDA_DB.RAW.hmda_stage', FILE_FORMAT=>'HMDA_DB.RAW.hmda_csv_format')));" --connection hmda_trial

snow sql -q "COPY INTO HMDA_DB.RAW.HMDA_RAW_CA FROM @HMDA_DB.RAW.hmda_stage FILE_FORMAT=(FORMAT_NAME='HMDA_DB.RAW.hmda_csv_format') MATCH_BY_COLUMN_NAME='CASE_INSENSITIVE';" --connection hmda_trial
```

Result: 1,161,292 rows loaded, 0 errors. Confirmed as a single year (2025) via:

```sql
SELECT ACTIVITY_YEAR, COUNT(*) FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS GROUP BY ACTIVITY_YEAR;
```

### 7. Clean the data (`clean_hmda.sql`)

Explored the raw data first (`explore.sql`) — checked year range, `action_taken` distribution, and null rates in key fields. Then built a cleaned, typed table filtering out rows missing `action_taken` or `county_code`, casting `income` with `TRY_CAST` (since some values were non-numeric/placeholder), and adding a readable `action_taken_desc` label via `CASE WHEN`.

### 8. Build the star schema (`start_schema.sql`)

**Why a star schema:** a single flat table repeats descriptive data (state, lender, race) across hundreds of thousands of rows. Splitting into fact + dimension tables is the standard fix.

- **Fact table** = events/transactions with measurable numbers (`loan_amount`, `income`, `action_taken`) — one row per loan application
- **Dimension tables** = descriptive attributes you'd slice by (`DIM_GEOGRAPHY`, `DIM_LENDER`, `DIM_APPLICANT`) — things that exist independently of any one transaction

**Decision rule used for every column:** does it get summed/counted (→ fact), or does it answer who/what/where and repeat across many rows (→ dimension)?

```sql
CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DIM_LENDER AS
SELECT DISTINCT lender_id FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA WHERE lender_id IS NOT NULL;

CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DIM_GEOGRAPHY AS
SELECT DISTINCT state_code, county_code FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA WHERE county_code IS NOT NULL;

CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DIM_APPLICANT AS
SELECT DISTINCT race, ethnicity, sex FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;

CREATE OR REPLACE TABLE HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS AS
SELECT activity_year, lender_id, state_code, county_code, race, ethnicity, sex,
       action_taken, action_taken_desc, loan_amount, income
FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;
```

Result: `FACT_LOAN_APPLICATIONS` (1,161,292 rows), `DIM_LENDER` (1,160), `DIM_GEOGRAPHY` (59 CA counties), `DIM_APPLICANT` (171 combinations).

**Engineering note:** `DIM_APPLICANT` deliberately isn't joined to the fact table in the BI layer. Since it only stores category combinations with no additional attributes, and `race`/`ethnicity`/`sex` already live directly on the fact table, joining it adds complexity with zero analytical benefit — a case where the "correct-looking" dimensional pattern wasn't worth the engineering effort. Queries use the fact table's own columns directly instead.

### 9. Data quality checks (`verification.sql`)

```sql
CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DATA_QUALITY_CHECKS AS
SELECT 'null_action_taken' AS check_name, COUNT(*) AS failing_rows
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS WHERE action_taken IS NULL
UNION ALL
SELECT 'negative_loan_amount', COUNT(*) FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS WHERE loan_amount < 0
UNION ALL
SELECT 'negative_income', COUNT(*) FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS WHERE income < 0
UNION ALL
SELECT 'missing_geography', COUNT(*) FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS WHERE county_code IS NULL;
```

| Check | Result |
|---|---|
| Null action_taken | 0 failing rows |
| Negative loan amount | 0 failing rows |
| Negative income | 825 failing rows (0.07%) — placeholder values, excluded from income-based analysis |
| Missing geography | 0 failing rows |

### 10. Build the dashboards

**Streamlit-in-Snowflake:** built directly in Snowsight (Projects → Streamlit), using `get_active_session()` for a credential-free connection, with Altair for custom-colored, interactive charts (`HMDA_Lending_Dashboard.py` in this repo).

---

## Key metrics tracked

- Denial rate %, approval rate %, withdrawal rate %, incomplete-file rate %
- Denial rate by race, county, lender, and loan-amount bracket
- Denial rate by race *split by income bracket* (a control against the most obvious alternative explanation)
- Average loan amount by outcome
- Loan-to-income ratio (a DIY affordability proxy, since official DTI/LTV aren't in public HMDA data)

## Limitations (read before assuming too much)

Raw denial-rate differences do **not** by themselves prove discrimination. Legitimate underwriting factors — credit score, debt-to-income ratio, loan-to-value ratio — aren't present in public HMDA data and could contribute to the disparity. The income-bracket and loan-to-income breakdowns are partial controls, not complete ones.

Other known limitations:
- Single year (2025) only — no trend-over-time analysis possible
- Lenders identified only by LEI code, not company name (HMDA's standard format)
- 'Free Form Text Only', 'Joint', and 'Race Not Available' race categories excluded from race breakdowns (they don't represent single-applicant demographics)

## What I'd build next

- Extend to additional states or years to check if the pattern holds more broadly
- Add credit score/DTI as controls, if a dataset with those fields becomes available
- Automate refresh via a scheduled Snowflake Task
- Explore Snowflake Cortex for natural-language summarization of findings

## Skills demonstrated

`Snowflake` · `SQL` (CTEs, CASE/bucketing, HAVING vs WHERE, TRY_CAST, NULLIF) · `Snowflake CLI` · `dimensional modeling (star schema)` · `data quality validation` · `Python` · `Streamlit` · `Altair` · `Power BI / DAX` · `Git/GitHub`

## Repo contents

- `HMDA_Lending_Dashboard.py` — Streamlit dashboard (heavily commented as self-teaching notes)
- `setup.sql` — database/warehouse/stage setup
- `explore.sql` — initial data exploration
- `clean_hmda.sql` — cleaning and typing logic
- `start_schema.sql` — star schema build
- `verification.sql` — data quality checks

## Data source

[CFPB HMDA Data Browser](https://ffiec.cfpb.gov/data-browser/) — public, federally mandated mortgage disclosure data.
