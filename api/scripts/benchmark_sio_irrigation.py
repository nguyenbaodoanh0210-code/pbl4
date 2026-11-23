"""Offline experiment on the externally authored SIO synthetic dataset.

Different target from train_irrigation_model: irrigation Yes/No and water depth
in mm, NOT future soil moisture. No database, hardware or runtime integration.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlretrieve

import catboost
from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             mean_absolute_error, mean_squared_error, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import make_pipeline
import joblib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/irrigation/external/sio/irrigation_dataset.csv"
EXPECTED_HASH = "607c30a69e55bd8110b43a0bdff6ab7ceB86965de43b51700803683848ced14b".lower()
CAT = ["Crop_Type", "Growth_Stage"]
AVAILABLE = CAT + ["Soil_Moisture_pct", "Temperature_C", "Humidity_pct"]
CONTEXT = AVAILABLE + ["Rainfall_7day_mm", "Solar_Radiation_MJm2"]


def main():
    if not SOURCE.exists():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        url = "https://raw.githubusercontent.com/Abijith-U0245/SIO---Smart-Irrigation-Optimization/fb421ab52d070cb9dce6c2db28d0f95fcec96105/irrigation_dataset.csv"
        urlretrieve(url, SOURCE)
        (SOURCE.parent / "source.json").write_text(json.dumps({"url": url, "kind": "external_synthetic",
            "license": "No explicit license observed; local research only"}), encoding="utf8")
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED_HASH:
        raise ValueError("Source differs from reviewed snapshot. Review schema/provenance before training.")
    data = pd.read_csv(SOURCE)
    if data.isna().any().any() or data[AVAILABLE].duplicated().any():
        raise ValueError("Missing values or repeated feature rows require review before splitting.")
    if set(data.Irrigate) != {"Yes", "No"}:
        raise ValueError("Unexpected class labels")
    y = (data.Irrigate == "Yes").astype(int)
    train_idx, rest_idx = train_test_split(data.index, test_size=.30, random_state=42, stratify=y)
    val_idx, test_idx = train_test_split(rest_idx, test_size=.50, random_state=42, stratify=y.loc[rest_idx])
    out = ROOT / "ml_models/irrigation/external_sio" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    split = pd.Series("train", index=data.index)
    split.loc[val_idx], split.loc[test_idx] = "validation", "test"
    pd.DataFrame({"source_id": data.ID, "split": split}).to_csv(out / "split_assignments.csv", index=False)
    # Keep the original download intact; this derived file contains no pH/N/P/K.
    data[CONTEXT + ["Water_Requirement_mm", "Irrigate"]].to_csv(out / "dataset_without_ph.csv", index=False)
    majority = int(y.loc[train_idx].mode().iloc[0])
    median_water = float(data.loc[train_idx, "Water_Requirement_mm"].median())
    report = {
        "dataset": "SIO custom synthetic irrigation dataset", "data_source": "external_synthetic",
        "source": json.loads((SOURCE.parent / "source.json").read_text(encoding="utf-8-sig")),
        "catboost_version": catboost.__version__, "rows": len(data),
        "split": {"method": "random stratified 70/15/15, seed=42; no timestamps supplied",
                  "train": len(train_idx), "validation": len(val_idx), "test": len(test_idx)},
        "automatic_control_approved": False,
        "excluded": ["ID", "Soil_pH", "other target columns from either model's inputs"],
        "crop_counts": data.Crop_Type.value_counts().to_dict(),
        "baseline": {"majority_accuracy_pct": 100 * accuracy_score(y.loc[test_idx], np.full(len(test_idx), majority)),
                     "median_water_mae_mm": mean_absolute_error(data.loc[test_idx, "Water_Requirement_mm"],
                                                                 np.full(len(test_idx), median_water))},
        "experiments": {},
        "limitations": [
            "Accuracy measures reproduction of synthetic labels, not field irrigation correctness.",
            "No timestamp or moisture-after-30-min target; not comparable to the previous moisture model.",
            "No chili or lettuce rows in this dataset. No evidence of transfer to the project's crops.",
            "Solar radiation MJ/m2 cannot be substituted directly with LDR lux.",
            "Unknown label-generation details; removing pH as an input does not establish pH-independent ground truth.",
            "No explicit source license observed. Download and outputs kept local, not redistributed.",
        ],
    }
    for name, features in [("available_inputs", AVAILABLE), ("with_weather_context", CONTEXT)]:
        train, val, test = (data.loc[idx, features] for idx in (train_idx, val_idx, test_idx))
        config = dict(iterations=500, depth=6, learning_rate=.05, random_seed=42,
                      thread_count=2, allow_writing_files=False)
        classifier = CatBoostClassifier(**config, loss_function="Logloss", eval_metric="Logloss")
        classifier.fit(train, y.loc[train_idx], cat_features=CAT, eval_set=(val, y.loc[val_idx]),
                       early_stopping_rounds=50, verbose=False)
        regressor = CatBoostRegressor(**config, loss_function="RMSE", eval_metric="MAE")
        regressor.fit(train, data.loc[train_idx, "Water_Requirement_mm"], cat_features=CAT,
                      eval_set=(val, data.loc[val_idx, "Water_Requirement_mm"]),
                      early_stopping_rounds=50, verbose=False)
        probabilities = classifier.predict_proba(test)[:, 1]
        decisions = (probabilities >= .5).astype(int)
        water = regressor.predict(test)
        actual = data.loc[test_idx, "Water_Requirement_mm"]
        def rf_pipeline(estimator):
            return make_pipeline(ColumnTransformer([("categories", OneHotEncoder(handle_unknown="ignore"), CAT)],
                                                   remainder="passthrough"), estimator)
        rf_classifier = rf_pipeline(RandomForestClassifier(n_estimators=400, min_samples_leaf=2, random_state=42, n_jobs=2))
        rf_regressor = rf_pipeline(RandomForestRegressor(n_estimators=400, min_samples_leaf=2, random_state=42, n_jobs=2))
        rf_classifier.fit(train, y.loc[train_idx])
        rf_regressor.fit(train, data.loc[train_idx, "Water_Requirement_mm"])
        rf_decisions, rf_water = rf_classifier.predict(test), rf_regressor.predict(test)
        stats_rf = {
            "classifier_accuracy_pct": 100 * accuracy_score(y.loc[test_idx], rf_decisions),
            "water_mae_mm": mean_absolute_error(actual, rf_water),
            "water_rmse_mm": float(np.sqrt(mean_squared_error(actual, rf_water))),
            "water_r2": r2_score(actual, rf_water),
            "confusion_matrix": confusion_matrix(y.loc[test_idx], rf_decisions, labels=[0, 1]).tolist(),
        }
        for suffix, estimator in [("decision", rf_classifier), ("water", rf_regressor)]:
            path = out / f"{name}_rf_{suffix}.joblib"
            joblib.dump(estimator, path)
            if not np.allclose(estimator.predict(test), joblib.load(path).predict(test)):
                raise RuntimeError("RF save/load mismatch")
        error = np.abs(water - actual.to_numpy())
        stats = {
            "features": features, "classifier_accuracy_pct": 100 * accuracy_score(y.loc[test_idx], decisions),
            "correct": int(np.sum(y.loc[test_idx].to_numpy() == decisions)), "test_count": len(test_idx),
            "classification_report": classification_report(y.loc[test_idx], decisions, labels=[0, 1],
                target_names=["No", "Yes"], output_dict=True, zero_division=0),
            "confusion_matrix_labels": ["No", "Yes"],
            "confusion_matrix": confusion_matrix(y.loc[test_idx], decisions, labels=[0, 1]).tolist(),
            "water_mae_mm": mean_absolute_error(actual, water),
            "water_rmse_mm": float(np.sqrt(mean_squared_error(actual, water))),
            "water_r2": r2_score(actual, water),
            "water_within_5mm_pct": float(100 * np.mean(error <= 5)),
            "water_within_10mm_pct": float(100 * np.mean(error <= 10)),
            "negative_water_predictions": int(np.sum(water < 0)),
        }
        for suffix, model, cls in [("decision", classifier, CatBoostClassifier), ("water", regressor, CatBoostRegressor)]:
            artifact = out / f"{name}_{suffix}.cbm"
            model.save_model(str(artifact))
            loaded = cls()
            loaded.load_model(str(artifact))
            if not np.allclose(model.predict(test), loaded.predict(test)):
                raise RuntimeError("Model save/load verification failed")
        predictions = data.loc[test_idx, ["ID", "Crop_Type", "Irrigate", "Water_Requirement_mm"]].copy()
        predictions["predicted_irrigate"] = np.where(decisions, "Yes", "No")
        predictions["predicted_water_mm"] = water
        predictions.to_csv(out / f"{name}_test_predictions.csv", index=False)
        report["experiments"][name] = stats
        report["experiments"][name]["random_forest"] = stats_rf
        print("random_forest", name, json.dumps(stats_rf))
        print(name, json.dumps({k: stats[k] for k in ["classifier_accuracy_pct", "correct", "water_mae_mm", "water_within_5mm_pct"]}))
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", out)
    print("External synthetic experiment only; no pump control or production approval.")


if __name__ == "__main__":
    main()
