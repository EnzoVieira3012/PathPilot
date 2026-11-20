"""Tests for PathPilot migrations module."""

import pytest
from pathpilot.migrations import (
    MIGRATIONS, run_migrations, get_current_version,
    get_pending_migrations, migration_status, normalize_path as mig_normalize_path
)
from pathpilot.db import get_db, Database
from pathpilot.models import Scope
from pathpilot.repositories import UserSettingsRepository


class TestMigrations:
    """Test migration system."""

    def test_migrations_list_structure(self):
        assert len(MIGRATIONS) == 5
        for i, migration in enumerate(MIGRATIONS):
            assert migration["version"] == i + 1
            assert "name" in migration
            assert "up" in migration
            assert callable(migration["up"])

    def test_migration_versions_sequential(self):
        versions = [m["version"] for m in MIGRATIONS]
        assert versions == [1, 2, 3, 4, 5]

    def test_run_migrations_on_fresh_db(self, temp_db_path):
        from pathpilot.db import Database

        db = Database(temp_db_path)
        db.connect()

        run_migrations(db)

        applied = get_current_version(db)
        assert applied == 5

        schema_version = db.get_schema_version()
        assert schema_version == 5

        db.close()

    def test_run_migrations_idempotent(self, temp_db_path):
        from pathpilot.db import Database

        db = Database(temp_db_path)
        db.connect()

        run_migrations(db)
        run_migrations(db)
        run_migrations(db)

        applied = get_current_version(db)
        assert applied == 5

        db.close()

    def test_get_current_version(self, mock_db):
        applied = get_current_version(mock_db)
        assert applied == 5

    def test_seed_initial_data_via_migration(self, mock_db):
        repo = UserSettingsRepository()
        settings = repo.get_all()

        assert "backup.schedule.enabled" in settings
        assert "backup.schedule.interval_hours" in settings
        assert "backup.schedule.max_backups" in settings
        assert "backup.auto.enabled" in settings
        assert "backup.auto.max_backups" in settings
        assert "backup.auto.max_age_days" in settings
        assert "crypto.hmac_enabled" in settings

        assert settings["backup.schedule.enabled"] == "false"
        assert settings["backup.schedule.interval_hours"] == "24"
        assert settings["backup.schedule.max_backups"] == "30"
        assert settings["backup.auto.enabled"] == "false"
        assert settings["backup.auto.max_backups"] == "10"
        assert settings["backup.auto.max_age_days"] == "30"
        assert settings["crypto.hmac_enabled"] == "true"

    def test_migration_1_creates_core_tables(self, temp_db_path):
        from pathpilot.db import Database
        db = Database(temp_db_path)
        db.connect()

        # Run only first migration
        MIGRATIONS[0]["up"](db)

        # Check tables exist
        tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {t["name"] for t in tables}
        assert "schema_version" in table_names
        assert "env_vars" in table_names
        assert "path_entries" in table_names
        assert "backups" in table_names
        assert "operation_log" in table_names
        assert "user_settings" in table_names

        db.close()

    def test_migration_2_adds_indexes(self, temp_db_path):
        from pathpilot.db import Database
        db = Database(temp_db_path)
        db.connect()

        MIGRATIONS[0]["up"](db)
        MIGRATIONS[1]["up"](db)

        indexes = db.fetchall("SELECT name FROM sqlite_master WHERE type='index'")
        index_names = {i["name"] for i in indexes}
        assert "idx_env_vars_name_scope" in index_names
        assert "idx_path_entries_path_scope" in index_names
        assert "idx_backups_scope_created" in index_names
        assert "idx_operation_log_scope_created" in index_names

        db.close()

    def test_migration_3_adds_columns(self, temp_db_path):
        from pathpilot.db import Database
        db = Database(temp_db_path)
        db.connect()

        MIGRATIONS[0]["up"](db)
        MIGRATIONS[1]["up"](db)
        MIGRATIONS[2]["up"](db)

        cols = db.fetchall("PRAGMA table_info(env_vars)")
        col_names = {c["name"] for c in cols}
        assert "description" in col_names
        assert "encrypted" in col_names

        cols = db.fetchall("PRAGMA table_info(path_entries)")
        col_names = {c["name"] for c in cols}
        assert "description" in col_names
        assert "position" in col_names

        cols = db.fetchall("PRAGMA table_info(backups)")
        col_names = {c["name"] for c in cols}
        assert "description" in col_names
        assert "checksum" in col_names

        db.close()

    def test_migration_4_adds_hmac_column(self, temp_db_path):
        from pathpilot.db import Database
        db = Database(temp_db_path)
        db.connect()

        for m in MIGRATIONS[:4]:
            m["up"](db)

        cols = db.fetchall("PRAGMA table_info(operation_log)")
        col_names = {c["name"] for c in cols}
        assert "hmac_signature" in col_names

        db.close()

    def test_migration_5_adds_triggers(self, temp_db_path):
        from pathpilot.db import Database
        db = Database(temp_db_path)
        db.connect()

        for m in MIGRATIONS:
            m["up"](db)

        triggers = db.fetchall("SELECT name FROM sqlite_master WHERE type='trigger'")
        trigger_names = {t["name"] for t in triggers}
        assert "trg_env_vars_updated_at" in trigger_names
        assert "trg_path_entries_updated_at" in trigger_names
        assert "trg_backups_updated_at" in trigger_names
        assert "trg_operation_log_updated_at" in trigger_names
        assert "trg_user_settings_updated_at" in trigger_names

        db.close()

    def test_get_pending_migrations(self, mock_db):
        pending = get_pending_migrations(mock_db)
        assert pending == []

    def test_migration_status(self, mock_db):
        status = migration_status()
        assert "current_version" in status
        assert "target_version" in status
        assert "pending_migrations" in status
        assert status["current_version"] == 5
        assert status["target_version"] == 5
        assert status["pending_migrations"] == []

    def test_normalize_path_in_migrations(self):
        assert mig_normalize_path(r"C:\Test") == r"C:\Test"
        assert mig_normalize_path(r"C:\\Test\\") == r"C:\Test"
        assert mig_normalize_path("C:/Test") == r"C:\Test"