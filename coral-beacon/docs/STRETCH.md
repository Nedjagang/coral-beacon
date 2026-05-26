# Stretch ideas — explicitly OUT of the May 25–31 sprint

Don't touch these until in-scope is done. If we're tempted to "just sneak this in," the answer is no — reread `PRD.md` §6.

- **Pre-deploy Blast Radius Scanner** — GitHub Action that comments on PRs with a Coral-powered risk score for the touched services.
- **Incident DNA Fingerprinting** — vector similarity over `runbook.entries` instead of structured equality.
- **Silent Failure Hunter** — Datadog metric anomalies with no corresponding PagerDuty fire.
- **On-Call Burnout Detector** — page-load stats per engineer with night-page weighting.
- **Cascade Failure Predictor** — Datadog APM dependency graph used to predict downstream blast.
- **Incident Cost Calculator** — SLO + revenue-per-minute math, exec-friendly output.
- **Slack / Teams investigator bot** — same agent, chat surface.
- **Multi-tenant SaaS** — auth, RBAC, org isolation.

Promote anything from here to PRD only with a corresponding cut from in-scope.
