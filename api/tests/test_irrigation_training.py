"""Data integrity checks for offline training; no database or hardware imports."""
import unittest
import pandas as pd
from scripts.train_irrigation_model import make_demo, validate, split_time, FEATURES, TARGET


class IrrigationTrainingTests(unittest.TestCase):
    def test_synthetic_cannot_be_accepted_as_measured(self):
        with self.assertRaisesRegex(ValueError, "data_source"):
            validate(make_demo(), demo=False)

    def test_missing_future_measurement_is_rejected(self):
        frame = make_demo()
        frame.loc[0, TARGET] = float("nan")
        with self.assertRaisesRegex(ValueError, "Missing/infinite"):
            validate(frame, demo=True)

    def test_wrong_horizon_is_rejected(self):
        frame = make_demo()
        frame.loc[0, "target_timestamp"] = frame.loc[0, "timestamp"]
        with self.assertRaisesRegex(ValueError, "30 minutes"):
            validate(frame, demo=True)

    def test_duplicate_zone_timestamp_is_rejected(self):
        frame = make_demo()
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate(frame, demo=True)

    def test_split_purges_overlapping_labels(self):
        frame = validate(make_demo(), demo=True)
        times = pd.date_range("2026-01-01", periods=300, freq="20min", tz="UTC")
        frame["timestamp"] = times.repeat(4)
        frame["target_timestamp"] = frame.timestamp + pd.Timedelta(minutes=30)
        train, val, test = split_time(frame)
        self.assertLess(train.target_timestamp.max(), val.timestamp.min())
        self.assertLess(val.target_timestamp.max(), test.timestamp.min())
        self.assertLess(len(train) + len(val) + len(test), len(frame))
        self.assertNotIn(TARGET, FEATURES)
        self.assertNotIn("target_timestamp", FEATURES)


if __name__ == "__main__":
    unittest.main()
