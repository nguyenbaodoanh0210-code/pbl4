"""Validate PostgreSQL credentials before saving the project's local DATABASE_URL."""

import argparse
import getpass
import json
import os
from pathlib import Path
import warnings

from dotenv import dotenv_values, set_key
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PLACEHOLDERS = {"USER", "PASSWORD", "TEN_USER", "MAT_KHAU"}


def configured_url() -> URL | None:
    values = dotenv_values(ENV_PATH, interpolate=False)
    raw = os.environ.get("DATABASE_URL") or values.get("DATABASE_URL")
    if not raw:
        return None
    try:
        url = make_url(raw)
    except (ValueError, SQLAlchemyError):
        raise ValueError("DATABASE_URL không đúng định dạng URL PostgreSQL.") from None
    if url.drivername not in {"postgresql", "postgresql+psycopg2"}:
        raise ValueError("Dự án này sử dụng PostgreSQL qua psycopg2.")
    return url.set(drivername="postgresql+psycopg2")


def connection_defaults() -> URL:
    existing = configured_url()
    if existing and existing.username and existing.username not in PLACEHOLDERS:
        return existing
    for directory in (ROOT, ROOT.parent):
        settings = directory / ".vscode" / "settings.json"
        if not settings.is_file():
            continue
        try:
            saved = json.loads(settings.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            continue
        connections = [
            item for item in saved.get("sqltools.connections", [])
            if item.get("driver") == "PostgreSQL"
        ]
        if len(connections) != 1:
            continue
        item = connections[0]
        if not all(item.get(key) for key in ("username", "server", "database")):
            continue
        return URL.create(
            "postgresql+psycopg2",
            username=item["username"],
            host=item["server"],
            port=int(item.get("port", 5432)),
            database=item["database"],
        )
    raise ValueError("Chưa có kết nối PostgreSQL duy nhất trong cấu hình SQLTools của workspace.")


def check_connection(url: URL) -> bool:
    engine = create_engine(
        url, connect_args={"connect_timeout": 5}, poolclass=NullPool,
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Inspect the error locally, but never print its DSN, username or password.
        message = str(getattr(exc, "orig", exc)).casefold()
        sqlstate = getattr(getattr(exc, "orig", None), "pgcode", None)
        if sqlstate in {"28P01", "28000"} or "password authentication failed" in message:
            print("PostgreSQL từ chối xác thực. Kiểm tra mật khẩu của tài khoản SQLTools.")
        elif "no password supplied" in message:
            print("Kết nối PostgreSQL còn thiếu mật khẩu.")
        elif sqlstate == "3D000" or ("database" in message and "does not exist" in message):
            print("Database được cấu hình chưa tồn tại trên PostgreSQL.")
        else:
            print("Không kết nối được PostgreSQL. Kiểm tra dịch vụ, host, port và quyền truy cập.")
        return False
    finally:
        engine.dispose()
    print("Đã kiểm tra SELECT 1: kết nối PostgreSQL thành công.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra cấu hình hiện tại, không sửa file.")
    args = parser.parse_args()
    try:
        if args.check:
            url = configured_url()
            if url is None:
                print("Chưa cấu hình DATABASE_URL.")
                return 2
            return 0 if check_connection(url) else 2

        inherited = os.environ.get("DATABASE_URL")
        local = dotenv_values(ENV_PATH, interpolate=False).get("DATABASE_URL")
        if inherited and inherited != local:
            print("Terminal đang đặt DATABASE_URL khác .env. Hãy mở terminal mới hoặc bỏ biến này trong terminal rồi chạy lại.")
            return 2
        if not ENV_PATH.is_file():
            print("Chưa có .env. Tạo từ .env.example trước khi cấu hình database.")
            return 2
        original = ENV_PATH.read_bytes()
        defaults = connection_defaults()
        print("Dùng thông tin kết nối PostgreSQL đã cấu hình trong workspace.")
        print("Nhập mật khẩu PostgreSQL trong terminal; ký tự mật khẩu sẽ không hiển thị.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Mật khẩu PostgreSQL: ")
        if not password:
            print("Mật khẩu trống. Cấu hình được giữ nguyên.")
            return 2
        candidate = defaults.set(password=password)
        if not check_connection(candidate):
            print("Kết nối chưa hợp lệ; .env được giữ nguyên.")
            return 2
        if ENV_PATH.read_bytes() != original:
            print(".env đã được thay đổi trong lúc nhập mật khẩu. Chạy lại để tránh ghi đè cấu hình mới.")
            return 2
        result = set_key(
            str(ENV_PATH), "DATABASE_URL", candidate.render_as_string(hide_password=False),
            quote_mode="always", encoding="utf-8",
        )
        if not result[0]:
            print("Không thể lưu DATABASE_URL vào .env.")
            return 2
        print("Đã lưu DATABASE_URL vào .env. Các cấu hình khác được giữ nguyên.")
        print("Khởi động lại API để nạp kết nối mới, sau đó kiểm tra /health?check_database=true.")
        return 0
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("\nCần nhập mật khẩu trong terminal tương tác có ẩn ký tự. Cấu hình được giữ nguyên.")
        return 2
    except (OSError, ValueError, SQLAlchemyError):
        print("Không thể đọc, kiểm tra hoặc lưu cấu hình PostgreSQL. Không hiển thị nội dung lỗi chứa thông tin kết nối.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
