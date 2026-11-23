# Research artifacts — not approved for pump control

Both CatBoost and Random Forest were trained with the same features and held-out samples within each experiment. The API does not load these files. `automatic_control_approved` is false for every experiment.

- `synthetic`: project-generated 1,200-row demonstration, moisture after 30 minutes. Crop names include chili and lettuce but the labels come from a synthetic equation.
- `lettuce`: measured two-plant, six-day study, moisture after one hour. Both trees performed much worse than persistence on the chronological test. Do not deploy these weights.
- SIO weights/data stay local because no explicit source license was found. The script and metrics are included for reproduction.

The Random Forest artifacts are joblib-compressed. Only load trusted artifacts; pickle/joblib can execute code. `manifest.json` records SHA-256 and exact training-library versions. For exact reproduction use those versions in a separate training environment. The CatBoost weights were round-trip checked by the training scripts; compression does not retrain Random Forest.

Lettuce attribution: Georgios Fevgas, Thomas Lagkas, Vasileios Argyriou, Panagiotis Sarigiannidis, dataset v2, DOI [10.17632/294zk6k5wf.2](https://data.mendeley.com/datasets/294zk6k5wf/2), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Transformations: hourly lag features, cyclical hour, next-hour target, chronological split and model fitting. Authors do not endorse these models. The CSV download script pins its SHA-256; raw images were not downloaded.

Full findings and commands: [report](../../../docs/reports/2026-11-23-irrigation/REPORT.md).
