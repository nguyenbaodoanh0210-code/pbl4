"""CC BY lettuce data: one-hour moisture prediction, NOT irrigation timing/volume ground truth."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlretrieve
import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parents[1]
URL = "https://data.mendeley.com/public-files/datasets/294zk6k5wf/files/55219eeb-4879-4de3-a410-a0bf15e89e24/file_downloaded"
SHA = "30303a92d7ab7462435d18d496941e9ff4bf43a07b788b85d22b3d8e5055dd83"
FEATURES = ["moisture_pct", "lag_1h_pct", "hour_sin", "hour_cos"]


def main():
    source = ROOT / "data/irrigation/external/lettuce/Soil_Moisture_Values.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        urlretrieve(URL, source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SHA:
        raise ValueError("Source checksum differs")
    raw = pd.read_csv(source)
    times = pd.to_datetime(raw.iloc[:, 0]).dt.tz_localize("Etc/GMT-2").dt.tz_convert("UTC")
    frames = []
    for index, column in enumerate(raw.columns[1:]):
        part = pd.DataFrame({"timestamp": times, "plant_id": index, "moisture_pct": raw[column],
            "lag_1h_pct": raw[column].shift(1), "target": raw[column].shift(-1),
            "target_timestamp": times.shift(-1)})
        delta = (part.target_timestamp - part.timestamp).dt.total_seconds()
        part = part[delta.between(55*60, 65*60)].dropna()
        hour = part.timestamp.dt.hour + part.timestamp.dt.minute / 60
        part["hour_sin"] = np.sin(2*np.pi*hour/24)
        part["hour_cos"] = np.cos(2*np.pi*hour/24)
        frames.append(part)
    data = pd.concat(frames).sort_values(["timestamp", "plant_id"])
    unique = sorted(data.timestamp.unique())
    val_start, test_start = unique[int(len(unique)*.7)], unique[int(len(unique)*.85)]
    train = data[(data.timestamp < val_start) & (data.target_timestamp < val_start)]
    val = data[(data.timestamp >= val_start) & (data.timestamp < test_start) & (data.target_timestamp < test_start)]
    test = data[data.timestamp >= test_start]
    out = ROOT / "ml_models/irrigation/lettuce" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True)
    models = {
        "CatBoost": CatBoostRegressor(iterations=400, depth=4, learning_rate=.03, random_seed=42, thread_count=2, allow_writing_files=False),
        "RandomForest": RandomForestRegressor(n_estimators=400, min_samples_leaf=2, random_state=42, n_jobs=2),
    }
    report = {"source": "https://data.mendeley.com/datasets/294zk6k5wf/2",
        "doi": "10.17632/294zk6k5wf.2", "license": "CC BY 4.0",
        "authors": "Georgios Fevgas; Thomas Lagkas; Vasileios Argyriou; Panagiotis Sarigiannidis",
        "sha256": SHA, "data_source": "measured", "raw_rows": len(raw), "plants": 2,
        "features": FEATURES, "target": "soil moisture at next hourly reading (55–65 minutes)",
        "split": "chronological 70/15/15, target overlap purged; same split for both plants and models",
        "rows": {"train": len(train), "validation": len(val), "test": len(test)},
        "automatic_control_approved": False,
        "limitations": ["Only two lettuces over six days; no independent garden test.",
            "No temperature, light, irrigation amount or rain labels. Cannot train a watering-time or weather model.",
            "One plant normally irrigated, one withheld; treatment is NOT a correct-action label.",
            "The data cannot validate chili irrigation or causal effects of water amount."],
        "metrics": {}}
    pred = test[["timestamp", "plant_id", "target"]].copy()
    predictions = {"Persistence": test.moisture_pct.to_numpy()}
    for name, model in models.items():
        kwargs = dict(eval_set=(val[FEATURES], val.target), early_stopping_rounds=40, verbose=False) if name == "CatBoost" else {}
        model.fit(train[FEATURES], train.target, **kwargs)
        predictions[name] = model.predict(test[FEATURES])
        if name == "CatBoost":
            model.save_model(str(out / "catboost.cbm"))
            loaded = CatBoostRegressor()
            loaded.load_model(str(out / "catboost.cbm"))
        else:
            joblib.dump(model, out / "random_forest.joblib")
            loaded = joblib.load(out / "random_forest.joblib")
        assert np.allclose(predictions[name], loaded.predict(test[FEATURES]))
    for name, values in predictions.items():
        pred[name] = values
        report["metrics"][name] = {"mae_pp": mean_absolute_error(test.target, values),
            "rmse_pp": float(np.sqrt(mean_squared_error(test.target, values))), "r2": r2_score(test.target, values),
            "within_5pp_pct": float(np.mean(np.abs(test.target-values) <= 5)*100)}
    pred.to_csv(out / "test_predictions.csv", index=False)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    print("Saved:", out)


if __name__ == "__main__":
    main()
