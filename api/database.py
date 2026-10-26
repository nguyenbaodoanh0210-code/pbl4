import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name('.env'), override=False)

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Cấu hình chuỗi kết nối Database
# Định dạng: postgresql+psycopg2://user:password@host:port/dbname
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured before starting the API")

# Tạo Engine (Động cơ kết nối)
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

# Tạo Session (Phiên làm việc với database)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class để tạo các Model sau này
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
