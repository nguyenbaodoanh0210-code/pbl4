# Model artifacts

Image artifacts are consumed by `../app/ai/disease.py`:

- `plant_disease_model.keras` is the default MobileNetV2 image classifier (224×224). Its matching metadata and class names came with the supplied model; no evaluation report is available.
- `chili_disease_model.keras` is the alternative small CNN (160×160), trained by `../scripts/train_disease_model.py`. Its matching metadata contains the existing evaluation report.
- To select an alternative, configure both `DISEASE_MODEL_PATH` and `DISEASE_METADATA_PATH` together.
- Neither image model requires pH, nitrogen, phosphorus, or potassium measurements.

The retired fertilizer models, their loader, training script, and training report have been removed. The old fertilizer endpoint returns HTTP 410 and cannot perform inference. `legacy/class_names_legacy.json` is an old image-label list, not a fertilizer model.
