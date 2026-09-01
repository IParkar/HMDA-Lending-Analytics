
-- ============================================================
-- STAR SCHEMA BUILD
-- Purpose: split the single wide clean table into dimension
-- tables (descriptive attributes) and a fact table (the actual
-- loan-level events). This is standard data warehouse design —
-- it makes the model easier to extend, join, and reason about
-- as more data sources get added later.
-- ============================================================

-- Dimension: lender info
CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DIM_LENDER AS
SELECT DISTINCT lender_id FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;

-- Dimension: geography
CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DIM_GEOGRAPHY AS
SELECT DISTINCT state_code, county_code FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;

-- Dimension: applicant demographics
CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DIM_APPLICANT AS
SELECT DISTINCT race, ethnicity, sex FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;

-- Fact table: the actual loan-level events, referencing dimension keys
CREATE OR REPLACE TABLE HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS AS
SELECT activity_year, lender_id, county_code, state_code, action_taken,
       action_taken_desc, loan_amount, race, ethnicity, sex, income
FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;

-- VERIFY: row counts across all four tables
SELECT 'dim_lender' AS table_name, COUNT(*) AS row_count FROM HMDA_DB.CLEAN.DIM_LENDER
UNION ALL
SELECT 'dim_geography', COUNT(*) FROM HMDA_DB.CLEAN.DIM_GEOGRAPHY
UNION ALL
SELECT 'dim_applicant', COUNT(*) FROM HMDA_DB.CLEAN.DIM_APPLICANT
UNION ALL
SELECT 'fact_loan_applications', COUNT(*) FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS;
-- Confirms the star schema still supports the core analysis —
-- should match Day 2's numbers exactly (16.6% White, 22.7% Black, etc.)
SELECT
    race,
    COUNT(*) AS total_applications,
    ROUND(100.0 * SUM(CASE WHEN action_taken_desc = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
GROUP BY race
ORDER BY total_applications DESC;

-- ============================================================
-- DATA QUALITY CHECKS
-- Purpose: validate the pipeline's own output rather than
-- trusting it blindly. Each row is one check; failing_rows
-- should be 0 for a healthy pipeline.
-- ============================================================

CREATE OR REPLACE TABLE HMDA_DB.CLEAN.DATA_QUALITY_CHECKS AS
SELECT 'null_action_taken' AS check_name, COUNT(*) AS failing_rows
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE action_taken IS NULL

UNION ALL

SELECT 'negative_loan_amount', COUNT(*)
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE loan_amount < 0

UNION ALL

SELECT 'negative_income', COUNT(*)
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE income < 0

UNION ALL

SELECT 'missing_geography', COUNT(*)
FROM HMDA_DB.CLEAN.FACT_LOAN_APPLICATIONS
WHERE county_code IS NULL;

-- View the results
SELECT * FROM HMDA_DB.CLEAN.DATA_QUALITY_CHECKS;