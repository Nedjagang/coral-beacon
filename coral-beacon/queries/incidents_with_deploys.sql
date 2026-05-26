-- schemas: pagerduty, github
-- join: PR merged_at falls within 2 hours before incident created_at
-- shows which high-urgency incidents had a recent deploy as a potential trigger
-- note: requires owner + repo constant; seed repo populated in Phase 6

SELECT
  i.id              AS incident_id,
  i.title           AS incident_title,
  i.urgency,
  i.created_at      AS incident_opened,
  i.service__id     AS service_id,
  pr.number         AS deploy_pr,
  pr.title          AS pr_title,
  pr.user__login    AS pr_author,
  pr.merged_at,
  pr.html_url       AS pr_url
FROM pagerduty.incidents i
JOIN github.pulls pr
  ON CAST(pr.merged_at AS TIMESTAMP)
     BETWEEN CAST(i.created_at AS TIMESTAMP) - INTERVAL '2 hours'
         AND CAST(i.created_at AS TIMESTAMP)
WHERE i.urgency = 'high'
  AND pr.owner = 'Nedjagang'
  AND pr.repo  = 'coral-beacon-demo'
ORDER BY i.created_at DESC
LIMIT 20;
