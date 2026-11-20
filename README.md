# PathPilot

🎯 **PathPilot** - Gerencie seu PATH do Windows com estilo.

CLI moderna construída com **Typer + Rich + Questionary** para gerenciar variáveis de ambiente e PATH no Windows com banco de dados SQLite, migrações versionadas, backup/restore, criptografia e interface bonita no terminal.

## ✨ Funcionalidades

### PATH Management
- `list` - Lista paths (table/tree/json) por escopo (user/system/both)
- `add` - Adiciona path com validação, descrição, posição
- `remove` - Remove/desativa path com confirmação
- `reorder` / `move-to` - Move paths up/down ou posição absoluta
- `prioritize` - Define ordem de prioridade para múltiplos paths
- `add-bulk` / `remove-bulk` - Operações em lote
- `validate` / `validate-detailed` - Verifica existência, duplicados, inválidos
- `expand-vars` - Expande %VAR% no database
- `sync` / `sync-conflicts` - Sincroniza DB ↔ Windows, resolve drift

### Import/Export
- `export` - Exporta para JSON ou CSV com metadados
- `import-cmd` - Importa de JSON

### Backup & Restore
- `backup` - Snapshot do PATH atual com checksum SHA-256
- `backups` - Lista backups disponíveis
- `backup-verify` - Verifica integridade do backup
- `restore` - Merge (adiciona faltando) ou Full (substitui tudo) com `--dry-run`
- `backup-schedule` - Agendamento automático (intervalo, max backups)
- `backup-cleanup` - Limpeza por quantidade e idade

### Variáveis de Ambiente (Security)
- `env-add` - Adiciona variável (opcional `--encrypt` com Fernet)
- `env-get` - Obtém valor (`--show` descriptografa)
- `env-list` - Lista variáveis (`--encrypted-only`)
- `env-encrypt` / `env-decrypt` - Criptografa/descriptografa existentes
- `crypto-keygen` - Gera chave Fernet base64
- HMAC-SHA256 em logs de operação para integridade

### Database & Auditoria
- `migrate` - Migrações versionadas (5 migrações + seeds + triggers)
- `db-stats` - Estatísticas + health check
- `history` - Log de operações auditado
- `log-verify` - Verifica integridade HMAC dos logs
- SQLite WAL mode, thread-local connections, foreign keys

### Interface
- `interactive` - Menu TUI completo (setas, seleção, confirmação)
- Output Rich: tables coloridas, panels, trees, progress bars
- Prompts Questionary bonitos e responsivos

## 🚀 Instalação

```bash
# Via pipx (recomendado - isolado)
pipx install pathpilot

# Via pip
pip install pathpilot

# Desenvolvimento
git clone https://github.com/EnzoVieira3012/PathPilot
cd PathPilot
pip install -e ".[dev]"
```

## ⚙️ Configuração

Copie `.env.example` para `.env` e ajuste:

```env
PATHPILOT_DB_PATH=C:\Users\<USER>\.pathpilot\pathpilot.db
PATHPILOT_FERNET_KEY=              # Gere com: pathpilot crypto-keygen
PATHPILOT_HMAC_KEY=sua-chave-hmac-32-chars-minimo
PATHPILOT_DEFAULT_SCOPE=user
PATHPILOT_AUTO_BACKUP=false
PATHPILOT_CONFIRM_DESTRUCTIVE=true
PATHPILOT_THEME=default
PATHPILOT_SHOW_PROGRESS=true
PATHPILOT_USE_EMOJI=true
```

Gere chaves:
```bash
pathpilot crypto-keygen
# Output: MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw=
# Copie para PATHPILOT_FERNET_KEY no .env
```

## 📖 Uso

