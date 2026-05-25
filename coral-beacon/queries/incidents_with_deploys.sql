SELECT
  i.title AS incident,
  pr.number AS deploy_pr,
  pr.title AS deploy_title,
  pr.merged_at
FROM pagerduty.incidents i
JOIN github.pulls pr
  ON pr.merged_at BETWEEN i.started_at - INTERVAL '2 hours' AND i.started_at
WHERE i.urgency = 'high'
ORDER BY i.started_at DESC
LIMIT 10;
