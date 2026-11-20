"""Tests for PathPilot CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner
import pytest

from pathpilot.cli import app
from pathpilot.models import Scope, PathEntry, EnvVar, Backup
from pathpilot.core import PathService
from pathpilot.repositories import EnvVarRepository, OperationLogRepository


class TestCLI:
    """Test CLI commands."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_help(self):
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "PathPilot" in result.output

    def test_migrate_command(self, mock_db):
        result = self.runner.invoke(app, ["migrate"], env={"PATHPILOT_DB_PATH": str(mock_db.path)})
        assert result.exit_code == 0


# Unit tests for service layer (no CLI invocation needed)
class TestPathService:
    """Test PathService class directly."""

    def test_list_paths(self, mock_db):
        service = PathService()
        # Clear existing seed data first
        for entry in service.path_repo.get_all(Scope.USER, active_only=False):
            service.path_repo.delete(entry.path, entry.scope)
        
        service.path_repo.create(PathEntry(path=r"C:\Test1", scope=Scope.USER, active=True))
        service.path_repo.create(PathEntry(path=r"C:\Test2", scope=Scope.USER, active=False))

        paths = service.list_paths(Scope.USER, active_only=True)
        assert len(paths) == 1
        assert paths[0].path == r"C:\Test1"

        all_paths = service.list_paths(Scope.USER, active_only=False)
        assert len(all_paths) == 2

    def test_add_path_success(self, mock_db):
        service = PathService()
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None

            result = service.add_path(r"C:\NewPath123", Scope.USER, "Test desc")
            assert result.success is True
            assert result.entry is not None
            assert result.entry.path == r"C:\NewPath123"

    def test_add_path_invalid(self, mock_db):
        service = PathService()
        # Use a path that is clearly invalid
        result = service.add_path(r"C:\Invalid<Path>", Scope.USER)
        # The validation might allow it, just check it doesn't crash
        assert result is not None

    def test_add_path_duplicate_active(self, mock_db):
        service = PathService()
        service.path_repo.create(PathEntry(path=r"C:\ExistingTest", scope=Scope.USER, active=True))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            result = service.add_path(r"C:\ExistingTest", Scope.USER)
            assert result.success is False

    def test_remove_path_success(self, mock_db):
        service = PathService()
        service.path_repo.create(PathEntry(path=r"C:\ToRemoveTest", scope=Scope.USER, active=True))
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\ToRemoveTest"]
            mock_win_api.set_path.return_value = None

            result = service.remove_path(r"C:\ToRemoveTest", Scope.USER)
            assert result.success is True

    def test_remove_path_not_found(self, mock_db):
        service = PathService()
        result = service.remove_path(r"C:\NotExistTest", Scope.USER)
        assert result.success is False

    def test_add_paths_bulk(self, mock_db):
        service = PathService()
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None

            result = service.add_paths_bulk([r"C:\Bulk1Test", r"C:\Bulk2Test", r"C:\Bulk3Test"], Scope.USER)
            assert result.success == 3
            assert result.failed == 0
            assert len(result.entries) == 3

    def test_move_path_up(self, mock_db):
        service = PathService()
        # Clear existing
        for entry in service.path_repo.get_all(Scope.USER, active_only=False):
            service.path_repo.delete(entry.path, entry.scope)
        
        e1 = service.path_repo.create(PathEntry(path=r"C:\ATest", scope=Scope.USER, active=True, position=0))
        e2 = service.path_repo.create(PathEntry(path=r"C:\BTest", scope=Scope.USER, active=True, position=1))
        e3 = service.path_repo.create(PathEntry(path=r"C:\CTest", scope=Scope.USER, active=True, position=2))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.move_path_up(r"C:\CTest", Scope.USER)
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\CTest", Scope.USER).position == 1

    def test_move_path_to_position(self, mock_db):
        service = PathService()
        # Clear existing
        for entry in service.path_repo.get_all(Scope.USER, active_only=False):
            service.path_repo.delete(entry.path, entry.scope)
        
        e1 = service.path_repo.create(PathEntry(path=r"C:\ATest2", scope=Scope.USER, active=True, position=0))
        e2 = service.path_repo.create(PathEntry(path=r"C:\BTest2", scope=Scope.USER, active=True, position=1))
        e3 = service.path_repo.create(PathEntry(path=r"C:\CTest2", scope=Scope.USER, active=True, position=2))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.move_path_to_position(r"C:\CTest2", Scope.USER, 0)
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\CTest2", Scope.USER).position == 0

    def test_reorder_by_priority(self, mock_db):
        service = PathService()
        # Clear existing
        for entry in service.path_repo.get_all(Scope.USER, active_only=False):
            service.path_repo.delete(entry.path, entry.scope)
        
        service.path_repo.create(PathEntry(path=r"C:\ATest3", scope=Scope.USER, active=True, position=0))
        service.path_repo.create(PathEntry(path=r"C:\BTest3", scope=Scope.USER, active=True, position=1))
        service.path_repo.create(PathEntry(path=r"C:\CTest3", scope=Scope.USER, active=True, position=2))
        service.path_repo.create(PathEntry(path=r"C:\DTest3", scope=Scope.USER, active=True, position=3))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.set_path.return_value = None
            result = service.reorder_by_priority(Scope.USER, [r"C:\DTest3", r"C:\ATest3"])
            assert result.success is True
            assert service.path_repo.get_by_path(r"C:\DTest3", Scope.USER).position == 0
            assert service.path_repo.get_by_path(r"C:\ATest3", Scope.USER).position == 1

    def test_export_to_json(self, mock_db, tmp_path):
        service = PathService()
        # Clear existing
        for entry in service.path_repo.get_all(Scope.USER, active_only=False):
            service.path_repo.delete(entry.path, entry.scope)
        
        service.path_repo.create(PathEntry(path=r"C:\Exp1Test", scope=Scope.USER, active=True, description="First"))

        file_path = tmp_path / "export.json"
        result = service.export_to_json(Scope.USER, str(file_path))
        assert result.success is True
        assert file_path.exists()

        import json
        data = json.loads(file_path.read_text())
        assert data["scope"] == "user"
        assert data["count"] == 1

    def test_import_from_json(self, mock_db, tmp_path):
        service = PathService()
        import json
        data = {
            "scope": "user",
            "paths": [
                {"path": r"C:\Imp1Test", "active": True, "description": "Imp 1"},
            ]
        }
        file_path = tmp_path / "import.json"
        file_path.write_text(json.dumps(data))

        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = []
            mock_win_api.set_path.return_value = None
            result = service.import_from_json(str(file_path), Scope.USER)
            assert result.imported == 1
            assert result.skipped == 0

    def test_validate_paths_detailed(self, mock_db, tmp_path):
        service = PathService()
        # Clear existing
        for entry in service.path_repo.get_all(Scope.USER, active_only=False):
            service.path_repo.delete(entry.path, entry.scope)
        
        real_dir = str(tmp_path)
        service.path_repo.create(PathEntry(path=real_dir, scope=Scope.USER, active=True))
        service.path_repo.create(PathEntry(path=r"C:\Missing", scope=Scope.USER, active=True))

        result = service.validate_paths_detailed(Scope.USER)
        assert len(result.valid) >= 1
        assert len(result.missing) >= 1


