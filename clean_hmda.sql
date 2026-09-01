CREATE OR REPLACE TABLE HMDA_DB.CLEAN.HMDA_CLEAN_CA AS
SELECT
  "activity_year"::NUMBER AS activity_year,
  -- Renamed lei (Legal Entity Identifier) to something readable —
  -- this is the unique ID for the lending institution
  "lei" AS lender_id,
  -- Keeping geography fields as-is, just renamed for consistency
  "county_code" AS county_code,
  "state_code" AS state_code,
   -- Casting year to a proper number type (was inferred, but this
    -- makes the type explicit and safe for later date math)
  "action_taken"::NUMBER AS action_taken,

      -- Casting action_taken to a number — this is our key outcome
    -- variable (see code dictionary from Block 2's exploration)
  CASE "action_taken"
    WHEN 1 THEN 'Originated'
    WHEN 2 THEN 'Approved Not Accepted'
    WHEN 3 THEN 'Denied'
    WHEN 4 THEN 'Withdrawn'
    WHEN 5 THEN 'Incomplete'
    ELSE 'Other'
  END AS action_taken_desc,
  "loan_amount"::NUMBER AS loan_amount,
  "derived_race" AS race,
  "derived_ethnicity" AS ethnicity,
  "derived_sex" AS sex,
  TRY_CAST("income" AS NUMBER) AS income
FROM HMDA_DB.RAW.HMDA_RAW_CA
WHERE "action_taken" IS NOT NULL
  AND "county_code" IS NOT NULL;
