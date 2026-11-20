"""Tests for PathPilot models."""

import pytest
from datetime import datetime
from pathpilot.models import (
    Scope, PathEntry, EnvVar, Backup, OperationLog,
    OperationType, OperationStatus, ValidationResult, SyncResult
)
from pathpilot.core import SyncConflict


class TestScope:
    """Test Scope enum."""

    def test_user_scope(self):
        assert Scope.USER.value == "user"

    def test_system_scope(self):
        assert Scope.SYSTEM.value == "system"


class TestPathEntry:
    """Test PathEntry dataclass."""

    def test_create_basic(self):
        entry = PathEntry(path=r"C:\Test", scope=Scope.USER)
        assert entry.path == r"C:\Test"
        assert entry.scope == Scope.USER
        assert entry.active is True
        assert entry.position is None
        assert entry.description == ""
        assert entry.created_at is None
        assert entry.updated_at is None

    def test_create_full(self):
        now = datetime.now()
        entry = PathEntry(
            path=r"C:\Test",
            scope=Scope.SYSTEM,
            active=False,
            position=5,
            description="Test path",
            created_at=now,
            updated_at=now,
        )
        assert entry.path == r"C:\Test"
        assert entry.scope == Scope.SYSTEM
        assert entry.active is False
        assert entry.position == 5
        assert entry.description == "Test path"
        assert entry.created_at == now
        assert entry.updated_at == now


class TestEnvVar:
    """Test EnvVar dataclass."""

    def test_create_basic(self):
        var = EnvVar(name="TEST", value="value", scope=Scope.USER)
        assert var.name == "TEST"
        assert var.value == "value"
        assert var.scope == Scope.USER
        assert var.description == ""
        assert var.encrypted is False
        assert var.created_at is None
        assert var.updated_at is None

    def test_create_encrypted(self):
        var = EnvVar(name="SECRET", value="encrypted", scope=Scope.USER, encrypted=True)
        assert var.encrypted is True


class TestBackup:
    """Test Backup dataclass."""

    def test_create_basic(self):
        backup = Backup(name="test-backup", scope=Scope.USER, path_snapshot=["C:\\A", "C:\\B"])
        assert backup.name == "test-backup"
        assert backup.scope == Scope.USER
        assert backup.path_snapshot == ["C:\\A", "C:\\B"]
        assert backup.description == ""
        assert backup.checksum is not None
        assert backup.created_at is None

    def test_checksum_generation(self):
        backup1 = Backup(name="b1", scope=Scope.USER, path_snapshot=["C:\\A"])
        backup2 = Backup(name="b2", scope=Scope.USER, path_snapshot=["C:\\A"])
        assert backup1.checksum == backup2.checksum

    def test_different_checksum(self):
        backup1 = Backup(name="b1", scope=Scope.USER, path_snapshot=["C:\\A"])
        backup2 = Backup(name="b2", scope=Scope.USER, path_snapshot=["C:\\B"])
        assert backup1.checksum != backup2.checksum


class TestOperationLog:
    """Test OperationLog dataclass."""

    def test_create_basic(self):
        log = OperationLog(
            operation=OperationType.ADD,
            scope=Scope.USER,
            target_path=r"C:\Test",
            status=OperationStatus.SUCCESS,
        )
        assert log.operation == OperationType.ADD
        assert log.scope == Scope.USER
        assert log.target_path == r"C:\Test"
        assert log.status == OperationStatus.SUCCESS
        assert log.error_message == ""
        assert log.metadata == {}
        assert log.created_at is None


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_defaults(self):
        result = ValidationResult()
        assert result.valid == []
        assert result.missing == []
        assert result.invalid == []
        assert result.duplicates == []

    def test_add_results(self):
        result = ValidationResult()
        result.valid.append("C:\\Valid")
        result.missing.append("C:\\Missing")
        result.invalid.append("invalid")
        result.duplicates.append("C:\\Duplicate")
        assert len(result.valid) == 1
        assert len(result.missing) == 1
        assert len(result.invalid) == 1
        assert len(result.duplicates) == 1


class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_defaults(self):
        result = SyncResult()
        assert result.added == []
        assert result.removed == []
        assert result.unchanged == []
        assert result.drift_detected is False


class TestSyncConflict:
    """Test SyncConflict dataclass."""

    def test_create_basic(self):
        conflict = SyncConflict(
            path=r"C:\Test",
            in_windows=True,
            in_db=True,
            db_active=False,
        )
        assert conflict.path == r"C:\Test"
        assert conflict.in_windows is True
        assert conflict.in_db is True
        assert conflict.db_active is False
        assert conflict.resolution == "keep_db"


class TestOperationType:
    """Test OperationType enum."""

    def test_values(self):
        assert OperationType.ADD.value == "add"
        assert OperationType.REMOVE.value == "remove"
        assert OperationType.REORDER.value == "reorder"
        assert OperationType.BACKUP.value == "backup"
        assert OperationType.RESTORE.value == "restore"
        assert OperationType.SYNC.value == "sync"
        assert OperationType.VALIDATE.value == "validate"
        assert OperationType.ENCRYPT.value == "encrypt"
        assert OperationType.DECRYPT.value == "decrypt"


class TestOperationStatus:
    """Test OperationStatus enum."""

    def test_values(self):
        assert OperationStatus.SUCCESS.value == "success"
        assert OperationStatus.FAILED.value == "failed"
        assert OperationStatus.PARTIAL.value == "partial"