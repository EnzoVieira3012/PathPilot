"""Tests for PathPilot repositories module."""

import pytest
from pathpilot.models import Scope, PathEntry, EnvVar, Backup, OperationLog, OperationType, OperationStatus
from pathpilot.repositories import (
    PathEntryRepository, EnvVarRepository, BackupRepository,
    OperationLogRepository, UserSettingsRepository
)


class TestPathEntryRepository:
    """Test PathEntryRepository."""

    def test_create_and_get(self, mock_db):
        repo = PathEntryRepository()
        entry = PathEntry(path=r"C:\Test", scope=Scope.USER, description="Test path")
        created = repo.create(entry)
        assert created.id is not None
        assert created.path == r"C:\Test"
        assert created.scope == Scope.USER
        assert created.description == "Test path"
        assert created.active is True

        fetched = repo.get_by_id(created.id)
        assert fetched.path == created.path
        assert fetched.id == created.id

    def test_get_by_path(self, mock_db):
        repo = PathEntryRepository()
        entry = PathEntry(path=r"C:\Unique\Path", scope=Scope.USER)
        repo.create(entry)

        fetched = repo.get_by_path(r"C:\Unique\Path", Scope.USER)
        assert fetched is not None
        assert fetched.path == r"C:\Unique\Path"

        not_found = repo.get_by_path(r"C:\Nonexistent", Scope.USER)
        assert not_found is None

    def test_get_all_active_only(self, mock_db):
        repo = PathEntryRepository()
        repo.create(PathEntry(path=r"C:\Active1", scope=Scope.USER, active=True))
        repo.create(PathEntry(path=r"C:\Active2", scope=Scope.USER, active=True))
        repo.create(PathEntry(path=r"C:\Inactive", scope=Scope.USER, active=False))

        active = repo.get_all(Scope.USER, active_only=True)
        all_entries = repo.get_all(Scope.USER, active_only=False)

        assert len(active) == 2
        assert len(all_entries) == 3

    def test_set_active(self, mock_db):
        repo = PathEntryRepository()
        entry = repo.create(PathEntry(path=r"C:\Test", scope=Scope.USER, active=True))
        assert entry.active is True

        repo.set_active(r"C:\Test", Scope.USER, False)
        fetched = repo.get_by_path(r"C:\Test", Scope.USER)
        assert fetched.active is False

        repo.set_active(r"C:\Test", Scope.USER, True)
        fetched = repo.get_by_path(r"C:\Test", Scope.USER)
        assert fetched.active is True

    def test_update(self, mock_db):
        repo = PathEntryRepository()
        entry = repo.create(PathEntry(path=r"C:\Test", scope=Scope.USER, description="Old"))
        entry.description = "New"
        entry.position = 10
        updated = repo.update(entry)
        assert updated.description == "New"
        assert updated.position == 10

    def test_delete(self, mock_db):
        repo = PathEntryRepository()
        entry = repo.create(PathEntry(path=r"C:\ToDelete", scope=Scope.USER))
        repo.delete(entry.id)
        assert repo.get_by_id(entry.id) is None

    def test_reorder(self, mock_db):
        repo = PathEntryRepository()
        e1 = repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, position=0))
        e2 = repo.create(PathEntry(path=r"C:\B", scope=Scope.USER, position=1))
        e3 = repo.create(PathEntry(path=r"C:\C", scope=Scope.USER, position=2))

        repo.reorder([e3, e1, e2])

        assert repo.get_by_id(e3.id).position == 0
        assert repo.get_by_id(e1.id).position == 1
        assert repo.get_by_id(e2.id).position == 2

    def test_unique_constraint(self, mock_db):
        repo = PathEntryRepository()
        repo.create(PathEntry(path=r"C:\Duplicate", scope=Scope.USER))
        with pytest.raises(Exception):
            repo.create(PathEntry(path=r"C:\Duplicate", scope=Scope.USER))

    def test_scope_isolation(self, mock_db):
        repo = PathEntryRepository()
        repo.create(PathEntry(path=r"C:\Same", scope=Scope.USER))
        repo.create(PathEntry(path=r"C:\Same", scope=Scope.SYSTEM))

        user_entry = repo.get_by_path(r"C:\Same", Scope.USER)
        sys_entry = repo.get_by_path(r"C:\Same", Scope.SYSTEM)

        assert user_entry is not None
        assert sys_entry is not None
        assert user_entry.id != sys_entry.id


class TestEnvVarRepository:
    """Test EnvVarRepository."""

    def test_create_and_get(self, mock_db):
        repo = EnvVarRepository()
        var = EnvVar(name="TEST_VAR", value="test_value", scope=Scope.USER)
        created = repo.create(var)
        assert created.id is not None
        assert created.name == "TEST_VAR"
        assert created.value == "test_value"

    def test_encryption_flag(self, mock_db):
        repo = EnvVarRepository()
        var = EnvVar(name="SECRET", value="plain", scope=Scope.USER, encrypted=True)
        created = repo.create(var)
        assert created.encrypted is True

    def test_get_by_name(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="MY_VAR", value="value", scope=Scope.USER))
        fetched = repo.get_by_name("MY_VAR", Scope.USER)
        assert fetched is not None
        assert fetched.value == "value"

    def test_list_all(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="VAR1", value="v1", scope=Scope.USER))
        repo.create(EnvVar(name="VAR2", value="v2", scope=Scope.USER))
        repo.create(EnvVar(name="SYS_VAR", value="sv", scope=Scope.SYSTEM))

        user_vars = repo.list_all(Scope.USER)
        sys_vars = repo.list_all(Scope.SYSTEM)

        assert len(user_vars) == 2
        assert len(sys_vars) == 1

    def test_update_value(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="UPD_VAR", value="old", scope=Scope.USER))
        repo.update_value("UPD_VAR", Scope.USER, "new")
        fetched = repo.get_by_name("UPD_VAR", Scope.USER)
        assert fetched.value == "new"

    def test_delete(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="DEL_VAR", value="v", scope=Scope.USER))
        repo.delete("DEL_VAR", Scope.USER)
        assert repo.get_by_name("DEL_VAR", Scope.USER) is None


