"""Apply all SQL migrations in api/migrations/ in sorted order safely."""

from pathlib import Path

from app.core.database import engine


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def apply_all_migrations() -> list[str]:
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        raise RuntimeError("Không tìm thấy file migration SQL nào trong api/migrations/.")

    applied: list[str] = []
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        with raw_conn.cursor() as cursor:
            for path in sql_files:
                sql = path.read_text(encoding="utf-8")
                cursor.execute(sql)
                applied.append(path.name)
                print(f"[OK] Applied migration: {path.name}")
    finally:
        raw_conn.close()
    return applied


if __name__ == "__main__":
    applied_files = apply_all_migrations()
    print(f"Hoàn tất áp dụng {len(applied_files)} file migration.")
