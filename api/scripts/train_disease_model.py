"""Train a small CNN from the local Chili Plant Disease image folders.

No pretrained weights or network downloads are used. TensorFlow is an optional
dependency listed separately from the standard API requirements.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_DIR / "data" / "chili_plant_disease"
MODEL_PATH = PROJECT_DIR / "models" / "chili_disease_model.keras"
METADATA_PATH = PROJECT_DIR / "models" / "chili_disease_model_metadata.json"
SPLITS = ("train", "val", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
IMAGE_SIZE = 160
BATCH_SIZE = 16


def discover_class_directories(split_dir: Path) -> dict[str, Path]:
    """Find label folders by image files, including nested disease folders."""
    class_directories: dict[str, Path] = {}
    for path in sorted(item for item in split_dir.rglob("*") if item.is_dir()):
        direct_images = [
            item
            for item in path.iterdir()
            if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not direct_images:
            continue
        if path.name in class_directories:
            raise ValueError(
                f"Ambiguous label directory name {path.name!r} in {split_dir}"
            )
        class_directories[path.name] = path
    return class_directories


def collect_split(
    split: str, class_names: list[str], class_directories: dict[str, Path]
) -> tuple[list[str], list[int]]:
    paths: list[str] = []
    labels: list[int] = []
    for label, class_name in enumerate(class_names):
        class_dir = class_directories.get(class_name)
        if class_dir is None:
            raise ValueError(f"Missing class directory: {split}/{class_name}")
        images = sorted(
            path
            for path in class_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not images:
            raise ValueError(f"No JPEG images found for {split}/{class_name}")
        paths.extend(str(path) for path in images)
        labels.extend([label] * len(images))
    return paths, labels


def make_dataset(tf, paths: list[str], labels: list[int], training: bool):
    dataset = tf.data.Dataset.from_tensor_slices((paths, labels))

    def decode_image(path, label):
        image = tf.io.decode_jpeg(tf.io.read_file(path), channels=3)
        image = tf.image.resize(image, (IMAGE_SIZE, IMAGE_SIZE), antialias=True)
        return image, label

    dataset = dataset.map(decode_image, num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        dataset = dataset.shuffle(
            len(paths), seed=42, reshuffle_each_iteration=True
        )
    return dataset.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)


def build_model(tf, class_count: int):
    augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal"),
            tf.keras.layers.RandomRotation(0.08),
            tf.keras.layers.RandomZoom(0.1),
        ],
        name="augmentation",
    )
    inputs = tf.keras.Input(shape=(IMAGE_SIZE, IMAGE_SIZE, 3))
    x = augmentation(inputs)
    x = tf.keras.layers.Rescaling(1.0 / 255)(x)
    for filters in (32, 64, 128):
        x = tf.keras.layers.Conv2D(filters, 3, padding="same", activation="relu")(x)
        x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(128, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.35)(x)
    outputs = tf.keras.layers.Dense(class_count, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs, name="chili_disease_cnn")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 200:
        parser.error("--epochs must be between 1 and 200")

    try:
        import numpy as np
        import tensorflow as tf
        from sklearn.metrics import classification_report, confusion_matrix
    except ImportError as exc:
        print(
            "Training requires TensorFlow and the existing scikit-learn package. "
            "This script does not install dependencies. See requirements-vision.txt."
        )
        print(f"Missing dependency: {exc.name}")
        return 2

    if not DATASET_DIR.is_dir():
        raise FileNotFoundError(f"Image dataset not found: {DATASET_DIR}")

    split_dirs = [DATASET_DIR / split for split in SPLITS]
    if any(not path.is_dir() for path in split_dirs):
        raise ValueError("Dataset must contain train, val, and test directories")
    class_directories = {
        split: discover_class_directories(DATASET_DIR / split) for split in SPLITS
    }
    split_classes = [set(class_directories[split]) for split in SPLITS]
    if not split_classes[0] or any(
        classes != split_classes[0] for classes in split_classes[1:]
    ):
        raise ValueError("Train, val, and test must contain the same class folders")

    class_names = sorted(split_classes[0])
    split_data = {
        split: collect_split(split, class_names, class_directories[split])
        for split in SPLITS
    }
    counts = {
        split: dict(Counter(class_names[label] for label in labels))
        for split, (_, labels) in split_data.items()
    }
    if any(count == 0 for split_counts in counts.values() for count in split_counts.values()):
        raise ValueError("Every class needs images in every split")

    random.seed(42)
    np.random.seed(42)
    tf.keras.utils.set_random_seed(42)
    train_ds = make_dataset(tf, *split_data["train"], training=True)
    val_ds = make_dataset(tf, *split_data["val"], training=False)
    test_ds = make_dataset(tf, *split_data["test"], training=False)

    model = build_model(tf, len(class_names))
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        shuffle=False,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=7, restore_best_weights=True
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=3, min_lr=1e-6
            ),
        ],
        verbose=2,
    )

    probabilities = model.predict(test_ds, verbose=0)
    y_true = np.concatenate([labels.numpy() for _, labels in test_ds])
    y_predicted = probabilities.argmax(axis=1)
    report = classification_report(
        y_true,
        y_predicted,
        labels=list(range(len(class_names))),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_predicted).tolist()
    test_metrics = model.evaluate(test_ds, verbose=0, return_dict=True)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    metadata = {
        "dataset": DATASET_DIR.name,
        "class_names": class_names,
        "image_size": IMAGE_SIZE,
        "split_counts": counts,
        "test_metrics": {
            key: float(value) for key, value in test_metrics.items()
        },
        "classification_report": report,
        "confusion_matrix": matrix,
        "confusion_matrix_labels": class_names,
        "model": MODEL_PATH.name,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "This is a small demo dataset with only ten test images per class.",
            "The model is trained from scratch without pretrained weights.",
            "Scores are experimental and are not a verified plant-health diagnosis.",
        ],
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Model saved to: {MODEL_PATH}")
    print(f"Training report saved to: {METADATA_PATH}")
    print(json.dumps(metadata["test_metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
