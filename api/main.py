"""Compatibility entry point for `uvicorn main:app` from the api directory."""

from app.main import app

__all__ = ["app"]
