"""Servico principal - logica de negocio."""

import csv
import json
import sched
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings
from .models import Backup, OperationStatus, OperationType, PathEntry, Scope, SyncResult, ValidationResult
from .repositories import BackupRepository, OperationLogRepository, PathEntryRepository
from .utils import expand_path, is_valid_path, normalize_path, path_exists, print_info, print_warning
from .windows_api import WindowsPathAPI


@dataclass
class OperationResult:
    success: bool
    message: str
    entry: PathEntry | None = None


@dataclass
class BulkOperationResult:
    success: int
    failed: int
    errors: list[str]
    entries: list[PathEntry]


@dataclass
class ImportResult:
    imported: int
    skipped: int
    errors: list[str]


@dataclass
class SyncConflict:
    """Conflito detectado durante sync."""
    path: str
    in_windows: bool
    in_db: bool
    db_active: bool
    resolution: str = "keep_db"  # keep_db, keep_windows, keep_both


@dataclass
class RestoreResult:
    restored: int
    skipped: int
    failed: int
    errors: list[str]


@dataclass
class BackupSchedule:
    enabled: bool = False
    interval_hours: int = 24
    scope: Scope = Scope.USER
    max_backups: int = 10
    next_run: datetime | None = None


class BackupService:
    """Servico de backup/restore avancado."""

    def __init__(self, path_service: "PathService"):
        self.path_service = path_service
        self.backup_repo = BackupRepository()
        self.path_repo = PathEntryRepository()
        self.win_api = WindowsPathAPI()
        self._scheduler: sched.scheduler | None = None
        self._scheduler_thread: threading.Thread | None = None
        self._running = False
        self._schedule = BackupSchedule()

    # ==================== AUTO-BACKUP HOOKS ====================

    def auto_backup_before_change(self, scope: Scope, operation: str, description: str = "") -> Backup:
        """Cria backup automatico antes de mudanca destrutiva."""
        if not self.path_service.path_repo.get_all(scope, active_only=True):
            return None

        name = f"auto-{operation}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        paths = self.win_api.get_path(scope)
        backup = Backup(
            name=name,
            scope=scope,
            path_snapshot=paths,
            description=f"Auto-backup antes de {operation}: {description}",
        )
        created = self.backup_repo.create(backup)

        # Log da operacao de auto-backup
        from .models import OperationLog, OperationStatus, OperationType
        log = OperationLog(
            operation=OperationType.BACKUP,
            scope=scope,
            target_path="",
            status=OperationStatus.SUCCESS,
            metadata={"auto": True, "trigger": operation, "backup_id": created.id},
        )
        self.path_service.log_repo.log(log)

        return created

    # ==================== MERGE RESTORE ====================

    def restore_merge(self, backup_id: int, scope: Scope, dry_run: bool = False) -> RestoreResult:
        """Restore merge: adiciona paths do backup que faltam, nao remove existentes."""
        backup = self.backup_repo.get_by_id(backup_id)
        if not backup:
            return RestoreResult(0, 0, 1, [f"Backup {backup_id} nao encontrado"])

        result = RestoreResult(restored=0, skipped=0, failed=0, errors=[])
        current_paths = {normalize_path(p) for p in self.win_api.get_path(scope)}
        backup_paths = [normalize_path(p) for p in backup.path_snapshot]

        if dry_run:
            for p in backup_paths:
                if p not in current_paths:
                    result.restored += 1
                else:
                    result.skipped += 1
            return result

        for p in backup_paths:
            if p not in current_paths:
                op_result = self.path_service.add_path(p, scope, f"Restored from {backup.name}")
                if op_result.success:
                    result.restored += 1
                else:
                    result.failed += 1
                    result.errors.append(f"{p}: {op_result.message}")
            else:
                result.skipped += 1

        return result

    def restore_full(self, backup_id: int, scope: Scope, dry_run: bool = False) -> RestoreResult:
        """Restore full: substitui PATH atual pelo backup."""
        backup = self.backup_repo.get_by_id(backup_id)
        if not backup:
            return RestoreResult(0, 0, 1, [f"Backup {backup_id} nao encontrado"])

        result = RestoreResult(restored=0, skipped=0, failed=0, errors=[])

        if dry_run:
            result.restored = len(backup.path_snapshot)
            return result

        # Aplica no Windows
        self.win_api.set_path(scope, backup.path_snapshot)

        # Atualiza DB
        for idx, p in enumerate(backup.path_snapshot):
            entry = self.path_repo.get_by_path(p, scope)
            if entry:
                entry.active = True
                entry.position = idx
                self.path_repo.update(entry)
            else:
                self.path_repo.create(PathEntry(path=p, scope=scope, active=True, position=idx))

        # Desativa paths que estavam ativos mas nao estao no backup
        current_active = self.path_repo.get_all(scope, active_only=True)
        backup_set = {normalize_path(p) for p in backup.path_snapshot}
        for entry in current_active:
            if normalize_path(entry.path) not in backup_set:
                self.path_repo.set_active(entry.path, scope, False)

        result.restored = len(backup.path_snapshot)
        return result

    # ==================== INTEGRITY CHECK ====================

    def verify_backup(self, backup_id: int) -> bool:
        """Verifica integridade do backup (checksum SHA-256)."""
        return self.backup_repo.verify_integrity(backup_id)

    def verify_all_backups(self, scope: Scope = None) -> list[tuple[int, bool]]:
        """Verifica todos os backups."""
        backups = self.backup_repo.list_all(scope)
        return [(b.id, self.backup_repo.verify_integrity(b.id)) for b in backups]

    # ==================== CLEANUP ====================

    def cleanup_old_backups(self, scope: Scope = None, max_backups: int = 10, max_age_days: int = 90) -> int:
        """Remove backups antigos (mantem mais recentes ate max_backups, remove > max_age_days)."""
        backups = self.backup_repo.list_all(scope, limit=1000)
        removed = 0

        # Remove por idade
        cutoff = datetime.now() - timedelta(days=max_age_days)
        for backup in backups:
            if backup.created_at and backup.created_at < cutoff:
                self.backup_repo.delete(backup.id)
                removed += 1

        # Remove excedentes (mantem mais recentes)
        remaining = self.backup_repo.list_all(scope, limit=1000)
        if len(remaining) > max_backups:
            for backup in remaining[max_backups:]:
                self.backup_repo.delete(backup.id)
                removed += 1

        return removed

    # ==================== SCHEDULER ====================

    def set_schedule(self, enabled: bool, interval_hours: int = 24, scope: Scope = Scope.USER, max_backups: int = 10):
        """Configura agendamento automatico de backups."""
        self._schedule = BackupSchedule(
            enabled=enabled,
            interval_hours=interval_hours,
            scope=scope,
            max_backups=max_backups,
            next_run=datetime.now() + timedelta(hours=interval_hours) if enabled else None,
        )

        if enabled:
            self._start_scheduler()
        else:
            self._stop_scheduler()

    def _start_scheduler(self):
        if self._running:
            return
        self._running = True
        self._scheduler = sched.scheduler(time.time, time.sleep)
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        print_info(f"Scheduler de backup iniciado (intervalo: {self._schedule.interval_hours}h)")

    def _stop_scheduler(self):
        self._running = False
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)
        print_info("Scheduler de backup parado")

    def _run_scheduler(self):
        while self._running:
            now = datetime.now()
            if self._schedule.next_run and now >= self._schedule.next_run:
                try:
                    self._run_scheduled_backup()
                except Exception as e:
                    print_warning(f"Backup agendado falhou: {e}")
                # Agenda proximo
                self._schedule.next_run = now + timedelta(hours=self._schedule.interval_hours)
            time.sleep(60)  # Checa a cada minuto

    def _run_scheduled_backup(self):
        name = f"scheduled-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        paths = self.win_api.get_path(self._schedule.scope)
        backup = Backup(
            name=name,
            scope=self._schedule.scope,
            path_snapshot=paths,
            description="Backup agendado automatico",
        )
        self.backup_repo.create(backup)
        print_info(f"Backup agendado criado: {name} ({len(paths)} paths)")

        # Cleanup apos backup
        self.cleanup_old_backups(self._schedule.scope, self._schedule.max_backups)

    def get_schedule_status(self) -> dict:
        return {
            "enabled": self._schedule.enabled,
            "interval_hours": self._schedule.interval_hours,
            "scope": self._schedule.scope.value,
            "max_backups": self._schedule.max_backups,
            "next_run": self._schedule.next_run.isoformat() if self._schedule.next_run else None,
        }


