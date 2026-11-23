"""Apply reviewed additive migrations, atomically; never seeds or deletes garden data."""
import argparse
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import engine

FILES = ["20261118_outdoor_garden_multimodal_actuators.sql", "20261123_irrigation_feedback.sql"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("Will apply atomically:", ", ".join(FILES))
        print("Use --apply after reviewing migrations. Existing base schema is required.")
        return
    root = Path(__file__).resolve().parents[1] / "migrations"
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
        connection.exec_driver_sql("SET LOCAL statement_timeout = '60s'")
        for name in FILES:
            sql = (root / name).read_text(encoding="utf-8-sig")
            sql = re.sub(r"(?im)^\s*(BEGIN|COMMIT);\s*$", "", sql)
            connection.exec_driver_sql(sql)
            print("Applied:", name)
    print("Committed. No seed or data reset performed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Rolled back:", type(exc).__name__, "SQLSTATE:", getattr(getattr(exc, "orig", None), "pgcode", None))
        raise SystemExit(1)
