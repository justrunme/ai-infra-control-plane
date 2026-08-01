"""Schema migration ledger correctness (SQLite + optional Postgres)."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.db_schema import EXPECTED_MIGRATION_VERSIONS
from app.decision_store import DecisionStore

POSTGRES_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", ""),
)


def test_sqlite_migration_ledger_complete_and_idempotent(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    store = DecisionStore(db_url)
    try:
        assert store.list_schema_migrations() == EXPECTED_MIGRATION_VERSIONS
        store.assert_migrations_current()
    finally:
        store.close()

    reopened = DecisionStore(db_url)
    try:
        assert reopened.list_schema_migrations() == EXPECTED_MIGRATION_VERSIONS
        decision_id = reopened.create_decision(final_verdict="allow", team="platform")
        assert reopened.get_decision(decision_id) is not None
    finally:
        reopened.close()


def test_sqlite_concurrent_store_startup(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'concurrent.db'}"
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _boot() -> set[str]:
        barrier.wait(timeout=10)
        store = DecisionStore(db_url)
        try:
            return store.list_schema_migrations()
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_boot), pool.submit(_boot)]
        for future in futures:
            try:
                assert future.result(timeout=30) == EXPECTED_MIGRATION_VERSIONS
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    assert not errors


@pytest.mark.skipif(
    not POSTGRES_URL.startswith(("postgres://", "postgresql://")),
    reason="Postgres TEST_DATABASE_URL/DATABASE_URL not configured",
)
def test_postgres_migration_ledger_concurrent_and_idempotent() -> None:
    # Isolate this test on a disposable schema via search_path would be ideal;
    # CI uses a dedicated database so truncate the ledger + recreate is enough.
    first = DecisionStore(POSTGRES_URL)
    try:
        assert first.list_schema_migrations() == EXPECTED_MIGRATION_VERSIONS
    finally:
        first.close()

    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _boot() -> set[str]:
        barrier.wait(timeout=10)
        store = DecisionStore(POSTGRES_URL)
        try:
            store.assert_migrations_current()
            return store.list_schema_migrations()
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_boot), pool.submit(_boot)]
        for future in futures:
            try:
                assert future.result(timeout=60) == EXPECTED_MIGRATION_VERSIONS
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    assert not errors

    restarted = DecisionStore(POSTGRES_URL)
    try:
        assert restarted.list_schema_migrations() == EXPECTED_MIGRATION_VERSIONS
        restarted.assert_migrations_current()
    finally:
        restarted.close()
