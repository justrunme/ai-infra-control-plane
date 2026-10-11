"""NEGATIVE: kind-e2e must not mask Argo CD sync wait failures."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIND_E2E = ROOT / "demo" / "e2e" / "kind-e2e.sh"


def test_kind_e2e_argo_sync_wait_is_not_masked() -> None:
    text = KIND_E2E.read_text(encoding="utf-8")
    lines = text.splitlines()
    wait_lines = [
        line
        for line in lines
        if "wait" in line and "{.status.sync.status}'=Synced" in line
    ]
    assert wait_lines, "expected an Argo CD SyncStatusCode wait in kind-e2e.sh"
    for line in wait_lines:
        assert not line.rstrip().endswith("|| true"), (
            "Argo sync wait must not be masked with || true: "
            f"{line.strip()}"
        )
    assert "exit 1" in text
    assert "describe app ai-control-plane-demo" in text
