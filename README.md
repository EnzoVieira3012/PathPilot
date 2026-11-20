# PathPilot

🎯 **PathPilot** - Gerencie seu PATH do Windows com estilo.

CLI moderna construída com **Typer + Rich + Questionary** para gerenciar variáveis de ambiente e PATH no Windows com banco de dados SQLite, migrações versionadas, backup/restore e interface bonita no terminal.

## ✨ Funcionalidades

### PATH Management
- `list` - Lista paths (table/tree/json) por escopo (user/system/both)
- `add` - Adiciona path com validação, descrição, modo interativo
- `remove` - Remove/desativa path com confirmação
- `validate` - Verifica existência no disco, duplicados, inválidos (`--fix` limpa automático)
- `sync` - Sincroniza DB ↔ Windows real, detecta drift

### Backup & Restore
- `backup` - Snapshot do PATH atual com checksum SHA-256
- `restore` - Restaura backup (com `--dry-run` para simular)
- `history` - Log de operações (últimas 20 por padrão)

### Database & Migrations
- `migrate` - Executa migrações pendentes (`--status` mostra estado, `--version N` target específico)
- `db-stats` - Estatísticas do banco + health check
- SQLite com WAL mode, thread-local connections
- 5 migrações versionadas + seed paths padrão Windows

### Interface
- `interactive` - Menu completo com Questionary (setas, seleção, confirmação)
- Output Rich: tables coloridas, panels, trees, progress bars
- Prompts interativos bonitos

## 🚀 Instalação

```bash
# Clone
git clone https://github.com/EnzoVieira3012/PathPilot.git
cd PathPilot

# Instala dependências
pip install -e .

# Ou modo desenvolvimento
pip install -e ".[dev]"
```

## ⚙️ Configuração

Copie `.env.example` para `.env` e ajuste:

```env
DB_PATH=C:\Users\<USER>\.pathpilot\pathpilot.db
FERNET_KEY=              # Gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DEFAULT_SCOPE=user
AUTO_BACKUP=true
CONFIRM_DESTRUCTIVE=true
```

## 📖 Uso

```bash
# Help
pathpilot --help
pathpilot <comando> --help

# PATH
pathpilot list                    # Ambos escopos, table
pathpilot list --scope user --format tree
pathpilot list --format json

pathpilot add "C:\Tools" --scope user --desc "Minhas ferramentas"
pathpilot add "C:\Program Files\Git\bin" --scope system --interactive

pathpilot remove "C:\OldPath" --scope user
pathpilot remove "C:\OldPath" --scope user --force  # Sem confirmação

pathpilot validate                # Checka ambos escopos
pathpilot validate --scope system --fix  # Remove inválidos auto

pathpilot sync                    # Sync DB ↔ Windows (detecta drift)
pathpilot sync --dry-run          # Só mostra o que faria

# Backup/Restore
pathpilot backup "antes-update" --scope user --desc "Backup antes do update"
pathpilot restore 1               # Restaura backup ID 1
pathpilot restore 1 --dry-run     # Simula
pathpilot restore 1 --scope system  # Força escopo

# Histórico
pathpilot history                 # Últimas 20
pathpilot history -n 50 --scope user

# Database
pathpilot migrate --status        # Status migrações
pathpilot migrate                 # Roda pendentes
pathpilot migrate --version 3     # Até versão 3
pathpilot db-stats                # Stats + health check

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
├── core.py          # PathService - lógica de negócio
├── models.py        # Dataclasses/Pydantic (Scope, PathEntry, Backup, etc)
├── db.py            # Database singleton, WAL, thread-local, health check
├── migrations.py    # Sistema migrações versionadas (5 migrações)
├── repositories.py  # Repository Pattern (PathEntry, EnvVar, Backup, Log, Settings)
├── windows_api.py   # winreg wrapper (user/system PATH)
├── config.py        # pydantic-settings (.env)
├── utils.py         # Helpers (normalize, admin check, console prints)
└── __main__.py      # Entry point python -m pathpilot
```

### Migrações
| Versão | Descrição |
|--------|-----------|
| 1 | Schema inicial: env_vars, path_entries, backups, operation_log |
| 2 | Coluna `checksum` em backups (SHA-256) |
| 3 | Índices compostos performance |
| 4 | Tabela `user_settings` |
| 5 | Seed: paths padrão Windows (user + system) |

### Banco de Dados
- **SQLite** em `~/.pathpilot/pathpilot.db`
- **WAL mode** para concorrência
- **Thread-local connections** (seguro para CLI)
- **Foreign keys** ativas
- **Checksum SHA-256** nos backups para integridade

## 🧪 Desenvolvimento

```bash
# Lint + format
ruff check .
ruff format .

# Type check
mypy src/

# Testes
pytest -v
pytest --cov=src/pathpilot

# Pre-commit
pre-commit install
```

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

- Validação de input (path traversal, injection)
- Confirmação interativa para operações destrutivas
- Chave Fernet em `.env` (nunca no código)
- Checksum SHA-256 verifica integridade de backups
- Scope `system` requer execução como Administrador

## 🗺️ Roadmap

- [x] `feat/core-cli` - CLI base + comandos essenciais
- [x] `feat/database` - SQLite + migrations + seeds + repositories
- [ ] `feat/path-operations` - Reorder, bulk ops, import/export
- [ ] `feat/backup-restore` - Auto-backup hooks, merge restore, agendamento
- [ ] `feat/security` - Fernet encrypt env vars, audit log assinado
- [ ] `feat/tests` - Unit + integration tests (>80% coverage)
- [ ] `feat/polish` - CI/CD, packaging, docs completas

## 📄 Licença

MIT - veja [LICENSE](LICENSE)

---

**Feito com 💻 no Windows**