class PathService:
    """Servico de operacoes no PATH."""

    def __init__(self):
        self.path_repo = PathEntryRepository()
        self.backup_repo = BackupRepository()
        self.log_repo = OperationLogRepository()
        self.win_api = WindowsPathAPI()
        self.backup_service = BackupService(self)

    def list_paths(self, scope: Scope, active_only: bool = True) -> list[PathEntry]:
        return self.path_repo.get_all(scope, active_only)

    # ==================== BACKUP DELEGATION ====================

    def create_backup(self, name: str, scope: Scope, description: str = "") -> Backup:
        """Cria backup manual."""
        paths = self.win_api.get_path(scope)
        backup = Backup(name=name, scope=scope, path_snapshot=paths, description=description)
        return self.backup_repo.create(backup)

    def restore_backup_merge(self, backup_id: int, scope: Scope, dry_run: bool = False) -> RestoreResult:
        """Restore merge: adiciona paths que faltam."""
        return self.backup_service.restore_merge(backup_id, scope, dry_run)

    def restore_backup_full(self, backup_id: int, scope: Scope, dry_run: bool = False) -> RestoreResult:
        """Restore full: substitui PATH atual."""
        return self.backup_service.restore_full(backup_id, scope, dry_run)

    def verify_backup(self, backup_id: int) -> bool:
        return self.backup_service.verify_backup(backup_id)

    def verify_all_backups(self, scope: Scope = None) -> list[tuple[int, bool]]:
        return self.backup_service.verify_all_backups(scope)

    def cleanup_backups(self, scope: Scope = None, max_backups: int = 10, max_age_days: int = 90) -> int:
        return self.backup_service.cleanup_old_backups(scope, max_backups, max_age_days)

    def set_backup_schedule(self, enabled: bool, interval_hours: int = 24, scope: Scope = Scope.USER, max_backups: int = 10):
        self.backup_service.set_schedule(enabled, interval_hours, scope, max_backups)

    def get_backup_schedule_status(self) -> dict:
        return self.backup_service.get_schedule_status()

    def _auto_backup_if_enabled(self, scope: Scope, operation: str, description: str = ""):
        """Hook para auto-backup antes de operacoes destrutivas."""
        if settings.auto_backup:
            return self.backup_service.auto_backup_before_change(scope, operation, description)
        return None

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

        # Auto-backup antes de remover
        self._auto_backup_if_enabled(scope, "remove_path", path)

        self.path_repo.set_active(path, scope, False)
        self._sync_to_windows(scope)
        self._log(OperationType.REMOVE, scope, path, OperationStatus.SUCCESS)
        return OperationResult(True, f"Path removido (desativado): {path}")

    # ==================== BULK OPERATIONS ====================

    def add_paths_bulk(self, paths: list[str], scope: Scope, description: str = "") -> BulkOperationResult:
        """Adiciona multiplos paths de uma vez."""
        result = BulkOperationResult(success=0, failed=0, errors=[], entries=[])

        for path in paths:
            path = path.strip()
            if not path:
                continue
            op_result = self.add_path(path, scope, description)
            if op_result.success:
                result.success += 1
                if op_result.entry:
                    result.entries.append(op_result.entry)
            else:
                result.failed += 1
                result.errors.append(f"{path}: {op_result.message}")

        return result

    def remove_paths_bulk(self, paths: list[str], scope: Scope) -> BulkOperationResult:
        """Remove multiplos paths de uma vez."""
        result = BulkOperationResult(success=0, failed=0, errors=[], entries=[])

        for path in paths:
            path = path.strip()
            if not path:
                continue
            op_result = self.remove_path(path, scope)
            if op_result.success:
                result.success += 1
            else:
                result.failed += 1
                result.errors.append(f"{path}: {op_result.message}")

        return result

    # ==================== REORDER OPERATIONS ====================

    def move_path_up(self, path: str, scope: Scope) -> OperationResult:
        """Move path uma posicao para cima (prioridade maior)."""
        path = normalize_path(path)
        entries = self.path_repo.get_all(scope, active_only=True)

        idx = next((i for i, e in enumerate(entries) if normalize_path(e.path) == path), -1)
        if idx <= 0:
            return OperationResult(False, "Path ja esta no topo ou nao encontrado")

        # Swap positions
        entries[idx], entries[idx - 1] = entries[idx - 1], entries[idx]
        self.path_repo.reorder(entries)
        self._sync_to_windows(scope)
        self._log(OperationType.REORDER, scope, path, OperationStatus.SUCCESS, metadata={"direction": "up"})
        return OperationResult(True, f"Path movido para cima: {path}")

    def move_path_down(self, path: str, scope: Scope) -> OperationResult:
        """Move path uma posicao para baixo (prioridade menor)."""
        path = normalize_path(path)
        entries = self.path_repo.get_all(scope, active_only=True)

        idx = next((i for i, e in enumerate(entries) if normalize_path(e.path) == path), -1)
        if idx < 0 or idx >= len(entries) - 1:
            return OperationResult(False, "Path ja esta no final ou nao encontrado")

        entries[idx], entries[idx + 1] = entries[idx + 1], entries[idx]
        self.path_repo.reorder(entries)
        self._sync_to_windows(scope)
        self._log(OperationType.REORDER, scope, path, OperationStatus.SUCCESS, metadata={"direction": "down"})
        return OperationResult(True, f"Path movido para baixo: {path}")

    def move_path_to_position(self, path: str, scope: Scope, new_position: int) -> OperationResult:
        """Move path para posicao especifica (0-indexed)."""
        path = normalize_path(path)
        entries = self.path_repo.get_all(scope, active_only=True)

        idx = next((i for i, e in enumerate(entries) if normalize_path(e.path) == path), -1)
        if idx < 0:
            return OperationResult(False, "Path nao encontrado")

        if new_position < 0:
            new_position = 0
        if new_position >= len(entries):
            new_position = len(entries) - 1

        if idx == new_position:
            return OperationResult(True, "Path ja esta na posicao desejada")

        # Remove and insert at new position
        entry = entries.pop(idx)
        entries.insert(new_position, entry)
        self.path_repo.reorder(entries)
        self._sync_to_windows(scope)
        self._log(OperationType.REORDER, scope, path, OperationStatus.SUCCESS,
                  metadata={"from": idx, "to": new_position})
        return OperationResult(True, f"Path movido para posicao {new_position + 1}: {path}")

    def reorder_by_priority(self, scope: Scope, priority_paths: list[str]) -> OperationResult:
        """Reordena paths colocando os prioritarios no topo (na ordem dada)."""
        entries = self.path_repo.get_all(scope, active_only=True)
        entry_map = {normalize_path(e.path): e for e in entries}

        new_order = []
        seen = set()

        # Primeiro adiciona paths prioritarios na ordem
        for p in priority_paths:
            norm = normalize_path(p)
            if norm in entry_map and norm not in seen:
                new_order.append(entry_map[norm])
                seen.add(norm)

        # Depois adiciona o resto
        for e in entries:
            norm = normalize_path(e.path)
            if norm not in seen:
                new_order.append(e)

        self.path_repo.reorder(new_order)
        self._sync_to_windows(scope)
        self._log(OperationType.REORDER, scope, "", OperationStatus.SUCCESS,
                  metadata={"priority_count": len(priority_paths)})
        return OperationResult(True, f"Reordenado: {len(priority_paths)} prioritarios no topo")

    # ==================== IMPORT/EXPORT ====================

    def export_to_json(self, scope: Scope, file_path: str, active_only: bool = True) -> OperationResult:
        """Exporta paths para JSON."""
        try:
            entries = self.path_repo.get_all(scope, active_only)
            data = {
                "scope": scope.value,
                "exported_at": __import__("datetime").datetime.now().isoformat(),
                "count": len(entries),
                "paths": [
                    {
                        "path": e.path,
                        "active": e.active,
                        "position": e.position,
                        "description": e.description,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in entries
                ]
            }
            Path(file_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return OperationResult(True, f"Exportado {len(entries)} paths para {file_path}")
        except Exception as e:
            return OperationResult(False, f"Erro ao exportar: {e}")

    def export_to_csv(self, scope: Scope, file_path: str, active_only: bool = True) -> OperationResult:
        """Exporta paths para CSV."""
        try:
            entries = self.path_repo.get_all(scope, active_only)
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["path", "active", "position", "description", "created_at"])
                for e in entries:
                    writer.writerow([
                        e.path,
                        "true" if e.active else "false",
                        e.position,
                        e.description,
                        e.created_at.isoformat() if e.created_at else ""
                    ])
            return OperationResult(True, f"Exportado {len(entries)} paths para {file_path}")
        except Exception as e:
            return OperationResult(False, f"Erro ao exportar: {e}")

    def import_from_json(self, file_path: str, scope: Scope, merge: bool = True) -> ImportResult:
        """Importa paths de JSON."""
        result = ImportResult(imported=0, skipped=0, errors=[])

        try:
            data = json.loads(Path(file_path).read_text(encoding="utf-8"))
            paths_data = data.get("paths", [])

            for item in paths_data:
                path = item.get("path", "").strip()
                if not path:
                    continue

                existing = self.path_repo.get_by_path(path, scope)
                if existing and existing.active:
                    result.skipped += 1
                    continue

                desc = item.get("description", "")
                op_result = self.add_path(path, scope, desc)
                if op_result.success:
                    result.imported += 1
                else:
                    result.errors.append(f"{path}: {op_result.message}")

            return result
        except Exception as e:
            result.errors.append(f"Erro ao ler arquivo: {e}")
            return result

    def import_from_csv(self, file_path: str, scope: Scope, merge: bool = True) -> ImportResult:
        """Importa paths de CSV (colunas: path, active, description)."""
        result = ImportResult(imported=0, skipped=0, errors=[])

        try:
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    path = row.get("path", "").strip()
                    if not path:
                        continue

                    existing = self.path_repo.get_by_path(path, scope)
                    if existing and existing.active:
                        result.skipped += 1
                        continue

                    desc = row.get("description", "")
                    op_result = self.add_path(path, scope, desc)
                    if op_result.success:
                        result.imported += 1
                    else:
                        result.errors.append(f"{path}: {op_result.message}")

            return result
        except Exception as e:
            result.errors.append(f"Erro ao ler arquivo: {e}")
            return result

    # ==================== ADVANCED SYNC ====================

    def sync_with_conflicts(self, scope: Scope, strategy: str = "keep_db") -> SyncResult:
        """Sync avançado com resolucao de conflitos.
        
        strategy: keep_db | keep_windows | keep_both | interactive
        """
        system_paths = self.win_api.get_path(scope)
        db_entries = self.path_repo.get_all(scope, active_only=False)
        db_paths = {normalize_path(e.path): e for e in db_entries}

        result = SyncResult()
        conflicts = []

        # Detecta conflitos
        for spath in system_paths:
            norm = normalize_path(spath)
            if norm in db_paths:
                db_entry = db_paths[norm]
                if not db_entry.active:
                    # Path existe no Windows mas inativo no DB -> conflito
                    conflicts.append(SyncConflict(
                        path=spath,
                        in_windows=True,
                        in_db=True,
                        db_active=False,
                        resolution="keep_windows" if strategy == "keep_windows" else "keep_db"
                    ))

        # Aplica estrategia
        for conflict in conflicts:
            if conflict.resolution == "keep_windows":
                # Reativa no DB
                self.path_repo.set_active(conflict.path, scope, True)
                result.added.append(conflict.path)
            else:
                # Remove do Windows (desativa no DB ja esta)
                result.removed.append(conflict.path)

        # Paths so no Windows
        for spath in system_paths:
            norm = normalize_path(spath)
            if norm not in db_paths:
                entry = PathEntry(path=norm, scope=scope, active=True, position=len(db_entries))
                self.path_repo.create(entry)
                db_entries.append(entry)
                result.added.append(spath)
            elif norm not in [c.path for c in conflicts]:
                result.unchanged.append(spath)

        # Paths so no DB (ativos)
        sys_paths_norm = {normalize_path(p) for p in system_paths}
        for entry in db_entries:
            if normalize_path(entry.path) not in sys_paths_norm and entry.active:
                if strategy == "keep_both":
                    # Mantem no DB mas nao toca no Windows
                    result.unchanged.append(entry.path)
                else:
                    self.path_repo.set_active(entry.path, scope, False)
                    result.removed.append(entry.path)

        result.drift_detected = len(result.added) > 0 or len(result.removed) > 0
        return result

    def detect_conflicts(self, scope: Scope) -> list[SyncConflict]:
        """Detecta conflitos entre Windows e DB sem resolver."""
        system_paths = self.win_api.get_path(scope)
        db_entries = self.path_repo.get_all(scope, active_only=False)
        db_paths = {normalize_path(e.path): e for e in db_entries}

        conflicts = []
        sys_paths_norm = {normalize_path(p) for p in system_paths}

        # No Windows mas inativo no DB
        for spath in system_paths:
            norm = normalize_path(spath)
            if norm in db_paths and not db_paths[norm].active:
                conflicts.append(SyncConflict(
                    path=spath, in_windows=True, in_db=True, db_active=False, resolution="keep_windows"
                ))

        # Ativo no DB mas nao no Windows
        for entry in db_entries:
            norm = normalize_path(entry.path)
            if norm not in sys_paths_norm and entry.active:
                conflicts.append(SyncConflict(
                    path=entry.path, in_windows=False, in_db=True, db_active=True, resolution="keep_db"
                ))

        return conflicts

    # ==================== ADVANCED VALIDATION ====================

    def validate_paths_detailed(self, scope: Scope) -> ValidationResult:
        """Validacao avancada com expansao de variaveis."""
        entries = self.path_repo.get_all(scope, active_only=True)
        result = ValidationResult()

        seen = set()
        for entry in entries:
            # Expande variaveis de ambiente
            expanded = expand_path(entry.path)
            norm = normalize_path(expanded)

            if norm in seen:
                result.duplicates.append(entry.path)
                continue
            seen.add(norm)

            if path_exists(norm):
                result.valid.append(entry.path)
            else:
                # Tenta path original sem expansao
                orig_norm = normalize_path(entry.path)
                if path_exists(orig_norm):
                    result.valid.append(entry.path)
                else:
                    result.missing.append(entry.path)

        # Verifica invalidos
        for entry in entries:
            if not is_valid_path(entry.path):
                result.invalid.append(entry.path)

        return result

    def expand_variables_in_db(self, scope: Scope) -> OperationResult:
        """Expande variaveis de ambiente nos paths salvos no DB."""
        entries = self.path_repo.get_all(scope, active_only=False)
        updated = 0

        for entry in entries:
            expanded = expand_path(entry.path)
            norm = normalize_path(expanded)
            if norm != entry.path:
                entry.path = norm
                self.path_repo.update(entry)
                updated += 1

        if updated > 0:
            self._sync_to_windows(scope)

        return OperationResult(True, f"Variaveis expandidas em {updated} paths")

    # ==================== EXISTING METHODS ====================

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

        for entry in entries:
            if not is_valid_path(entry.path):
                result.invalid.append(entry.path)

        return result

    def sync_from_system(self, scope: Scope) -> SyncResult:
        """Sincroniza DB com PATH real do Windows (basico)."""
        system_paths = self.win_api.get_path(scope)
        db_entries = self.path_repo.get_all(scope, active_only=False)
        db_paths = {normalize_path(e.path) for e in db_entries}

        result = SyncResult()

        for spath in system_paths:
            norm = normalize_path(spath)
            if norm not in db_paths:
                entry = PathEntry(path=norm, scope=scope, active=True, position=len(db_entries))
                self.path_repo.create(entry)
                db_entries.append(entry)
                result.added.append(spath)
            else:
                result.unchanged.append(spath)

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
