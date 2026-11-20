"""Repository Pattern - Acesso a dados."""

import hashlib
import json
from datetime import datetime

from .crypto import get_crypto
from .db import get_db
from .models import Backup, EnvVar, OperationLog, OperationStatus, OperationType, PathEntry, Scope
from .utils import normalize_path, path_exists


class ValidationError(Exception):
    """Erro de validacao de repository."""
    pass


class BaseRepository:
    def __init__(self):
        self.db = get_db()


class PathEntryRepository(BaseRepository):
    def _row_to_entry(self, row) -> PathEntry:
        return PathEntry(
            id=row["id"],
            path=row["path"],
            scope=Scope(row["scope"]),
            active=bool(row["active"]),
            position=row["position"],
            description=row["description"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def _validate_path(self, path: str, scope: Scope) -> None:
        """Validacoes de negocio para path."""
        if not path or not path.strip():
            raise ValidationError("Path nao pode ser vazio")

        norm = normalize_path(path)
        if norm != path:
            raise ValidationError(f"Path deve estar normalizado: {norm}")

        dangerous = ["..", "|", "&", ";", "$(", "`"]
        for d in dangerous:
            if d in path:
                raise ValidationError(f"Caractere perigoso detectado: {d}")

        existing = self.get_by_path(norm, scope)
        if existing and existing.active:
            raise ValidationError(f"Path ja existe e esta ativo: {norm}")

    def get_all(self, scope: Scope, active_only: bool = True) -> list[PathEntry]:
        sql = "SELECT * FROM path_entries WHERE scope = ?"
        params = [scope.value]
        if active_only:
            sql += " AND active = 1"
        sql += " ORDER BY position, created_at"
        rows = self.db.fetchall(sql, tuple(params))
        return [self._row_to_entry(r) for r in rows]

    def get_by_path(self, path: str, scope: Scope) -> PathEntry | None:
        norm = normalize_path(path)
        row = self.db.fetchone(
            "SELECT * FROM path_entries WHERE path = ? AND scope = ?",
            (norm, scope.value)
        )
        return self._row_to_entry(row) if row else None

    def create(self, entry: PathEntry) -> PathEntry:
        self._validate_path(entry.path, entry.scope)
        norm = normalize_path(entry.path)

        with self.db.transaction() as conn:
            if entry.position < 0:
                row = conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM path_entries WHERE scope = ?",
                    (entry.scope.value,)
                ).fetchone()
                entry.position = row[0] if row else 0

            cursor = conn.execute(
                """INSERT INTO path_entries (path, scope, active, position, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (norm, entry.scope.value, entry.active, entry.position, entry.description)
            )
            entry.id = cursor.lastrowid
        return entry

    def update(self, entry: PathEntry) -> PathEntry:
        norm = normalize_path(entry.path)
        self._validate_path(norm, entry.scope)

        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE path_entries SET path=?, active=?, position=?, description=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (norm, entry.active, entry.position, entry.description, entry.id)
            )
        return entry

    def delete(self, path: str, scope: Scope) -> bool:
        norm = normalize_path(path)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM path_entries WHERE path = ? AND scope = ?",
                (norm, scope.value)
            )
        return cursor.rowcount > 0

    def reorder(self, entries: list[PathEntry]) -> None:
        with self.db.transaction() as conn:
            for idx, entry in enumerate(entries):
                entry.position = idx
                conn.execute(
                    "UPDATE path_entries SET position=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (entry.position, entry.id)
                )

    def set_active(self, path: str, scope: Scope, active: bool) -> bool:
        norm = normalize_path(path)
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE path_entries SET active=?, updated_at=CURRENT_TIMESTAMP WHERE path=? AND scope=?",
                (active, norm, scope.value)
            )
        return cursor.rowcount > 0

    def get_count(self, scope: Scope, active_only: bool = True) -> int:
        sql = "SELECT COUNT(*) as c FROM path_entries WHERE scope = ?"
        params = [scope.value]
        if active_only:
            sql += " AND active = 1"
        row = self.db.fetchone(sql, tuple(params))
        return row["c"] if row else 0

    def find_duplicates(self, scope: Scope) -> list[str]:
        rows = self.db.fetchall(
            """SELECT path, COUNT(*) as cnt FROM path_entries
               WHERE scope = ? GROUP BY path HAVING cnt > 1""",
            (scope.value,)
        )
        return [r["path"] for r in rows]

    def find_missing_on_disk(self, scope: Scope) -> list[PathEntry]:
        entries = self.get_all(scope, active_only=True)
        return [e for e in entries if not path_exists(e.path)]


class EnvVarRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self._crypto = get_crypto()

    def _row_to_envvar(self, row) -> EnvVar:
        value = row["value"]
        if row["encrypted"] and value:
            try:
                value = self._crypto.decrypt(value)
            except Exception:
                value = f"[DECRYPT ERROR: {value[:20]}...]"

        return EnvVar(
            id=row["id"],
            name=row["name"],
            value=value,
            scope=Scope(row["scope"]),
            description=row["description"] or "",
            encrypted=bool(row["encrypted"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def _validate_name(self, name: str, scope: Scope, exclude_id: int = None) -> None:
        if not name or not name.strip():
            raise ValidationError("Nome nao pode ser vazio")

        import re
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValidationError(f"Nome invalido para variavel de ambiente: {name}")

        existing = self.get_by_name(name, scope)
        if existing and existing.id != exclude_id:
            raise ValidationError(f"Variavel ja existe: {name}")

    def get_all(self, scope: Scope | None = None) -> list[EnvVar]:
        if scope:
            rows = self.db.fetchall("SELECT * FROM env_vars WHERE scope = ? ORDER BY name", (scope.value,))
        else:
            rows = self.db.fetchall("SELECT * FROM env_vars ORDER BY name")
        return [self._row_to_envvar(r) for r in rows]

    def get_by_name(self, name: str, scope: Scope) -> EnvVar | None:
        row = self.db.fetchone(
            "SELECT * FROM env_vars WHERE name = ? AND scope = ?",
            (name, scope.value)
        )
        return self._row_to_envvar(row) if row else None

    def _encrypt_if_needed(self, value: str, encrypted: bool) -> str:
        """Criptografa valor se encrypted=True."""
        if encrypted and value:
            return self._crypto.encrypt(value)
        return value

    def create(self, env_var: EnvVar) -> EnvVar:
        self._validate_name(env_var.name, env_var.scope)

        # Criptografa se necessario
        stored_value = self._encrypt_if_needed(env_var.value, env_var.encrypted)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO env_vars (name, value, scope, description, encrypted)
                   VALUES (?, ?, ?, ?, ?)""",
                (env_var.name, stored_value, env_var.scope.value, env_var.description, env_var.encrypted)
            )
            env_var.id = cursor.lastrowid
        return env_var

    def update(self, env_var: EnvVar) -> EnvVar:
        self._validate_name(env_var.name, env_var.scope, exclude_id=env_var.id)

        # Criptografa se necessario
        stored_value = self._encrypt_if_needed(env_var.value, env_var.encrypted)

        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE env_vars SET value=?, description=?, encrypted=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (stored_value, env_var.description, env_var.encrypted, env_var.id)
            )
        return env_var

    def delete(self, name: str, scope: Scope) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM env_vars WHERE name = ? AND scope = ?",
                (name, scope.value)
            )
        return cursor.rowcount > 0

    def get_count(self, scope: Scope | None = None) -> int:
        if scope:
            row = self.db.fetchone("SELECT COUNT(*) as c FROM env_vars WHERE scope = ?", (scope.value,))
        else:
            row = self.db.fetchone("SELECT COUNT(*) as c FROM env_vars")
        return row["c"] if row else 0


