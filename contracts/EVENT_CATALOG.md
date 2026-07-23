# RAIP Event Catalog

V9 does not publish runtime events. Its offline document lifecycle is:

1. `HISTORICAL_REPLAY_CREATED`
2. `SCENARIO_SUMMARY_CREATED`
3. `COUNTERFACTUAL_ANALYZED` (embedded in validation report)
4. `VALIDATION_REPORT_CREATED`
5. `VALIDATION_REPOSITORY_APPENDED`

These are audit lifecycle names only; they cannot trigger execution, deployment, or learning.
