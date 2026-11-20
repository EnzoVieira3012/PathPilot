"""Repository Pattern - Acesso a dados."""

import json
from datetime import datetime

from .db import get_db
from .models import Backup, EnvVar, OperationLog, OperationStatus, OperationType, PathEntry, Scope


class BaseRepository:
    def __init__(self):
        self.db = get_db()


class PathEntryRepository(BaseRepository):
    def _row_to_entry(self, row) -> PathEntry:
        return PathEntry(
            id=row['id'],
            path=row['path'],
            scope=Scope(row['scope']),
            active=bool(row['active']),
            position=row['position'],
            description=row['description'] or '',
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    def get_all(self, scope: Scope, active_only: bool = True) -> list[PathEntry]:
        sql = 'SELECT * FROM path_entries WHERE scope = ?'
        params = [scope.value]
        if active_only:
            sql += ' AND active = 1'
        sql += ' ORDER BY position, created_at'
        rows = self.db.fetchall(sql, tuple(params))
        return [self._row_to_entry(r) for r in rows]

    def get_by_path(self, path: str, scope: Scope) -> PathEntry | None:
        row = self.db.fetchone(
            'SELECT * FROM path_entries WHERE path = ? AND scope = ?', (path, scope.value)
        )
        return self._row_to_entry(row) if row else None

    def create(self, entry: PathEntry) -> PathEntry:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO path_entries (path, scope, active, position, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (entry.path, entry.scope.value, entry.active, entry.position, entry.description),
            )
            entry.id = cursor.lastrowid
        return entry

    def update(self, entry: PathEntry) -> PathEntry:
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE path_entries SET path=?, active=?, position=?, description=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (entry.path, entry.active, entry.position, entry.description, entry.id),
            )
        return entry

    def delete(self, path: str, scope: Scope) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                'DELETE FROM path_entries WHERE path = ? AND scope = ?', (path, scope.value)
            )
        return cursor.rowcount > 0

    def reorder(self, entries: list[PathEntry]) -> None:
        with self.db.transaction() as conn:
            for idx, entry in enumerate(entries):
                entry.position = idx
                conn.execute(
                    'UPDATE path_entries SET position=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                    (entry.position, entry.id),
                )

    def set_active(self, path: str, scope: Scope, active: bool) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                'UPDATE path_entries SET active=?, updated_at=CURRENT_TIMESTAMP WHERE path=? AND scope=?',
                (active, path, scope.value),
            )
        return cursor.rowcount > 0


class EnvVarRepository(BaseRepository):
    def _row_to_envvar(self, row) -> EnvVar:
        return EnvVar(
            id=row['id'],
            name=row['name'],
            value=row['value'],
            scope=Scope(row['scope']),
            description=row['description'] or '',
            encrypted=bool(row['encrypted']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )

    def get_all(self, scope: Scope | None = None) -> list[EnvVar]:
        if scope:
            rows = self.db.fetchall(
                'SELECT * FROM env_vars WHERE scope = ? ORDER BY name', (scope.value,)
            )
        else:
            rows = self.db.fetchall('SELECT * FROM env_vars ORDER BY name')
        return [self._row_to_envvar(r) for r in rows]

    def get_by_name(self, name: str, scope: Scope) -> EnvVar | None:
        row = self.db.fetchone(
            'SELECT * FROM env_vars WHERE name = ? AND scope = ?', (name, scope.value)
        )
        return self._row_to_envvar(row) if row else None

    def create(self, env_var: EnvVar) -> EnvVar:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO env_vars (name, value, scope, description, encrypted)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    env_var.name,
                    env_var.value,
                    env_var.scope.value,
                    env_var.description,
                    env_var.encrypted,
                ),
            )
            env_var.id = cursor.lastrowid
        return env_var

    def update(self, env_var: EnvVar) -> EnvVar:
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE env_vars SET value=?, description=?, encrypted=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (env_var.value, env_var.description, env_var.encrypted, env_var.id),
            )
        return env_var

    def delete(self, name: str, scope: Scope) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                'DELETE FROM env_vars WHERE name = ? AND scope = ?', (name, scope.value)
            )
        return cursor.rowcount > 0


class BackupRepository(BaseRepository):
    def _row_to_backup(self, row) -> Backup:
        return Backup(
            id=row['id'],
            name=row['name'],
            scope=Scope(row['scope']),
            path_snapshot=json.loads(row['path_snapshot']),
            description=row['description'] or '',
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
        )

    def create(self, backup: Backup) -> Backup:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO backups (name, scope, path_snapshot, description)
                   VALUES (?, ?, ?, ?)""",
                (
                    backup.name,
                    backup.scope.value,
                    json.dumps(backup.path_snapshot),
                    backup.description,
                ),
            )
            backup.id = cursor.lastrowid
        return backup

    def get_latest(self, scope: Scope) -> Backup | None:
        row = self.db.fetchone(
            'SELECT * FROM backups WHERE scope = ? ORDER BY created_at DESC LIMIT 1', (scope.value,)
        )
        return self._row_to_backup(row) if row else None

    def get_by_id(self, backup_id: int) -> Backup | None:
        row = self.db.fetchone('SELECT * FROM backups WHERE id = ?', (backup_id,))
        return self._row_to_backup(row) if row else None

    def list_all(self, scope: Scope | None = None, limit: int = 50) -> list[Backup]:
        if scope:
            rows = self.db.fetchall(
                'SELECT * FROM backups WHERE scope = ? ORDER BY created_at DESC LIMIT ?',
                (scope.value, limit),
            )
        else:
            rows = self.db.fetchall(
                'SELECT * FROM backups ORDER BY created_at DESC LIMIT ?', (limit,)
            )
        return [self._row_to_backup(r) for r in rows]

    def delete(self, backup_id: int) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
        return cursor.rowcount > 0


class OperationLogRepository(BaseRepository):
    def _row_to_log(self, row) -> OperationLog:
        return OperationLog(
            id=row['id'],
            operation=OperationType(row['operation']),
            scope=Scope(row['scope']) if row['scope'] else None,
            target_path=row['target_path'] or '',
            status=OperationStatus(row['status']),
            error_message=row['error_message'] or '',
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
        )

    def log(self, log: OperationLog) -> OperationLog:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO operation_log (operation, scope, target_path, status, error_message, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    log.operation.value,
                    log.scope.value if log.scope else None,
                    log.target_path,
                    log.status.value,
                    log.error_message,
                    json.dumps(log.metadata),
                ),
            )
            log.id = cursor.lastrowid
        return log

    def get_recent(self, limit: int = 100) -> list[OperationLog]:
        rows = self.db.fetchall(
            'SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?', (limit,)
        )
        return [self._row_to_log(r) for r in rows]
