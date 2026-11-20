"""Servico principal - logica de negocio."""

from dataclasses import dataclass

from .models import OperationStatus, OperationType, PathEntry, Scope, SyncResult, ValidationResult
from .repositories import BackupRepository, OperationLogRepository, PathEntryRepository
from .utils import is_valid_path, normalize_path, path_exists, print_warning
from .windows_api import WindowsPathAPI


@dataclass
class OperationResult:
    success: bool
    message: str
    entry: PathEntry | None = None


class PathService:
    """Servico de operacoes no PATH."""

    def __init__(self):
        self.path_repo = PathEntryRepository()
        self.backup_repo = BackupRepository()
        self.log_repo = OperationLogRepository()
        self.win_api = WindowsPathAPI()

    def list_paths(self, scope: Scope, active_only: bool = True) -> list[PathEntry]:
        return self.path_repo.get_all(scope, active_only)

    def add_path(self, path: str, scope: Scope, description: str = "") -> OperationResult:
        path = normalize_path(path)

        if not is_valid_path(path):
            return OperationResult(False, f"Path invalido: {path}")

        if not path_exists(path):
            print_warning(f"Path nao existe no filesystem: {path}")

        existing = self.path_repo.get_by_path(path, scope)
        if existing:
            if existing.active:
                return OperationResult(False, f"Path ja existe e esta ativo: {path}")
            else:
                self.path_repo.set_active(path, scope, True)
                self._log(OperationType.ADD, scope, path, OperationStatus.SUCCESS, "Reativado")
                return OperationResult(True, f"Path reativado: {path}", existing)

        # Pega position maxima
        entries = self.path_repo.get_all(scope, active_only=False)
        max_pos = max((e.position for e in entries), default=-1)

        entry = PathEntry(
            path=path,
            scope=scope,
            active=True,
            position=max_pos + 1,
            description=description,
        )
        self.path_repo.create(entry)

        self._sync_to_windows(scope)
        self._log(OperationType.ADD, scope, path, OperationStatus.SUCCESS)
        return OperationResult(True, f"Path adicionado: {path}", entry)

    def remove_path(self, path: str, scope: Scope) -> OperationResult:
        path = normalize_path(path)

        existing = self.path_repo.get_by_path(path, scope)
        if not existing:
            return OperationResult(False, f"Path nao encontrado: {path}")

        if not existing.active:
            return OperationResult(False, f"Path ja esta inativo: {path}")

        self.path_repo.set_active(path, scope, False)
        self._sync_to_windows(scope)
        self._log(OperationType.REMOVE, scope, path, OperationStatus.SUCCESS)
        return OperationResult(True, f"Path removido (desativado): {path}")

    def validate_paths(self, scope: Scope) -> ValidationResult:
        entries = self.path_repo.get_all(scope, active_only=True)
        result = ValidationResult()

        seen = set()
        for entry in entries:
            norm = normalize_path(entry.path)
            if norm in seen:
                result.duplicates.append(entry.path)
                continue
            seen.add(norm)

            if path_exists(norm):
                result.valid.append(entry.path)
            else:
                result.missing.append(entry.path)

        # Verifica invalidos (caracteres, etc)
        for entry in entries:
            if not is_valid_path(entry.path):
                result.invalid.append(entry.path)

        return result

    def sync_from_system(self, scope: Scope) -> SyncResult:
        """Sincroniza DB com PATH real do Windows."""
        system_paths = self.win_api.get_path(scope)
        db_entries = self.path_repo.get_all(scope, active_only=False)
        db_paths = {normalize_path(e.path) for e in db_entries}

        result = SyncResult()

        for spath in system_paths:
            norm = normalize_path(spath)
            if norm not in db_paths:
                # Novo path no Windows, adiciona ao DB
                entry = PathEntry(path=norm, scope=scope, active=True, position=len(db_entries))
                self.path_repo.create(entry)
                db_entries.append(entry)
                result.added.append(spath)
            else:
                result.unchanged.append(spath)

        # Paths no DB mas nao no Windows
        sys_paths_norm = {normalize_path(p) for p in system_paths}
        for entry in db_entries:
            if normalize_path(entry.path) not in sys_paths_norm:
                if entry.active:
                    self.path_repo.set_active(entry.path, scope, False)
                    result.removed.append(entry.path)

        result.drift_detected = len(result.added) > 0 or len(result.removed) > 0
        return result

    def reorder_paths(self, entries: list[PathEntry]) -> None:
        self.path_repo.reorder(entries)
        self._sync_to_windows(entries[0].scope if entries else Scope.USER)

    def _sync_to_windows(self, scope: Scope) -> None:
        entries = self.path_repo.get_all(scope, active_only=True)
        paths = [e.path for e in entries]
        self.win_api.set_path(scope, paths)

    def _log(self, op: OperationType, scope: Scope, target: str, status: OperationStatus, error: str = "", metadata: dict = None):
        from .models import OperationLog
        log = OperationLog(
            operation=op,
            scope=scope,
            target_path=target,
            status=status,
            error_message=error,
            metadata=metadata or {},
        )
        self.log_repo.log(log)
