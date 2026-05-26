SELECT schema_name, table_name, description
FROM coral.tables
WHERE schema_name IN ('pagerduty', 'github', 'datadog', 'statusgator')
ORDER BY 1, 2;