```bash
# Help
pathpilot --help
pathpilot <comando> --help

# PATH
pathpilot list --scope user --format table
pathpilot list --scope system --format json --active-only

pathpilot add "C:\Tools" --scope user --desc "Minhas ferramentas" --position 0
pathpilot remove "C:\OldPath" --scope user

pathpilot reorder "C:\Tools" --direction up --scope user
pathpilot move-to "C:\Tools" 0 --scope user
pathpilot prioritize --paths "C:\Python311,C:\Python311\Scripts,C:\Tools\bin" --scope user

pathpilot add-bulk --paths "C:\A,C:\B,C:\C" --scope user
pathpilot remove-bulk --paths "C:\A,C:\B" --scope user

pathpilot validate --scope user
pathpilot validate-detailed --scope user
pathpilot expand-vars --scope user
pathpilot sync --scope user --dry-run
pathpilot sync-conflicts --strategy merge --scope user

# Import/Export
pathpilot export paths.json --scope user --format json
pathpilot export paths.csv --scope user --format csv
pathpilot import-cmd paths.json --scope user

# Backup/Restore
pathpilot backup "antes-update" --scope user --desc "Backup antes do update"
pathpilot backups --scope user
pathpilot backup-verify 1 --scope user
pathpilot restore 1 --merge --scope user --dry-run
pathpilot restore 1 --merge --scope user
pathpilot restore 1 --full --scope user  # Cuidado: substitui tudo!
pathpilot backup-schedule --enable --interval 12 --max-backups 30 --scope user
pathpilot backup-cleanup --max-backups 10 --max-age-days 30 --scope user

# Variáveis de Ambiente
pathpilot env-add MINHA_VAR "valor" --scope user
pathpilot env-add API_TOKEN "ghp_xxx" --scope user --encrypt
pathpilot env-get API_TOKEN --scope user --show
pathpilot env-list --scope user --encrypted-only
pathpilot env-encrypt MINHA_VAR --scope user
pathpilot env-decrypt API_TOKEN --scope user
pathpilot crypto-keygen

# Database & Auditoria
pathpilot db-stats
pathpilot migrate --status
pathpilot migrate
pathpilot history --limit 50 --scope user
pathpilot log-verify

# Interativo
pathpilot interactive
```

## 🧪 Testes

```bash
# Roda todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ --cov=pathpilot --cov-report=term-missing

# Apenas testes unitários (sem CLI)
pytest tests/test_models.py tests/test_utils.py tests/test_crypto.py tests/test_db.py tests/test_repositories.py tests/test_core.py tests/test_migrations.py tests/test_windows_api.py tests/test_config.py -v

# Testes de CLI
pytest tests/test_cli.py -v
```

### Estrutura dos Testes

| Arquivo | Cobertura |
|---------|-----------|
| `test_models.py` | Dataclasses/enums (Scope, PathEntry, EnvVar, Backup, OperationLog, ValidationResult, etc.) |
| `test_utils.py` | `normalize_path`, `is_valid_path`, `path_exists`, `expand_path`, `sanitize_path`, `safe_join`, `validate_env_var`, `split_path`, `join_path`, `confirm_action` |
| `test_crypto.py` | `CryptoService` (Fernet encrypt/decrypt, SHA-256, HMAC sign/verify) |
| `test_db.py` | Database singleton, health_check, schema_version, stats, transactions |
| `test_repositories.py` | `PathEntryRepository`, `EnvVarRepository`, `BackupRepository`, `OperationLogRepository`, `UserSettingsRepository` |
| `test_core.py` | `PathService` & `BackupService` (list, add, remove, bulk, reorder, import/export, sync, validate, backup, restore) |
| `test_cli.py` | CLI commands via Typer runner + direct service tests |
| `test_migrations.py` | 5 versioned migrations, seed data, triggers, indexes |
| `test_windows_api.py` | `WindowsPathAPI` (registry read/write, broadcast) |
| `test_config.py` | Settings model validation |

### Fixtures

- `mock_db` - Banco SQLite temporário com migrações aplicadas (fixture principal)
- `temp_db_path` - Path temporário para arquivo .db
- `sample_paths` / `sample_env_vars` - Dados de exemplo

```python
# Exemplo de uso da fixture mock_db
def test_meu_teste(mock_db):
    from pathpilot.core import PathService
    from pathpilot.models import Scope, PathEntry
    
    service = PathService()
    service.path_repo.create(PathEntry(path=r"C:\Teste", scope=Scope.USER))
    # ...
```

## 🏗️ Arquitetura

```
src/pathpilot/
├── cli.py           # Typer + Rich + Questionary commands
├── core.py          # PathService, BackupService - lógica de negócio
├── models.py        # Dataclasses/Pydantic (Scope, PathEntry, EnvVar, Backup, etc)
├── db.py            # Database singleton, WAL, thread-local, health check
├── migrations.py    # Sistema migrações versionadas (5 migrações + seeds)
├── repositories.py  # Repository Pattern (PathEntry, EnvVar, Backup, Log, Settings)
├── crypto.py        # CryptoService - Fernet + HMAC + SHA-256
├── windows_api.py   # winreg wrapper (user/system PATH)
├── config.py        # pydantic-settings (.env)
├── utils.py         # Helpers (normalize, sanitize, validate, checksum)
└── __main__.py      # Entry point python -m pathpilot
```

### Migrações
| Versão | Nome | Descrição |
|--------|------|-----------|
| 1 | `create_core_tables` | Tabelas principais + schema_version |
| 2 | `add_indexes` | Índices compostos performance |
| 3 | `add_columns` | description, encrypted, position, checksum |
| 4 | `add_hmac_column` | hmac_signature em operation_log |
| 5 | `add_triggers_and_seeds` | Triggers updated_at + seed settings |