class BackupRepository(BaseRepository):
    def _row_to_backup(self, row) -> Backup:
        return Backup(
            id=row["id"],
            name=row["name"],
            scope=Scope(row["scope"]),
            path_snapshot=json.loads(row["path_snapshot"]),
            description=row["description"] or "",
            checksum=row["checksum"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def _compute_checksum(self, paths: list[str]) -> str:
        content = "\n".join(sorted(paths))
        return hashlib.sha256(content.encode()).hexdigest()

    def create(self, backup: Backup) -> Backup:
        if not backup.name or not backup.name.strip():
            raise ValidationError("Nome do backup nao pode ser vazio")

        if not backup.path_snapshot:
            raise ValidationError("Snapshot vazio")

        backup.checksum = self._compute_checksum(backup.path_snapshot)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO backups (name, scope, path_snapshot, description, checksum)
                   VALUES (?, ?, ?, ?, ?)""",
                (backup.name, backup.scope.value, json.dumps(backup.path_snapshot), backup.description, backup.checksum)
            )
            backup.id = cursor.lastrowid
        return backup

    def get_latest(self, scope: Scope) -> Backup | None:
        row = self.db.fetchone(
            "SELECT * FROM backups WHERE scope = ? ORDER BY created_at DESC LIMIT 1",
            (scope.value,)
        )
        return self._row_to_backup(row) if row else None

    def get_by_id(self, backup_id: int) -> Backup | None:
        row = self.db.fetchone("SELECT * FROM backups WHERE id = ?", (backup_id,))
        return self._row_to_backup(row) if row else None

    def list_all(self, scope: Scope | None = None, limit: int = 50) -> list[Backup]:
        if scope:
            rows = self.db.fetchall(
                "SELECT * FROM backups WHERE scope = ? ORDER BY created_at DESC LIMIT ?",
                (scope.value, limit)
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM backups ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        return [self._row_to_backup(r) for r in rows]

    def delete(self, backup_id: int) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
        return cursor.rowcount > 0

    def verify_integrity(self, backup_id: int) -> bool:
        backup = self.get_by_id(backup_id)
        if not backup or not backup.checksum:
            return False
        current_checksum = self._compute_checksum(backup.path_snapshot)
        return current_checksum == backup.checksum

    def get_count(self, scope: Scope | None = None) -> int:
        if scope:
            row = self.db.fetchone("SELECT COUNT(*) as c FROM backups WHERE scope = ?", (scope.value,))
        else:
            row = self.db.fetchone("SELECT COUNT(*) as c FROM backups")
        return row["c"] if row else 0


class OperationLogRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self._crypto = get_crypto()

    def _row_to_log(self, row) -> OperationLog:
        return OperationLog(
            id=row["id"],
            operation=OperationType(row["operation"]),
            scope=Scope(row["scope"]) if row["scope"] else None,
            target_path=row["target_path"] or "",
            status=OperationStatus(row["status"]),
            error_message=row["error_message"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def _compute_hmac(self, log: OperationLog) -> str:
        """Computa HMAC do log para integridade."""
        data = f"{log.operation.value}|{log.scope.value if log.scope else ''}|{log.target_path}|{log.status.value}|{log.error_message}|{json.dumps(log.metadata)}"
        return self._crypto.sign(data)

    def log(self, log: OperationLog) -> OperationLog:
        if not log.target_path and log.operation in (OperationType.ADD, OperationType.REMOVE):
            raise ValidationError("target_path obrigatorio para ADD/REMOVE")

        # Adiciona HMAC ao metadata
        if log.metadata is None:
            log.metadata = {}
        log.metadata["_hmac"] = self._compute_hmac(log)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO operation_log (operation, scope, target_path, status, error_message, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (log.operation.value, log.scope.value if log.scope else None,
                 log.target_path, log.status.value, log.error_message, json.dumps(log.metadata))
            )
            log.id = cursor.lastrowid
        return log

    def verify_log_integrity(self, log: OperationLog) -> bool:
        """Verifica integridade do log via HMAC."""
        stored_hmac = log.metadata.get("_hmac") if log.metadata else None
        if not stored_hmac:
            return False
        computed = self._compute_hmac(log)
        return self._crypto.verify(computed, stored_hmac)

    def get_recent(self, limit: int = 100) -> list[OperationLog]:
        rows = self.db.fetchall(
            "SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_log(r) for r in rows]

    def get_by_operation(self, operation: OperationType, limit: int = 50) -> list[OperationLog]:
        rows = self.db.fetchall(
            "SELECT * FROM operation_log WHERE operation = ? ORDER BY created_at DESC LIMIT ?",
            (operation.value, limit)
        )
        return [self._row_to_log(r) for r in rows]

    def get_count(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) as c FROM operation_log")
        return row["c"] if row else 0

    def cleanup_old(self, days: int = 90) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM operation_log WHERE created_at < datetime('now', ?)",
                (f"-{days} days",)
            )
        return cursor.rowcount


class UserSettingsRepository(BaseRepository):
    """Configuracoes persistentes do usuario."""

    def get(self, key: str, default: str = None) -> str | None:
        row = self.db.fetchone("SELECT value FROM user_settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set(self, key: str, value: str, description: str = "") -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO user_settings (key, value, description, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                (key, value, description)
            )

    def delete(self, key: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM user_settings WHERE key = ?", (key,))
        return cursor.rowcount > 0

    def list_all(self) -> dict:
        rows = self.db.fetchall("SELECT key, value, description FROM user_settings")
        return {r["key"]: {"value": r["value"], "description": r["description"]} for r in rows}
