"""FastAPI MVC entrypoint — wires global handlers, health check, and controllers."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import (
    OperationalError,
    SQLAlchemyError,
    TimeoutError as DatabaseTimeoutError,
)

from .controllers import ALL_ROUTERS
from .core.database import engine

app = FastAPI(title="Smart Outdoor Garden API (MVC)", version="2.0.0")
logger = logging.getLogger(__name__)

# Allow cross-origin requests for other machines/phones in the LAN and hardware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    # Log only exception category and SQLSTATE, never credentials or user data.
    sqlstate = getattr(getattr(exc, "orig", None), "pgcode", None)
    logger.error(
        "Database request failed: category=%s sqlstate=%s",
        type(exc).__name__,
        sqlstate,
    )
    if isinstance(exc, (OperationalError, DatabaseTimeoutError)):
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Không kết nối được cơ sở dữ liệu. Quản trị viên cần kiểm tra DATABASE_URL và dịch vụ PostgreSQL.",
                "code": "DATABASE_UNAVAILABLE",
            },
        )
    if sqlstate in {"42P01", "42703", "3F000"}:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Cấu trúc cơ sở dữ liệu chưa sẵn sàng. Quản trị viên cần kiểm tra và áp dụng migration.",
                "code": "DATABASE_SCHEMA_NOT_READY",
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Không thể xử lý dữ liệu lúc này. Vui lòng liên hệ quản trị viên.",
            "code": "DATABASE_ERROR",
        },
    )


@app.get("/health", tags=["health"])
def health(check_database: bool = False):
    if check_database:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    return {"status": "ok"}


for router in ALL_ROUTERS:
    app.include_router(router)

# Mount frontend static files so opening http://localhost:8000 serves the UI directly
import os
from fastapi.staticfiles import StaticFiles

_frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