### Banco de Dados
- **SQLite** em `%USERPROFILE%\.pathpilot\pathpilot.db`
- **WAL mode** para concorrência (leitores não bloqueiam escritores)
- **Thread-local connections** (seguro para CLI)
- **Foreign keys** ativas
- **Checksum SHA-256** nos backups para integridade

## 🧪 Testes

```bash
# Todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ --cov=pathpilot --cov-report=term-missing

# Apenas unitários (sem CLI)
pytest tests/test_models.py tests/test_utils.py tests/test_crypto.py tests/test_db.py tests/test_repositories.py tests/test_core.py tests/test_migrations.py tests/test_windows_api.py tests/test_config.py -v

# CLI
pytest tests/test_cli.py -v
```

### Estrutura dos Testes
| Arquivo | Cobertura |
|---------|-----------|
| `test_models.py` | Dataclasses/enums (Scope, PathEntry, EnvVar, Backup, OperationLog, etc.) |
| `test_utils.py` | `normalize_path`, `is_valid_path`, `path_exists`, `expand_path`, `sanitize_path`, `safe_join`, `validate_env_var`, `split_path`, `join_path`, `confirm_action` |
| `test_crypto.py` | `CryptoService` (Fernet encrypt/decrypt, SHA-256, HMAC sign/verify) |
| `test_db.py` | Database singleton, health_check, schema_version, stats, transactions |
| `test_repositories.py` | `PathEntryRepository`, `EnvVarRepository`, `BackupRepository`, `OperationLogRepository`, `UserSettingsRepository` |
| `test_core.py` | `PathService` & `BackupService` (list, add, remove, bulk, reorder, import/export, sync, validate, backup, restore) |
| `test_cli.py` | CLI commands via Typer runner + direct service tests |
| `test_migrations.py` | 5 versioned migrations, seed data, triggers, indexes |
| `test_windows_api.py` | `WindowsPathAPI` (registry read/write, broadcast) |
| `test_config.py` | Settings model validation |

### Fixtures
- `mock_db` - Banco SQLite temporário com migrações aplicadas (fixture principal)
- `temp_db_path` - Path temporário para arquivo .db
- `sample_paths` / `sample_env_vars` - Dados de exemplo

## 📦 Dependências Principais

| Pacote | Uso |
|--------|-----|
| `typer` | CLI framework moderno |
| `rich` | Output bonito (tables, panels, trees, progress) |
| `questionary` | Prompts interativos |
| `pydantic` + `pydantic-settings` | Validação + config |
| `cryptography` | Fernet encryption (env vars sensíveis) |
| `pytest` + `ruff` + `mypy` | Dev tooling |

## 🔐 Segurança

- Validação de input (path traversal, null bytes, injection)
- Confirmação interativa para operações destrutivas
- Chave Fernet em `.env` (nunca no código)
- Criptografia Fernet (AES-128-CBC + HMAC) para variáveis sensíveis
- HMAC-SHA256 em logs de operação para integridade/auditoria
- Checksum SHA-256 verifica integridade de backups
- Scope `system` requer execução como Administrador
- Sanitização de paths (`sanitize_path`, `safe_join`)

## 📚 Documentação

- [Instalação](docs/install.md)
- [Configuração](docs/config.md)
- [Guia de Uso](docs/usage/overview.md)
- [PATH Management](docs/usage/path.md)
- [Backup & Restore](docs/usage/backup.md)
- [Variáveis de Ambiente](docs/usage/env.md)
- [Database](docs/usage/database.md)
- [Modo Interativo](docs/usage/interactive.md)
- [Referência da API](docs/api/overview.md)
- [Arquitetura](docs/architecture.md)
- [Segurança](docs/security.md)
- [Desenvolvimento](docs/dev/contributing.md)

## 🗺️ Roadmap

- [x] `feat/core-cli` - CLI base + comandos essenciais
- [x] `feat/database` - SQLite + migrations + seeds + repositories
- [x] `feat/path-operations` - Reorder, bulk ops, import/export, sync avançado
- [x] `feat/backup-restore` - Auto-backup hooks, merge/full restore, agendamento, cleanup
- [x] `feat/security` - Fernet encrypt env vars, HMAC audit log, crypto CLI
- [x] `feat/tests` - Unit + integration tests (163 testes)
- [x] `feat/polish` - CI/CD, packaging, docs MkDocs, PowerShell completion, man pages

## 👨‍💻 Autor

**Enzo Vieira**
- GitHub: [@EnzoVieira3012](https://github.com/EnzoVieira3012)
- LinkedIn: [enzovieira3012](https://www.linkedin.com/in/enzovieira3012/)
- Email: enzovieira.trabalho@outlook.com

## 📄 Licença

MIT - veja [LICENSE](LICENSE)

---

**Feito com 💻 no Windows por Enzo Vieira**