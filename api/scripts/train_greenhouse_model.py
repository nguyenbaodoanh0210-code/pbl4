"""Train the greenhouse demo recommendation model from the project workbook.

The source workbook is read with the Python standard library so training does
not require installing an Excel reader into the project's existing venv.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import joblib
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_DIR / "data" / "greenhouse" / "Greenhouse_Demo_Dataset.xlsx"
MODEL_PATH = PROJECT_DIR / "models" / "greenhouse_demo_model.joblib"
REPORT_PATH = PROJECT_DIR / "models" / "greenhouse_demo_training_report.json"

FEATURE_COLUMNS = [
    "Crop_Type",
    "Growth_Stage",
    "Temperature",
    "Humidity",
    "Soil_Moisture",
    "Soil_pH",
    "Nitrogen",
    "Phosphorus",
    "Potassium",
]
CATEGORICAL_COLUMNS = ["Crop_Type", "Growth_Stage"]
NUMERIC_COLUMNS = [column for column in FEATURE_COLUMNS if column not in CATEGORICAL_COLUMNS]
DIAGNOSIS_COLUMN = "Condition_Diagnosis"
ACTION_COLUMN = "Fertilizer_Action"
XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "relationships": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "package": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _column_index(cell_reference: str) -> int:
    letters = re.match(r"[A-Z]+", cell_reference)
    if letters is None:
        raise ValueError(f"Excel cell reference is invalid: {cell_reference}")
    result = 0
    for character in letters.group(0):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _read_workbook(path: Path, sheet_name: str) -> pd.DataFrame:
    """Read a plain-value XLSX worksheet without modifying the workbook."""
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")

    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in members:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(text.text or "" for text in item.findall(".//main:t", XML_NS))
                for item in shared_root.findall("main:si", XML_NS)
            ]

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationship_targets = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in relationships
        }
        sheets = workbook.findall("main:sheets/main:sheet", XML_NS)
        sheet = next((item for item in sheets if item.attrib.get("name") == sheet_name), None)
        if sheet is None:
            available = [item.attrib.get("name", "") for item in sheets]
            raise ValueError(f"Worksheet {sheet_name!r} was not found. Available: {available}")

        relationship_id = sheet.attrib[f"{{{XML_NS['relationships']}}}id"]
        target = relationship_targets[relationship_id]
        worksheet_path = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join("xl", target))
        )
        worksheet = ET.fromstring(archive.read(worksheet_path))

        rows: list[dict[int, object]] = []
        for row in worksheet.findall(".//main:sheetData/main:row", XML_NS):
            values: dict[int, object] = {}
            for cell in row.findall("main:c", XML_NS):
                index = _column_index(cell.attrib["r"])
                cell_type = cell.attrib.get("t")
                value_node = cell.find("main:v", XML_NS)
                if cell_type == "s" and value_node is not None:
                    value: object = shared_strings[int(value_node.text or "0")]
                elif cell_type == "inlineStr":
                    value = "".join(
                        text.text or "" for text in cell.findall(".//main:t", XML_NS)
                    )
                elif value_node is None:
                    value = None
                else:
                    value = value_node.text
                values[index] = value
            if values:
                rows.append(values)

    if len(rows) < 2:
        raise ValueError("Dataset must contain a header row and at least one data row.")

    headers = [rows[0].get(index) for index in range(max(rows[0]) + 1)]
    if any(not isinstance(header, str) or not header.strip() for header in headers):
        raise ValueError("Dataset has a blank or invalid column name.")
    if len(headers) != len(set(headers)):
        raise ValueError("Dataset contains duplicate column names.")

    records = [
        {header: row.get(index) for index, header in enumerate(headers)}
        for row in rows[1:]
    ]
    return pd.DataFrame.from_records(records, columns=headers)


def _make_pipeline(estimator) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("categories", OneHotEncoder(handle_unknown="error"), CATEGORICAL_COLUMNS),
            ("measurements", StandardScaler(), NUMERIC_COLUMNS),
        ],
        remainder="drop",
    )
    return Pipeline([("preprocess", preprocessor), ("classifier", estimator)])


def _validate_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, dict[str, str]]:
    required = FEATURE_COLUMNS + [DIAGNOSIS_COLUMN, ACTION_COLUMN]
    missing_columns = [column for column in required if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    frame = frame[required].copy()
    blank = frame.isna() | frame.apply(
        lambda column: column.map(lambda value: isinstance(value, str) and not value.strip())
    )
    missing_values = {
        column: int(count)
        for column, count in blank.sum().items()
        if count
    }
    if missing_values:
        raise ValueError(f"Dataset has missing required values: {missing_values}")

    for column in CATEGORICAL_COLUMNS + [DIAGNOSIS_COLUMN, ACTION_COLUMN]:
        frame[column] = frame[column].astype(str).str.strip()
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)

    if not frame[NUMERIC_COLUMNS].apply(lambda column: column.map(pd.notna)).all().all():
        raise ValueError("Numeric feature values must be finite numbers.")
    if frame[NUMERIC_COLUMNS].isin([float("inf"), float("-inf")]).any().any():
        raise ValueError("Numeric feature values must be finite numbers.")
    if frame.duplicated().any():
        raise ValueError(f"Dataset contains {int(frame.duplicated().sum())} duplicate rows.")

    action_to_diagnosis: dict[str, str] = {}
    for action, group in frame.groupby(ACTION_COLUMN):
        diagnoses = group[DIAGNOSIS_COLUMN].unique().tolist()
        if len(diagnoses) != 1:
            raise ValueError(
                f"Action {action!r} maps to multiple diagnoses; train a multi-output model instead."
            )
        action_to_diagnosis[action] = diagnoses[0]

    diagnosis_to_action = frame.groupby(DIAGNOSIS_COLUMN)[ACTION_COLUMN].nunique()
    if (diagnosis_to_action != 1).any():
        raise ValueError(
            "A diagnosis maps to multiple fertilizer actions; the single-label model is not suitable."
        )

    features = frame[FEATURE_COLUMNS]
    labels = frame[ACTION_COLUMN]
    if labels.value_counts().min() < 5:
        raise ValueError("Each fertilizer action needs at least five rows for stratified evaluation.")
    return features, labels, action_to_diagnosis


def main() -> None:
    frame = _read_workbook(DATASET_PATH, "Dataset_Demo_Plants")
    features, labels, action_to_diagnosis = _validate_dataset(frame)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    candidates = {
        "ExtraTreesClassifier": ExtraTreesClassifier(
            n_estimators=400,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "RandomForestClassifier": RandomForestClassifier(
            n_estimators=400,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
        "LogisticRegression": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=42,
        ),
    }
    cross_validation = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    candidate_results: dict[str, dict[str, float]] = {}

    for name, estimator in candidates.items():
        scores = cross_validate(
            _make_pipeline(estimator),
            x_train,
            y_train,
            cv=cross_validation,
            scoring={"macro_f1": "f1_macro", "accuracy": "accuracy"},
            n_jobs=1,
            error_score="raise",
        )
        candidate_results[name] = {
            "cv_macro_f1_mean": float(scores["test_macro_f1"].mean()),
            "cv_macro_f1_std": float(scores["test_macro_f1"].std()),
            "cv_accuracy_mean": float(scores["test_accuracy"].mean()),
        }

    selected_name = max(
        candidate_results,
        key=lambda name: (
            candidate_results[name]["cv_macro_f1_mean"],
            candidate_results[name]["cv_accuracy_mean"],
        ),
    )
    selected_estimator = candidates[selected_name]
    evaluation_model = _make_pipeline(selected_estimator)
    evaluation_model.fit(x_train, y_train)
    test_predictions = evaluation_model.predict(x_test)
    class_labels = sorted(labels.unique().tolist())

    test_metrics = {
        "accuracy": float(accuracy_score(y_test, test_predictions)),
        "macro_f1": float(f1_score(y_test, test_predictions, average="macro")),
        "weighted_f1": float(f1_score(y_test, test_predictions, average="weighted")),
        "classification_report": classification_report(
            y_test,
            test_predictions,
            labels=class_labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix_labels": class_labels,
        "confusion_matrix": confusion_matrix(
            y_test, test_predictions, labels=class_labels
        ).tolist(),
    }

    final_model = _make_pipeline(selected_estimator)
    final_model.fit(features, labels)
    category_values = {
        column: sorted(features[column].unique().tolist())
        for column in CATEGORICAL_COLUMNS
    }
    numeric_ranges = {
        column: [float(features[column].min()), float(features[column].max())]
        for column in NUMERIC_COLUMNS
    }
    dataset_sha256 = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    bundle = {
        "artifact_version": 1,
        "model_name": selected_name,
        "model": final_model,
        "feature_columns": FEATURE_COLUMNS,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "numeric_ranges": numeric_ranges,
        "category_values": category_values,
        "diagnosis_by_action": action_to_diagnosis,
        "dataset_sha256": dataset_sha256,
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)

    report = {
        "dataset": DATASET_PATH.name,
        "dataset_sha256": dataset_sha256,
        "sheet": "Dataset_Demo_Plants",
        "row_count": int(len(features)),
        "feature_columns": FEATURE_COLUMNS,
        "target": ACTION_COLUMN,
        "derived_output": DIAGNOSIS_COLUMN,
        "class_count": int(labels.nunique()),
        "class_counts": {str(key): int(value) for key, value in Counter(labels).items()},
        "diagnosis_by_action": action_to_diagnosis,
        "duplicate_rows": int(frame.duplicated().sum()),
        "missing_values": {column: 0 for column in frame.columns},
        "train_test_split": {
            "test_size": 0.2,
            "random_state": 42,
            "stratified_by": ACTION_COLUMN,
            "train_rows": int(len(x_train)),
            "test_rows": int(len(x_test)),
        },
        "cross_validation": {
            "folds": 5,
            "selection_metric": "macro_f1",
            "candidates": candidate_results,
            "selected_model": selected_name,
        },
        "holdout_metrics": test_metrics,
        "software": {"scikit_learn": sklearn.__version__},
        "artifact": MODEL_PATH.name,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "The workbook is named Demo. Evaluation uses a random holdout from this workbook only.",
            "No independent greenhouse trial, agronomist review, or calibration evidence was provided.",
            "Predictions are experimental labels from the dataset and are not validated fertilizer prescriptions.",
            "Numeric inputs outside the observed training range and unknown crop/stage labels should be rejected by the caller.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Rows: {len(features)} | classes: {labels.nunique()} | features: {len(FEATURE_COLUMNS)}")
    print(f"Selected: {selected_name}")
    print(json.dumps(candidate_results, indent=2))
    print(
        "Holdout: "
        + json.dumps(
            {
                "accuracy": test_metrics["accuracy"],
                "macro_f1": test_metrics["macro_f1"],
                "weighted_f1": test_metrics["weighted_f1"],
            },
            indent=2,
        )
    )
    print(f"Model saved to: {MODEL_PATH}")
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
