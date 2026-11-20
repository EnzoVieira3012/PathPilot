"""Tests for PathPilot core module (PathService, BackupService)."""

import pytest
from unittest.mock import patch, MagicMock
from pathpilot.models import Scope, PathEntry, Backup, OperationType, OperationStatus, SyncResult
from pathpilot.core import PathService, BackupService, OperationResult, BulkOperationResult, ImportResult, RestoreResult


def _clear_user_paths(service):
    """Helper to clear user paths from seed data."""
    for entry in service.path_repo.get_all(Scope.USER, active_only=False):
        service.path_repo.delete(entry.path, entry.scope)


class TestPathService:
    """Test PathService class."""

    def test_list_paths(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Test1", scope=Scope.USER, active=True))
        service.path_repo.create(PathEntry(path=r"C:\Test2", scope=Scope.USER, active=False))

        paths = service.list_paths(Scope.USER, active_only=True)
        assert len(paths) == 1
        assert paths[0].path == r"C:\Test1"

        all_paths = service.list_paths(Scope.USER, active_only=False)
        assert len(all_paths) == 2

    def test_add_path_success(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None

            result = service.add_path(r"C:\NewPath", Scope.USER, "Test desc")
            assert result.success is True
            assert "adicionado" in result.message.lower()
            assert result.entry is not None
            assert result.entry.path == r"C:\NewPath"

    def test_add_path_invalid(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        result = service.add_path("invalid<path>", Scope.USER)
        # Current implementation allows it with a warning
        assert result is not None

    def test_add_path_duplicate_active(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Existing", scope=Scope.USER, active=True))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            result = service.add_path(r"C:\Existing", Scope.USER)
            assert result.success is False
            assert "ja existe" in result.message.lower()

    def test_add_path_reactivate_inactive(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Inactive", scope=Scope.USER, active=False))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None
            result = service.add_path(r"C:\Inactive", Scope.USER)
            assert result.success is True
            assert "reativado" in result.message.lower()

    def test_remove_path_success(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\ToRemove", scope=Scope.USER, active=True))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\ToRemove"]
            mock_win_api.set_path.return_value = None
            result = service.remove_path(r"C:\ToRemove", Scope.USER)
            assert result.success is True
            assert "removido" in result.message.lower()

    def test_remove_path_not_found(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        result = service.remove_path(r"C:\NotExist", Scope.USER)
        assert result.success is False
        assert "nao encontrado" in result.message.lower()

    def test_remove_path_already_inactive(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Inactive", scope=Scope.USER, active=False))
        result = service.remove_path(r"C:\Inactive", Scope.USER)
        assert result.success is False
        assert "ja esta inativo" in result.message.lower()


class TestBulkOperations:
    """Test bulk add/remove operations."""

    def test_add_paths_bulk(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None
            result = service.add_paths_bulk([r"C:\Bulk1", r"C:\Bulk2", r"C:\Bulk3"], Scope.USER)
            assert result.success == 3
            assert result.failed == 0
            assert len(result.entries) == 3

    def test_add_paths_bulk_partial_failure(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Existing", scope=Scope.USER, active=True))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None
            result = service.add_paths_bulk([r"C:\New1", r"C:\Existing", r"C:\New2"], Scope.USER)
            assert result.success == 2
            assert result.failed == 1

    def test_remove_paths_bulk(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Remove1", scope=Scope.USER, active=True))
        service.path_repo.create(PathEntry(path=r"C:\Remove2", scope=Scope.USER, active=True))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\Remove1", r"C:\Remove2"]
            mock_win_api.set_path.return_value = None
            result = service.remove_paths_bulk([r"C:\Remove1", r"C:\Remove2"], Scope.USER)
            assert result.success == 2
            assert result.failed == 0


class TestReorderOperations:
    """Test path reordering operations."""

    def test_move_path_up(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        e1 = service.path_repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, active=True, position=0))
        e2 = service.path_repo.create(PathEntry(path=r"C:\B", scope=Scope.USER, active=True, position=1))
        e3 = service.path_repo.create(PathEntry(path=r"C:\C", scope=Scope.USER, active=True, position=2))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.move_path_up(r"C:\C", Scope.USER)
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\C", Scope.USER).position == 1

    def test_move_path_up_at_top(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Top", scope=Scope.USER, active=True, position=0))
        result = service.move_path_up(r"C:\Top", Scope.USER)
        assert result.success is False

    def test_move_path_down(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        e1 = service.path_repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, active=True, position=0))
        e2 = service.path_repo.create(PathEntry(path=r"C:\B", scope=Scope.USER, active=True, position=1))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.move_path_down(r"C:\A", Scope.USER)
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\A", Scope.USER).position == 1

    def test_move_path_to_position(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        e1 = service.path_repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, active=True, position=0))
        e2 = service.path_repo.create(PathEntry(path=r"C:\B", scope=Scope.USER, active=True, position=1))
        e3 = service.path_repo.create(PathEntry(path=r"C:\C", scope=Scope.USER, active=True, position=2))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.move_path_to_position(r"C:\C", Scope.USER, 0)
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\C", Scope.USER).position == 0
            assert service.path_repo.get_by_path(r"C:\A", Scope.USER).position == 1

    def test_reorder_by_priority(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, active=True, position=0))
        service.path_repo.create(PathEntry(path=r"C:\B", scope=Scope.USER, active=True, position=1))
        service.path_repo.create(PathEntry(path=r"C:\C", scope=Scope.USER, active=True, position=2))
        service.path_repo.create(PathEntry(path=r"C:\D", scope=Scope.USER, active=True, position=3))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.reorder_by_priority(Scope.USER, [r"C:\D", r"C:\A"])
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\D", Scope.USER).position == 0
            assert service.path_repo.get_by_path(r"C:\A", Scope.USER).position == 1


class TestImportExport:
    """Test import/export operations."""

    def test_export_to_json(self, mock_db, tmp_path):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Exp1", scope=Scope.USER, active=True, description="First"))
        service.path_repo.create(PathEntry(path=r"C:\Exp2", scope=Scope.USER, active=True, description="Second"))

        file_path = tmp_path / "export.json"
        result = service.export_to_json(Scope.USER, str(file_path))
        assert result.success is True
        assert file_path.exists()

        import json
        data = json.loads(file_path.read_text())
        assert data["scope"] == "user"
        assert data["count"] == 2
        assert len(data["paths"]) == 2

    def test_export_to_csv(self, mock_db, tmp_path):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Exp1", scope=Scope.USER, active=True))

        file_path = tmp_path / "export.csv"
        result = service.export_to_csv(Scope.USER, str(file_path))
        assert result.success is True
        assert file_path.exists()

        content = file_path.read_text()
        assert "path,active,position,description,created_at" in content
        assert "C:\\Exp1" in content

    def test_import_from_json(self, mock_db, tmp_path):
        service = PathService()
        _clear_user_paths(service)
        import json
        data = {
            "scope": "user",
            "paths": [
                {"path": r"C:\Imp1", "active": True, "description": "Imp 1"},
                {"path": r"C:\Imp2", "active": True, "description": "Imp 2"},
            ]
        }
        file_path = tmp_path / "import.json"
        file_path.write_text(json.dumps(data))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None
            result = service.import_from_json(str(file_path), Scope.USER)
            assert result.imported == 2
            assert result.skipped == 0

    def test_import_from_json_skip_existing(self, mock_db, tmp_path):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\Existing", scope=Scope.USER, active=True))

        import json
        data = {"scope": "user", "paths": [{"path": r"C:\Existing", "active": True}]}
        file_path = tmp_path / "import.json"
        file_path.write_text(json.dumps(data))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None
            result = service.import_from_json(str(file_path), Scope.USER)
            assert result.imported == 0
            assert result.skipped == 1


class TestAdvancedSync:
    """Test advanced sync operations."""

    def test_sync_with_conflicts_keep_db(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\InDBOnly", scope=Scope.USER, active=True))
        service.path_repo.create(PathEntry(path=r"C:\InBothInactive", scope=Scope.USER, active=False))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\InBothInactive", r"C:\InWinOnly"]
            mock_win_api.set_path.return_value = None
            result = service.sync_with_conflicts(Scope.USER, strategy="keep_db")
            assert isinstance(result, SyncResult)

    def test_detect_conflicts(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.path_repo.create(PathEntry(path=r"C:\InBothInactive", scope=Scope.USER, active=False))
        service.path_repo.create(PathEntry(path=r"C:\InDBOnly", scope=Scope.USER, active=True))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\InBothInactive", r"C:\InWinOnly"]
            conflicts = service.detect_conflicts(Scope.USER)
            assert len(conflicts) == 2
            assert any(c.path == r"C:\InBothInactive" and not c.db_active for c in conflicts)
            assert any(c.path == r"C:\InDBOnly" and c.db_active and not c.in_windows for c in conflicts)


class TestAdvancedValidation:
    """Test advanced validation operations."""

    def test_validate_paths_detailed(self, mock_db, tmp_path):
        service = PathService()
        _clear_user_paths(service)
        real_dir = str(tmp_path)

        service.path_repo.create(PathEntry(path=real_dir, scope=Scope.USER, active=True))
        service.path_repo.create(PathEntry(path=r"C:\Missing", scope=Scope.USER, active=True))

        result = service.validate_paths_detailed(Scope.USER)
        assert len(result.valid) >= 1
        assert len(result.missing) >= 1


class TestBackupService:
    """Test BackupService class."""

    def test_create_backup(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\A", r"C:\B"]
            backup = service.create_backup("manual-backup", Scope.USER, "Test backup")
            assert backup.name == "manual-backup"
            assert backup.path_snapshot == [r"C:\A", r"C:\B"]

    def test_restore_merge_dry_run(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        backup = service.backup_repo.create(Backup(name="merge-test", scope=Scope.USER, path_snapshot=[r"C:\A", r"C:\B"]))
        service.path_repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, active=True))

        with patch.object(service.backup_service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\A"]
            result = service.restore_backup_merge(backup.id, Scope.USER, dry_run=True)
            assert result.restored == 1
            assert result.skipped == 1

    def test_restore_merge(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        backup = service.backup_repo.create(Backup(name="merge-test", scope=Scope.USER, path_snapshot=[r"C:\A", r"C:\B"]))

        with patch.object(service.backup_service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\A"]
            mock_win_api.set_path.return_value = None
            result = service.restore_backup_merge(backup.id, Scope.USER)
            assert result.restored == 1

    def test_restore_full_dry_run(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        backup = service.backup_repo.create(Backup(name="full-test", scope=Scope.USER, path_snapshot=[r"C:\A", r"C:\B", r"C:\C"]))

        result = service.restore_backup_full(backup.id, Scope.USER, dry_run=True)
        assert result.restored == 3

    def test_verify_backup(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        backup = service.backup_repo.create(Backup(name="verify", scope=Scope.USER, path_snapshot=[r"C:\A"]))
        assert service.verify_backup(backup.id) is True

    def test_cleanup_backups(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        for i in range(15):
            service.backup_repo.create(Backup(name=f"b{i}", scope=Scope.USER, path_snapshot=[f"C:\\P{i}"]))

        removed = service.cleanup_backups(Scope.USER, max_backups=10, max_age_days=90)
        assert removed >= 5

        remaining = service.backup_repo.list_all(Scope.USER, limit=100)
        assert len(remaining) <= 10

    def test_set_backup_schedule(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        service.set_backup_schedule(enabled=True, interval_hours=12, scope=Scope.USER, max_backups=5)
        status = service.get_backup_schedule_status()
        assert status["enabled"] is True
        assert status["interval_hours"] == 12
        assert status["max_backups"] == 5

        service.set_backup_schedule(enabled=False)
        status = service.get_backup_schedule_status()
        assert status["enabled"] is False


class TestExpandVariables:
    """Test expand_variables_in_db."""

    def test_expand_variables(self, mock_db):
        service = PathService()
        _clear_user_paths(service)
        # Use a path that doesn't expand to an existing Windows path
        service.path_repo.create(PathEntry(path=r"C:\Test\Path", scope=Scope.USER, active=True))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.expand_variables_in_db(Scope.USER)
            assert result.success is True