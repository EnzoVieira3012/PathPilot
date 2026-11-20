# Referência da API

## Módulos

| Módulo | Descrição |
|--------|-----------|
| `pathpilot.cli` | Entry point Typer + comandos Rich |
| `pathpilot.core` | `PathService`, `BackupService` — lógica de negócio |
| `pathpilot.models` | Dataclasses Pydantic tipadas |
| `pathpilot.db` | `Database` singleton, conexões thread-local WAL |
| `pathpilot.migrations` | Sistema migrações versionadas + seeds |
| `pathpilot.repositories` | Repository pattern para cada entidade |
| `pathpilot.crypto` | `CryptoService` — Fernet + HMAC + SHA-256 |
| `pathpilot.windows_api` | `WindowsPathAPI` — wrapper `winreg` |
| `pathpilot.utils` | Helpers (paths, validação, sanitização) |
| `pathpilot.config` | `Settings` — config via pydantic-settings |

## Uso Programático

```python
from pathpilot.core import PathService, BackupService
from pathpilot.models import Scope, PathEntry, Backup
from pathpilot.repositories import (
    PathEntryRepository, EnvVarRepository,
    BackupRepository, OperationLogRepository,
    UserSettingsRepository
)
from pathpilot.crypto import CryptoService
from pathpilot.db import get_db, init_db

# Inicializa DB (uma vez no startup)
init_db(run_migrations=True)

# Services
path_service = PathService()
backup_service = BackupService()

# Repositories (acesso direto se necessário)
path_repo = PathEntryRepository()
env_repo = EnvVarRepository()
```

## PathService

### Métodos Principais

```python
# Listagem
list_paths(scope: Scope, active_only: bool = True) -> list[PathEntry]

# CRUD
add_path(path: str, scope: Scope, description: str = "", position: int = None) -> OperationResult
remove_path(path: str, scope: Scope) -> OperationResult

# Bulk
add_paths_bulk(paths: list[str], scope: Scope) -> BulkOperationResult
remove_paths_bulk(paths: list[str], scope: Scope) -> BulkOperationResult

# Reorder
move_path_up(path: str, scope: Scope) -> OperationResult
move_path_down(path: str, scope: Scope) -> OperationResult
move_path_to_position(path: str, scope: Scope, position: int) -> OperationResult
reorder_by_priority(scope: Scope, priority_paths: list[str]) -> OperationResult

# Import/Export
export_to_json(scope: Scope, file_path: str) -> OperationResult
export_to_csv(scope: Scope, file_path: str) -> OperationResult
import_from_json(file_path: str, scope: Scope) -> ImportResult

# Sync & Validate
sync_with_conflicts(scope: Scope, strategy: str = "merge") -> SyncResult
detect_conflicts(scope: Scope) -> list[SyncConflict]
validate_paths_detailed(scope: Scope) -> ValidationResult
expand_variables_in_db(scope: Scope) -> OperationResult

# Backup
create_backup(name: str, scope: Scope, description: str = "") -> Backup
restore_backup_merge(backup_id: int, scope: Scope, dry_run: bool = False) -> RestoreResult
restore_backup_full(backup_id: int, scope: Scope, dry_run: bool = False) -> RestoreResult
verify_backup(backup_id: int) -> bool
cleanup_backups(scope: Scope, max_backups: int, max_age_days: int) -> int
set_backup_schedule(enabled: bool, interval_hours: int, scope: Scope, max_backups: int) -> None
get_backup_schedule_status() -> dict
```

## BackupService

```python
# Herda métodos de backup do PathService
# Adiciona:
# - schedule daemon (thread background)
# - auto-backup hooks
```

## CryptoService

```python
from pathpilot.crypto import CryptoService

crypto = CryptoService()

# Fernet
encrypt(plaintext: str) -> str
decrypt(ciphertext: str) -> str

# Hash
hash_data(data: str) -> str  # SHA-256 hex

# HMAC
hmac_sign(data: str) -> str
hmac_verify(data: str, signature: str) -> bool

# Utilitários
generate_key() -> str  # Fernet key base64
```

## Models

```python
from pathpilot.models import (
    Scope, PathEntry, EnvVar, Backup, OperationLog,
    OperationType, OperationStatus,
    ValidationResult, SyncResult, SyncConflict,
    OperationResult, BulkOperationResult, ImportResult, RestoreResult
)

# Enums
Scope.USER / Scope.SYSTEM
OperationType.ADD / REMOVE / REORDER / BACKUP / RESTORE / SYNC / VALIDATE / ENCRYPT / DECRYPT
OperationStatus.SUCCESS / FAILED / PARTIAL

# Dataclasses
PathEntry(path, scope, active, position, description, created_at, updated_at)
EnvVar(name, value, scope, encrypted, description, created_at, updated_at)
Backup(name, scope, path_snapshot, description, checksum, created_at)
OperationLog(operation, scope, target_path, status, error_message, metadata, hmac_signature, created_at)

# Result Types
ValidationResult(valid, missing, invalid, duplicates)
SyncResult(added, removed, unchanged, drift_detected)
SyncConflict(path, in_windows, in_db, db_active, resolution)
```

## Repositories

```python
# PathEntryRepository
create(entry), get_by_id(id), get_by_path(path, scope), get_all(scope, active_only)
update(entry), delete(path, scope), set_active(path, scope, active), reorder(entries)

# EnvVarRepository
create(entry), get_by_name(name, scope), get_all(scope)
update_value(name, scope, value), delete(name, scope)

# BackupRepository
create(backup), get_by_id(id), list_all(scope, limit)
verify_integrity(id), delete(id)

# OperationLogRepository
log(entry), list_all(limit), list_by_operation(op_type)

# UserSettingsRepository
set(key, value, description), get(key, default), get_all(), delete(key)
```

## Database

```python
from pathpilot.db import Database, get_db, init_db, get_schema_version, migrate

# Singleton
db = get_db()  # Thread-local

# Conexão direta
db.execute(sql, params)
db.fetchone(sql, params)
db.fetchall(sql, params)
db.transaction() -> context manager

# Migrações
init_db(run_migrations=True)
get_schema_version() -> int
migrate() -> None
migration_status() -> dict

# Stats
db.get_stats() -> dict
db.health_check() -> bool
db.vacuum()
```

## Windows API

```python
from pathpilot.windows_api import WindowsPathAPI

api = WindowsPathAPI()

get_path(scope: str) -> list[str]
set_path(paths: list[str], scope: str) -> bool
add_to_path(path: str, scope: str) -> bool
remove_from_path(path: str, scope: str) -> bool
reorder_path(paths: list[str], scope: str) -> bool
broadcast_change() -> bool
```

## Utils

```python
from pathpilot.utils import (
    normalize_path, is_valid_path, path_exists, expand_path,
    sanitize_path, safe_join,
    validate_env_var_name, validate_env_var_value,
    split_path, join_path,
    confirm_action, broadcast_environment_change,
    compute_checksum
)
```

## Config

```python
from pathpilot.config import settings

settings.db_path        # Path
settings.fernet_key     # str
settings.hmac_key       # str
settings.default_scope  # "user" | "system"
settings.auto_backup    # bool
# ...
```

## Exceções

```python
# Exceções customizadas (em core.py, repositories.py)
class PathPilotError(Exception): pass
class ValidationError(PathPilotError): pass
class NotFoundError(PathPilotError): pass
class DuplicateError(PathPilotError): pass
class CryptoError(PathPilotError): pass
class DatabaseError(PathPilotError): pass
class WindowsAPIError(PathPilotError): pass
```