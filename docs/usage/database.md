# Database

## Visão Geral

SQLite com **WAL mode** para concorrência, **migrações versionadas**, **repositórios tipados**.

## Estrutura

### Tabelas

| Tabela | Descrição |
|--------|-----------|
| `env_vars` | Variáveis de ambiente (nome, valor, scope, encrypted, description) |
| `path_entries` | Entradas PATH (path, scope, active, position, description) |
| `backups` | Snapshots PATH (nome, scope, path_snapshot JSON, checksum, description) |
| `operation_log` | Auditoria (operação, scope, target, status, error, metadata, HMAC) |
| `user_settings` | Configurações persistentes (chave-valor) |
| `schema_version` | Controle de migrações |

### Índices

```sql
-- Performance queries comuns
idx_env_vars_name_scope      -- lookup por nome+scope
idx_path_entries_path_scope  -- lookup por path+scope
idx_backups_scope_created    -- listagem por scope+data
idx_operation_log_scope_created -- histórico por scope+data
```

### Triggers

Atualizam `updated_at` automaticamente:
- `trg_env_vars_updated_at`
- `trg_path_entries_updated_at`
- `trg_backups_updated_at`
- `trg_operation_log_updated_at`
- `trg_user_settings_updated_at`

## Migrações

### Versões

| v | Nome | Descrição |
|---|------|-----------|
| 1 | `create_core_tables` | Tabelas principais + schema_version |
| 2 | `add_indexes` | Índices de performance |
| 3 | `add_columns` | description, encrypted, position, checksum |
| 4 | `add_hmac_column` | hmac_signature em operation_log |
| 5 | `add_triggers_and_seeds` | Triggers updated_at + seed settings |

### Aplicar

```bash
# Aplica migrações pendentes
pathpilot migrate

# Status
pathpilot migrate --status
# ou
python -c "from pathpilot.migrations import migration_status; print(migration_status())"
```

### Seed Data (v5)

```sql
INSERT INTO user_settings (key, value, description) VALUES
('backup.schedule.enabled', 'false', 'Agendamento backup'),
('backup.schedule.interval_hours', '24', 'Intervalo horas'),
('backup.schedule.max_backups', '30', 'Máx backups agendados'),
('backup.auto.enabled', 'false', 'Backup auto antes mudanças'),
('backup.auto.max_backups', '10', 'Máx backups auto'),
('backup.auto.max_age_days', '30', 'Idade máx backups auto (dias)'),
('crypto.hmac_enabled', 'true', 'HMAC nos logs');
```

## Conexão

### Thread-Local + WAL

```python
# Singleton por thread
from pathpilot.db import get_db
db = get_db()  # Mesma conexão na thread

# WAL mode: leitores não bloqueiam escritores
# PRAGMA journal_mode=WAL
# PRAGMA busy_timeout=5000
```

### Health Check

```bash
pathpilot db-stats
```

```
┌─────────────────────┬───────────┐
│ Métrica             │ Valor     │
├─────────────────────┼───────────┤
│ env_vars            │ 15        │
│ path_entries        │ 42        │
│ backups             │ 8         │
│ operation_log       │ 156       │
│ user_settings       │ 7         │
│ schema_version      │ 5         │
│ db_size_bytes       │ 245760    │
│ wal_size_bytes      │ 32768     │
└─────────────────────┴───────────┘
```

## Repositórios

Padrão Repository com tipagem completa:

```python
from pathpilot.repositories import (
    PathEntryRepository, EnvVarRepository,
    BackupRepository, OperationLogRepository,
    UserSettingsRepository
)
from pathpilot.models import Scope, PathEntry, EnvVar, Backup, OperationLog

# PathEntryRepository
repo = PathEntryRepository()
repo.create(PathEntry(path=r"C:\Test", scope=Scope.USER))
repo.get_by_path(r"C:\Test", Scope.USER)
repo.get_all(Scope.USER, active_only=True)
repo.set_active(r"C:\Test", Scope.USER, False)
repo.update(entry)
repo.delete(entry.id)
repo.reorder([entry3, entry1, entry2])

# EnvVarRepository (crypto transparente)
repo = EnvVarRepository()
repo.create(EnvVar(name="SECRET", value="val", scope=Scope.USER, encrypted=True))
repo.get_by_name("SECRET", Scope.USER)  # Retorna descriptografado
repo.update_value("SECRET", Scope.USER, "new_val")  # Criptografa auto

# BackupRepository
repo = BackupRepository()
repo.create(Backup(name="bkp", scope=Scope.USER, path_snapshot=["C:\A"]))
repo.verify_integrity(backup_id)  # Check SHA-256

# OperationLogRepository (HMAC)
repo = OperationLogRepository()
repo.log(OperationLog(operation=OperationType.ADD, ...))
repo.list_all(limit=100)
repo.list_by_operation(OperationType.BACKUP)

# UserSettingsRepository
repo = UserSettingsRepository()
repo.set("chave", "valor", "desc")
repo.get("chave", default="padrao")
repo.get_all()
```

## Transações

```python
db = get_db()

# Context manager (auto commit/rollback)
with db.transaction() as conn:
    conn.execute("INSERT INTO ...")
    conn.execute("UPDATE ...")
# Commit automático se sem exceção
# Rollback automático se exceção

# Manual
db.execute("BEGIN")
try:
    db.execute("INSERT ...")
    db.execute("COMMIT")
except:
    db.execute("ROLLBACK")
    raise
```

## Backup do Banco

```bash
# Copia arquivos (requer fechar conexões)
copy %USERPROFILE%\.pathpilot\pathpilot.db backup\
copy %USERPROFILE%\.pathpilot\pathpilot.db-wal backup\
copy %USERPROFILE%\.pathpilot\pathpilot.db-shm backup\

# Ou via SQLite
sqlite3 pathpilot.db ".backup backup.db"
```

## Vacuum

```bash
# Otimiza arquivo (reorganiza, reclaim space)
python -c "from pathpilot.db import get_db; get_db().vacuum()"
```

## Troubleshooting

| Problema | Solução |
|----------|---------|
| `database is locked` | Feche outras instâncias; aumente `busy_timeout` |
| `schema_version mismatch` | Rode `pathpilot migrate` |
| `no such table` | Migrações não rodaram; delete DB e rode `migrate` |
| WAL files grandes | `checkpoint` ou `vacuum` |
| Corrupção | Restore de backup `.db` |

## Arquivo de Configuração

```python
# src/pathpilot/config.py
class Settings(BaseSettings):
    db_path: Path = Path.home() / ".pathpilot" / "pathpilot.db"
    # ...
```

Sobrescreve via `PATHPILOT_DB_PATH` no `.env`.