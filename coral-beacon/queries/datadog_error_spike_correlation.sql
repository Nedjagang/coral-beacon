-- schemas: pagerduty, datadog
-- join: cross join filtered to alerting/no-data monitors — surfaces which
--       Datadog monitors were unhealthy alongside each active incident,
--       helping SREs identify correlated metric failures without leaving SQL

SELECT
  i.id            AS incident_id,
  i.title         AS incident,
  i.urgency,
  i.created_at    AS incident_opened,
  m.id            AS monitor_id,
  m.name          AS monitor_name,
  m.status        AS monitor_status,
  m.tags          AS monitor_tags
FROM pagerduty.incidents i
CROSS JOIN datadog.monitors m
WHERE i.urgency   = 'high'
  AND m.status   != 'OK'
ORDER BY i.created_at DESC, m.status;
