-- Row count by year
SELECT "activity_year", COUNT(*) AS row_count
FROM HMDA_DB.RAW.HMDA_RAW_CA
GROUP BY "activity_year"
ORDER BY "activity_year";

-- Action taken breakdown (this is the key outcome variable)
SELECT "action_taken", COUNT(*) AS row_count
FROM HMDA_DB.RAW.HMDA_RAW_CA
GROUP BY "action_taken"
ORDER BY row_count DESC;

/*-- ============================================
-- HMDA action_taken code dictionary (per CFPB LAR field reference):
-- 1 = Loan originated
-- 2 = Application approved but not accepted
-- 3 = Application denied
-- 4 = Application withdrawn by applicant
-- 5 = File closed for incompleteness
-- 6 = Purchased loan
-- 7 = Preapproval request denied
-- 8 = Preapproval request approved but not accepted
-- Source: https://ffiec.cfpb.gov/documentation/publications/loan-level-datasets/lar-data-fields
-- ============================================

-- Row count by year
SELECT "activity_year", COUNT(*) AS row_count
FROM HMDA_DB.RAW.HMDA_RAW_CA
GROUP BY "activity_year"
ORDER BY "activity_year";

-- Action taken breakdown (this is your key outcome variable)
-- See code dictionary above for what each number means
SELECT "action_taken", COUNT(*) AS row_count
FROM HMDA_DB.RAW.HMDA_RAW_CA
GROUP BY "action_taken"
ORDER BY row_count DESC;

-- Check for nulls in key fields
SELECT
  COUNT(*) AS total_rows,
  COUNT("loan_amount") AS non_null_loan_amount,
  COUNT("derived_race") AS non_null_race,
  COUNT("derived_sex") AS non_null_sex,
  COUNT("county_code") AS non_null_county
FROM HMDA_DB.RAW.HMDA_RAW_CA;*/

-- Check for nulls in key fields
SELECT
  COUNT(*) AS total_rows,
  COUNT("loan_amount") AS non_null_loan_amount,
  COUNT("derived_race") AS non_null_race,
  COUNT("derived_sex") AS non_null_sex,
  COUNT("county_code") AS non_null_county
FROM HMDA_DB.RAW.HMDA_RAW_CA;