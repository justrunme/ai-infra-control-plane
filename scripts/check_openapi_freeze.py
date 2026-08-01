#!/usr/bin/env python3
"""Fail CI when the live OpenAPI document drifts from the frozen contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "control-api"
sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


def main() -> int:
    frozen_path = API_ROOT / "openapi.json"
    if not frozen_path.exists():
        print(f"missing frozen OpenAPI contract: {frozen_path}", file=sys.stderr)
        return 1
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    live = app.openapi()
    # Compare normalized JSON to ignore key ordering noise.
    if json.dumps(frozen, sort_keys=True) != json.dumps(live, sort_keys=True):
        print(
            "OpenAPI contract drift detected. Run: "
            "PYTHONPATH=apps/control-api python scripts/export_openapi.py",
            file=sys.stderr,
        )
        return 1
    print("OpenAPI contract matches frozen openapi.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
