#!/usr/bin/env python3
"""Export the Control API OpenAPI document for contract freeze checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "control-api"
sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


def main() -> int:
    out = API_ROOT / "openapi.json"
    payload = app.openapi()
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
