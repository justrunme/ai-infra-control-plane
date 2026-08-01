"""SQLite decision store must tolerate concurrent writers."""

from __future__ import annotations

import threading
from pathlib import Path

from app.decision_store import DecisionStore


def test_concurrent_create_decision(tmp_path: Path) -> None:
    db_path = tmp_path / "concurrent.db"
    store = DecisionStore(f"sqlite:///{db_path}")
    errors: list[BaseException] = []
    created: list[str] = []
    barrier = threading.Barrier(20)

    def worker(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            decision_id = store.create_decision(
                final_verdict="allow",
                request_id=f"req-{index}",
                team="platform",
                environment="development",
            )
            created.append(decision_id)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    store.close()
    assert errors == []
    assert len(created) == 20
    assert len(set(created)) == 20
