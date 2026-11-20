"""Tests for PathPilot database module."""

import pytest
from pathlib import Path
from pathpilot.db import Database, get_db, init_db, get_schema_version, migrate, migration_status, SCHEMA_VERSION
from pathpilot.config import settings
from pathpilot.migrations import get_current_version, get_pending_migrations


class TestDatabase:
    """Test Database class."""

    def test_health_check(self, mock_db):
        assert mock_db.health_check() is True

    def test_get_schema_version(self, mock_db):
        version = mock_db.get_schema_version()
        assert version == SCHEMA_VERSION

    def test_get_stats(self, mock_db):
        stats = mock_db.get_stats()
        assert "env_vars" in stats
        assert "path_entries" in stats
        assert "backups" in stats
        assert "operation_log" in stats
        assert "user_settings" in stats
        assert "schema_version" in stats
        assert "db_size_bytes" in stats
        assert stats["schema_version"] == SCHEMA_VERSION

    def test_execute_fetch(self, mock_db):
        mock_db.execute("INSERT INTO user_settings (key, value) VALUES (?, ?)", ("test_key", "test_value"))
        row = mock_db.fetchone("SELECT value FROM user_settings WHERE key = ?", ("test_key",))
        assert row["value"] == "test_value"

    def test_transaction_commit(self, mock_db):
        with mock_db.transaction() as conn:
            conn.execute("INSERT INTO user_settings (key, value) VALUES (?, ?)", ("tx_key", "tx_value"))
        row = mock_db.fetchone("SELECT value FROM user_settings WHERE key = ?", ("tx_key",))
        assert row["value"] == "tx_value"

    def test_transaction_rollback(self, mock_db):
        try:
            with mock_db.transaction() as conn:
                conn.execute("INSERT INTO user_settings (key, value) VALUES (?, ?)", ("rollback_key", "before"))
                raise ValueError("force rollback")
        except ValueError:
            pass
        row = mock_db.fetchone("SELECT value FROM user_settings WHERE key = ?", ("rollback_key",))
        assert row is None

    def test_close(self, mock_db):
        mock_db.close()
        assert mock_db.health_check() is True

    def test_vacuum(self, mock_db):
        mock_db.vacuum()
        assert mock_db.health_check() is True


class TestDatabaseSingleton:
    """Test database singleton behavior."""

    def test_get_db_returns_same_instance(self, mock_db):
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2


class TestMigrationStatus:
    """Test migration status function."""

    def test_returns_status_dict(self, mock_db):
        status = migration_status()
        assert "current_version" in status
        assert "target_version" in status
        assert "pending_migrations" in status
        assert status["current_version"] == SCHEMA_VERSION
        assert status["target_version"] == SCHEMA_VERSION
        assert status["pending_migrations"] == []

    def test_get_current_version(self, mock_db):
        version = get_current_version(mock_db)
        assert version == SCHEMA_VERSION

    def test_get_pending_migrations(self, mock_db):
        pending = get_pending_migrations(mock_db)
        assert pending == []