class TestBackupRepository:
    """Test BackupRepository."""

    def test_create_and_get(self, mock_db):
        repo = BackupRepository()
        backup = Backup(name="test-backup", scope=Scope.USER, path_snapshot=["C:\\A", "C:\\B"])
        created = repo.create(backup)
        assert created.id is not None
        assert created.name == "test-backup"
        assert created.checksum is not None

    def test_get_by_id(self, mock_db):
        repo = BackupRepository()
        backup = repo.create(Backup(name="b1", scope=Scope.USER, path_snapshot=["C:\\A"]))
        fetched = repo.get_by_id(backup.id)
        assert fetched.id == backup.id
        assert fetched.path_snapshot == ["C:\\A"]

    def test_list_all(self, mock_db):
        repo = BackupRepository()
        repo.create(Backup(name="b1", scope=Scope.USER, path_snapshot=["C:\\A"]))
        repo.create(Backup(name="b2", scope=Scope.USER, path_snapshot=["C:\\B"]))
        repo.create(Backup(name="b3", scope=Scope.SYSTEM, path_snapshot=["C:\\C"]))

        user_backups = repo.list_all(Scope.USER)
        sys_backups = repo.list_all(Scope.SYSTEM)

        assert len(user_backups) == 2
        assert len(sys_backups) == 1

    def test_verify_integrity(self, mock_db):
        repo = BackupRepository()
        backup = repo.create(Backup(name="verify-test", scope=Scope.USER, path_snapshot=["C:\\A"]))
        assert repo.verify_integrity(backup.id) is True

    def test_verify_integrity_fail(self, mock_db):
        repo = BackupRepository()
        backup = repo.create(Backup(name="verify-fail", scope=Scope.USER, path_snapshot=["C:\\A"]))
        # Manually corrupt the checksum
        repo._db.execute(
            "UPDATE backups SET checksum = ? WHERE id = ?",
            ("corrupted-checksum", backup.id)
        )
        assert repo.verify_integrity(backup.id) is False

    def test_delete(self, mock_db):
        repo = BackupRepository()
        backup = repo.create(Backup(name="to-delete", scope=Scope.USER, path_snapshot=["C:\\A"]))
        repo.delete(backup.id)
        assert repo.get_by_id(backup.id) is None


class TestOperationLogRepository:
    """Test OperationLogRepository."""

    def test_log_and_list(self, mock_db):
        repo = OperationLogRepository()
        log = OperationLog(
            operation=OperationType.ADD,
            scope=Scope.USER,
            target_path=r"C:\Test",
            status=OperationStatus.SUCCESS,
        )
        repo.log(log)

        logs = repo.list_all(limit=10)
        assert len(logs) == 1
        assert logs[0].operation == OperationType.ADD
        assert logs[0].target_path == r"C:\Test"

    def test_log_with_metadata(self, mock_db):
        repo = OperationLogRepository()
        log = OperationLog(
            operation=OperationType.BACKUP,
            scope=Scope.USER,
            target_path="",
            status=OperationStatus.SUCCESS,
            metadata={"backup_id": 123, "auto": True},
        )
        repo.log(log)

        logs = repo.list_all()
        assert logs[0].metadata == {"backup_id": 123, "auto": True}

    def test_log_failed(self, mock_db):
        repo = OperationLogRepository()
        log = OperationLog(
            operation=OperationType.REMOVE,
            scope=Scope.USER,
            target_path=r"C:\Fail",
            status=OperationStatus.FAILED,
            error_message="Path not found",
        )
        repo.log(log)

        logs = repo.list_all()
        assert logs[0].status == OperationStatus.FAILED
        assert logs[0].error_message == "Path not found"

    def test_list_by_operation(self, mock_db):
        repo = OperationLogRepository()
        repo.log(OperationLog(operation=OperationType.ADD, scope=Scope.USER, target_path="A", status=OperationStatus.SUCCESS))
        repo.log(OperationLog(operation=OperationType.REMOVE, scope=Scope.USER, target_path="B", status=OperationStatus.SUCCESS))
        repo.log(OperationLog(operation=OperationType.ADD, scope=Scope.USER, target_path="C", status=OperationStatus.SUCCESS))

        add_logs = repo.list_by_operation(OperationType.ADD)
        assert len(add_logs) == 2


class TestUserSettingsRepository:
    """Test UserSettingsRepository."""

    def test_set_and_get(self, mock_db):
        repo = UserSettingsRepository()
        repo.set("test_key", "test_value", "Test description")
        value = repo.get("test_key")
        assert value == "test_value"

    def test_get_default(self, mock_db):
        repo = UserSettingsRepository()
        value = repo.get("nonexistent", "default_value")
        assert value == "default_value"

    def test_get_all(self, mock_db):
        repo = UserSettingsRepository()
        repo.set("key1", "val1", "Desc 1")
        repo.set("key2", "val2", "Desc 2")
        all_settings = repo.get_all()
        assert "key1" in all_settings
        assert "key2" in all_settings
        assert all_settings["key1"] == "val1"

    def test_delete(self, mock_db):
        repo = UserSettingsRepository()
        repo.set("del_key", "val", "Desc")
        repo.delete("del_key")
        assert repo.get("del_key") is None