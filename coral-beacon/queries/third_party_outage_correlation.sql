-- schemas: pagerduty, statusgator
-- join: cross join — shows the real-time status of every tracked third-party
--       service alongside each high-urgency incident, revealing whether an
--       external dependency was degraded at the time of the incident

SELECT
  i.id              AS incident_id,
  i.title           AS incident,
  i.urgency,
  i.created_at      AS incident_opened,
  sg.display_name   AS third_party_service,
  sg.monitor_type,
  sg.filtered_status AS service_status_at_query_time
FROM pagerduty.incidents i
CROSS JOIN statusgator.monitors sg
WHERE sg.board_id  = 'g1t0HJdmfr'
  AND i.urgency    = 'high'
ORDER BY i.created_at DESC;
