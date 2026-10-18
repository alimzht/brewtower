-- Every flagged record from every check (checks.all_issues is the UNION of the sql/checks files). Nothing is
-- dropped from the facts: this table says what is wrong with which record, so Power BI can drill from a score down
-- to the records behind it. date = the file (or as-of) day the issue belongs to.
SELECT i.file_date AS date,
       i.source,
       i.check_name,
       i.dimension,
       i.record_id,
       CASE WHEN i.dc_code IS NULL THEN NULL
            WHEN i.dc_code IN (SELECT dc_code FROM staging.dcs) THEN i.dc_code
            ELSE 'UNKNOWN' END AS dc_code,
       i.reason
FROM checks.all_issues i
