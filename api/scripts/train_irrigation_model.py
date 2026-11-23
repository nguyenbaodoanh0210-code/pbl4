"""Offline CatBoost lesson and training. Never connects to a DB, API or pump."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import make_pipeline
import joblib

ROOT = Path(__file__).resolve().parents[1]
CAT = ["crop_type", "growth_stage", "substrate"]
NUM = ["area_sqm", "soil_moisture_pct", "temperature_c", "air_humidity_pct", "light_lux", "irrigation_liters"]
FEATURES = CAT + NUM
TARGET = "soil_moisture_30m_pct"
COLUMNS = ["timestamp", "target_timestamp", "zone_id"] + FEATURES + [TARGET, "data_source"]


def make_demo() -> pd.DataFrame:
    """Artificial observations for learning software, not an agronomic dataset."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(300):
        timestamp = pd.Timestamp("2026-01-01T00:00:00+07:00") + pd.Timedelta(hours=2 * i)
        for zone in range(4):
            moisture = rng.uniform(25, 75)
            temp = rng.uniform(20, 35)
            humidity = rng.uniform(45, 90)
            light = rng.uniform(0, 40000)
            liters = rng.choice([0., 0.1, 0.2, 0.3])
            # This equation is invented solely for an executable beginner lesson.
            target = np.clip(moisture + liters * (12 + zone * 2)
                             - 0.12 * (temp - 20) - light / 40000
                             + rng.normal(0, 0.6), 0, 100)
            rows.append({
                "timestamp": timestamp.isoformat(),
                "target_timestamp": (timestamp + pd.Timedelta(minutes=30)).isoformat(),
                "zone_id": f"demo-{zone}", "crop_type": ["chili", "lettuce"][zone % 2],
                "growth_stage": "vegetative" if i < 150 else "flowering",
                "substrate": ["soil", "coco"][zone // 2],
                "area_sqm": 1.0, "soil_moisture_pct": round(moisture, 3), "temperature_c": round(temp, 3),
                "air_humidity_pct": round(humidity, 3), "light_lux": round(light, 2),
                "irrigation_liters": float(liters), TARGET: round(float(target), 3),
                "data_source": "synthetic",
            })
    return pd.DataFrame(rows, columns=COLUMNS)


def validate(frame: pd.DataFrame, demo: bool) -> pd.DataFrame:
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    frame = frame[COLUMNS].copy()
    if len(frame) < 200:
        raise ValueError("Need at least 200 labeled rows to exercise the split; this is NOT a quality guarantee.")
    for col in CAT + ["zone_id", "data_source"]:
        if frame[col].isna().any():
            raise ValueError(f"Missing value in {col}")
        frame[col] = frame[col].astype(str).str.strip()
        if (frame[col] == "").any():
            raise ValueError(f"Blank value in {col}")
    expected = "synthetic" if demo else "measured"
    if not (frame["data_source"] == expected).all():
        raise ValueError(f"All data_source values must be {expected}; do not relabel synthetic data as measured.")
    for col in ["timestamp", "target_timestamp"]:
        # Require offsets, instead of silently interpreting local times as UTC.
        if not frame[col].astype(str).str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", regex=True).all():
            raise ValueError(f"{col} needs timezone offsets, e.g. 2026-11-22T08:00:00+07:00")
        frame[col] = pd.to_datetime(frame[col], utc=True, errors="raise")
    delay = (frame["target_timestamp"] - frame["timestamp"]).dt.total_seconds() / 60
    if not delay.between(27, 33).all():
        raise ValueError("Target measurements must be 30 minutes later (+/- 3 minutes).")
    if frame.duplicated(["zone_id", "timestamp"]).any():
        raise ValueError("Duplicate zone_id + timestamp observations.")
    for col in NUM + [TARGET]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not np.isfinite(frame[col].to_numpy(dtype=float)).all():
            raise ValueError(f"Missing/infinite measurement in {col}")
    bounds = {"area_sqm": (0.0001, np.inf), "soil_moisture_pct": (0, 100), TARGET: (0, 100),
              "air_humidity_pct": (0, 100), "temperature_c": (-40, 85),
              "light_lux": (0, 200000), "irrigation_liters": (0, np.inf)}
    for col, (low, high) in bounds.items():
        if not frame[col].between(low, high).all():
            raise ValueError(f"Out-of-range measurement in {col}")
    if frame[TARGET].nunique() < 2:
        raise ValueError("Target is constant; collect real varying measurements.")
    return frame.sort_values(["timestamp", "zone_id"]).reset_index(drop=True)


def split_time(frame: pd.DataFrame):
    times = frame["timestamp"].drop_duplicates().sort_values().tolist()
    if len(times) < 20:
        raise ValueError("Need at least 20 distinct observation times.")
    val_start, test_start = times[int(len(times) * .70)], times[int(len(times) * .85)]
    train = frame[(frame.timestamp < val_start) & (frame.target_timestamp < val_start)]
    val = frame[(frame.timestamp >= val_start) & (frame.timestamp < test_start)
                & (frame.target_timestamp < test_start)]
    test = frame[frame.timestamp >= test_start]
    if min(len(train), len(val), len(test)) < 20:
        raise ValueError("Not enough rows after time split and removal of overlapping targets.")
    return train, val, test


def metrics(actual, predicted):
    return {"mae_percentage_points": float(mean_absolute_error(actual, predicted)),
            "rmse_percentage_points": float(np.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Train on clearly labeled artificial data")
    source.add_argument("--csv", type=Path, help="Measured observations in the template format")
    parser.add_argument("--iterations", type=int, default=400)
    args = parser.parse_args()
    if not 10 <= args.iterations <= 3000:
        parser.error("--iterations must be between 10 and 3000")
    frame = make_demo() if args.demo else pd.read_csv(args.csv, encoding="utf-8-sig")
    frame = validate(frame, args.demo)
    train, val, test = split_time(frame)
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = ROOT / "ml_models" / "irrigation" / ("demo" if args.demo else "experiments") / run_name
    out.mkdir(parents=True, exist_ok=False)
    model = CatBoostRegressor(iterations=args.iterations, depth=6, learning_rate=.05,
                              loss_function="RMSE", eval_metric="MAE", random_seed=42,
                              thread_count=2, allow_writing_files=False)
    model.fit(train[FEATURES], train[TARGET], cat_features=CAT,
              eval_set=(val[FEATURES], val[TARGET]), early_stopping_rounds=50,
              use_best_model=True, verbose=100)
    prediction = model.predict(test[FEATURES])
    score = metrics(test[TARGET], prediction)
    forest = make_pipeline(ColumnTransformer([("categories", OneHotEncoder(handle_unknown="ignore"), CAT)],
                                             remainder="passthrough"),
                           RandomForestRegressor(n_estimators=400, min_samples_leaf=2, random_state=42, n_jobs=2))
    forest.fit(train[FEATURES], train[TARGET])
    forest_prediction = forest.predict(test[FEATURES])
    forest_score = metrics(test[TARGET], forest_prediction)
    joblib.dump(forest, out / "random_forest.joblib")
    if not np.allclose(forest_prediction, joblib.load(out / "random_forest.joblib").predict(test[FEATURES])):
        raise RuntimeError("Random Forest round-trip failed")
    baseline = metrics(test[TARGET], test["soil_moisture_pct"])
    model_path = out / "irrigation_model.cbm"
    model.save_model(str(model_path))
    loaded = CatBoostRegressor()
    loaded.load_model(str(model_path))
    if not np.allclose(prediction, loaded.predict(test[FEATURES])):
        raise RuntimeError("Saved model failed prediction round-trip validation")
    report = {
        "model": "CatBoostRegressor", "data_source": "synthetic" if args.demo else "measured",
        "automatic_control_approved": False,
        "target": TARGET, "horizon_minutes": 30, "features": FEATURES,
        "categorical_features": CAT, "best_iteration": model.get_best_iteration(),
        "split": "chronological 70/15/15; overlapping target timestamps purged",
        "split_rows": {"train": len(train), "validation": len(val), "test": len(test)},
        "purged_rows": len(frame) - len(train) - len(val) - len(test),
        "test_metrics": score, "persistence_baseline": baseline,
        "random_forest_test_metrics": forest_score,
        "comparison_protocol": "Same time split, inputs, targets; encoders fitted on training only. CatBoost uses validation early stopping; RF fixed a priori.",
        "random_forest_per_crop_test_mae": {
            str(crop): float(mean_absolute_error(test.loc[test.crop_type == crop, TARGET],
                forest_prediction[(test.crop_type == crop).to_numpy()])) for crop in test.crop_type.unique()
        },
        "beats_persistence_mae": score["mae_percentage_points"] < baseline["mae_percentage_points"],
        "per_crop_test_mae": {
            str(crop): float(mean_absolute_error(test.loc[test.crop_type == crop, TARGET],
                prediction[(test.crop_type == crop).to_numpy()])) for crop in test.crop_type.unique()
        },
        "training_categories": {col: sorted(train[col].unique().tolist()) for col in CAT},
        "training_numeric_ranges": {col: [float(train[col].min()), float(train[col].max())] for col in NUM},
        "feature_importance": dict(zip(FEATURES, model.feature_importances_.tolist())),
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "dataset_sha256": hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest(),
        "limitations": ["Synthetic results are software checks, not field accuracy.",
                        "Observed associations do not establish optimal irrigation or causal effects.",
                        "No held-out-garden validation yet. Do not enable automatic pump control.",
                        "Same calibrated sensors, units and physical zone setup required for comparisons."],
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    results = test[["timestamp", "zone_id", "crop_type", TARGET]].copy()
    results["predicted_moisture_pct"] = prediction
    results["random_forest_moisture_pct"] = forest_prediction
    results.to_csv(out / "test_predictions.csv", index=False)
    if args.demo:
        frame.to_csv(out / "synthetic_training_data.csv", index=False)
    print(json.dumps({"catboost": score, "random_forest": forest_score, "baseline": baseline}, indent=2))
    print(f"Saved: {out}")
    print("EXPERIMENT ONLY. Not connected to API or pump. Synthetic scores are not field accuracy.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Training stopped: {exc}") from None
