"""Operator dashboard HTML entrypoint."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DASHBOARD_HTML_PATH = STATIC_DIR / "index.html"

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML_PATH.read_text()
