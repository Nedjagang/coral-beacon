-- schemas: pagerduty, github
-- join: cross join — pairs each on-call engineer with recently active repos,
--       revealing whether the person currently holding the pager also owns
--       repos with recent commits (potential deploy → incident correlation)

SELECT
  oc.user__summary             AS oncall_engineer,
  oc.escalation_policy__summary AS escalation_policy,
  oc.start                     AS shift_start,
  oc.end                       AS shift_end,
  r.full_name                  AS active_repo,
  r.updated_at                 AS repo_last_updated,
  r.open_issues_count          AS open_issues
FROM pagerduty.oncalls oc
CROSS JOIN github.user_repos r
WHERE oc.escalation_level = 1
ORDER BY r.updated_at DESC, oc.user__summary
LIMIT 20;
