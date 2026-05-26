-- schemas: pagerduty (incidents + oncalls)
-- join: UNION ALL across two PagerDuty tables — unified event timeline
--       ordered by time, used as the foundation for the Web UI timeline view

SELECT
  'incident'   AS event_type,
  id           AS event_id,
  title        AS description,
  urgency      AS severity,
  created_at   AS event_time
FROM pagerduty.incidents
WHERE urgency = 'high'

UNION ALL

SELECT
  'oncall'     AS event_type,
  user__id     AS event_id,
  user__summary AS description,
  'oncall'     AS severity,
  start        AS event_time
FROM pagerduty.oncalls
WHERE escalation_level = 1

ORDER BY event_time DESC
LIMIT 30;
