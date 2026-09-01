-- ============================================================
-- VERIFY CLEAN TABLE
-- Purpose: confirm the cleaning worked as expected before
-- moving on — check row count survived reasonably, and get
-- a first real, readable insight (a preview of
-- dashboard).
-- ============================================================

-- How many rows survived the WHERE filters?
-- Compare this to 1,161,292 raw row count —
-- expect it to be close, since action_taken and county_code
-- were mostly non-null 
SELECT COUNT(*) AS clean_row_count
FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA;

-- First real insight: approval/denial counts with average loan size
-- This directly previews the kind of chart you'll build Thursday
SELECT
    action_taken_desc,
    COUNT(*) AS count,
    ROUND(AVG(loan_amount), 0) AS avg_loan_amount
FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA
GROUP BY action_taken_desc
ORDER BY count DESC;

-- Quick look at denial rate by race — this is the CDFI-relevant
-- does approval outcome vary by demographic group?
SELECT
    race,
    COUNT(*) AS total_applications,
    SUM(CASE WHEN action_taken_desc = 'Denied' THEN 1 ELSE 0 END) AS denied_count,
    ROUND(100.0 * SUM(CASE WHEN action_taken_desc = 'Denied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS denial_rate_pct
FROM HMDA_DB.CLEAN.HMDA_CLEAN_CA
GROUP BY race
ORDER BY total_applications DESC;