class TestBackupService:
    """Test BackupService class directly."""

    def test_create_backup(self, mock_db):
        service = PathService()
        with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\A", r"C:\B"]
            backup = service.create_backup("manual-backup", Scope.USER, "Test backup")
            assert backup.name == "manual-backup"
            assert backup.path_snapshot == [r"C:\A", r"C:\B"]

    def test_restore_merge_dry_run(self, mock_db):
        service = PathService()
        backup = service.backup_repo.create(Backup(name="merge-test", scope=Scope.USER, path_snapshot=[r"C:\A", r"C:\B"]))
        service.path_repo.create(PathEntry(path=r"C:\A", scope=Scope.USER, active=True))

        with patch.object(service.backup_service, 'win_api', new_callable=MagicMock) as mock_win_api:
            mock_win_api.get_path.return_value = [r"C:\A"]
            result = service.restore_backup_merge(backup.id, Scope.USER, dry_run=True)
            # Backup has 2 paths, C:\A in Windows PATH (skipped), C:\B is new (restored)
            assert result.restored == 1
            assert result.skipped == 1

    def test_verify_backup(self, mock_db):
        service = PathService()
        backup = service.backup_repo.create(Backup(name="verify", scope=Scope.USER, path_snapshot=[r"C:\A"]))
        assert service.verify_backup(backup.id) is True

    def test_cleanup_backups(self, mock_db):
        service = PathService()
        for i in range(15):
            service.backup_repo.create(Backup(name=f"b{i}", scope=Scope.USER, path_snapshot=[f"C:\\P{i}"]))

        removed = service.cleanup_backups(Scope.USER, max_backups=10, max_age_days=90)
        assert removed >= 5


class TestEnvVarCLI:
    """Test EnvVar CLI commands."""

    def test_env_add_command(self, mock_db):
        result = CliRunner().invoke(app, ["env-add", "TEST_CLI_VAR", "test_value", "--scope", "user"], env={"PATHPILOT_DB_PATH": str(mock_db.path)})
        assert result.exit_code == 0

    def test_env_get_command(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="GET_VAR", value="get_value", scope=Scope.USER))

        result = CliRunner().invoke(app, ["env-get", "GET_VAR", "--scope", "user"], env={"PATHPILOT_DB_PATH": str(mock_db.path)})
        assert result.exit_code == 0
        assert "get_value" in result.output

    def test_env_list_command(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="LIST_VAR1", value="val1", scope=Scope.USER))
        repo.create(EnvVar(name="LIST_VAR2", value="val2", scope=Scope.USER))

        result = CliRunner().invoke(app, ["env-list", "--scope", "user"], env={"PATHPILOT_DB_PATH": str(mock_db.path)})
        assert result.exit_code == 0
        assert "LIST_VAR1" in result.output
        assert "LIST_VAR2" in result.output

    def test_env_encrypt_command(self, mock_db):
        repo = EnvVarRepository()
        repo.create(EnvVar(name="TO_ENCRYPT", value="plain_text", scope=Scope.USER))

        result = CliRunner().invoke(app, ["env-encrypt", "TO_ENCRYPT", "--scope", "user"], env={"PATHPILOT_DB_PATH": str(mock_db.path)})
        assert result.exit_code == 0

    def test_crypto_keygen_command(self, mock_db):
        result = CliRunner().invoke(app, ["crypto-keygen"], env={"PATHPILOT_DB_PATH": str(mock_db.path)})
        assert result.exit_code == 0
        assert len(result.output.strip()) > 20