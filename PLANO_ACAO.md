# Plano de Ação - PathPilot

## Visão Geral
CLI Python para gerenciar PATH/variáveis de ambiente no Windows com persistência em banco de dados SQLite.

---

## Estratégia de Branches

| Branch | Foco | Base |
|--------|------|------|
| `develop` | Integração contínua | `main` |
| `feat/core-cli` | CLI base + comandos essenciais | `develop` |
| `feat/database` | Modelo de dados + SQLite + repositories | `develop` |
| `feat/path-operations` | Add/remove/list/validate PATH | `feat/database` |
| `feat/backup-restore` | Backup/restore + histórico | `feat/path-operations` |
| `feat/security` | Criptografia sensível (Fernet) + validações | `feat/backup-restore` |
| `feat/tests` | Testes unitários + integração | `feat/security` |
| `feat/polish` | Linting, docs, packaging, CI | `feat/tests` |

**Regra**: Cada branch = 1 funcionalidade isolada. PR obrigatório para `develop` com review.

---

## Fases de Desenvolvimento

### FASE 0: Setup Inicial (Branch: `feat/core-cli`)

#### 0.1 Estrutura do Projeto
- [ ] Verificar/criar `src/pathpilot/__init__.py`
- [ ] Criar `src/pathpilot/cli.py` (Typer/Click)
- [ ] Criar `src/pathpilot/core.py` (lógica de negócio)
- [ ] Criar `src/pathpilot/utils.py` (helpers)
- [ ] Criar `src/pathpilot/models.py` (dataclasses/Pydantic)
- [ ] Criar `src/pathpilot/db.py` (conexão SQLite)
- [ ] Criar `src/pathpilot/repositories.py` (data access)
- [ ] Atualizar `pyproject.toml` com dependências

#### 0.2 CLI Base (Padrão: Menu Interativo + Estado - Skill Python Aula 6)
```python
# cli.py - Typer app com comandos:
# pathpilot list
# pathpilot add <path> [--system|--user]
# pathpilot remove <path> [--system|--user]
# pathpilot backup
# pathpilot restore [--backup-id]
# pathpilot history
# pathpilot validate
```

#### 0.3 Configuração
- [ ] `.env.example` com: `DB_PATH`, `FERNET_KEY`, `DEFAULT_SCOPE`
- [ ] `config.py` com `pydantic-settings`
- [ ] Logging configurado (`logging.config.dictConfig`)

#### 0.4 Validações Iniciais (Skill Python: Validação Defensiva em Cascata)
- [ ] Verificar admin rights para escopo system
- [ ] Validar path existe (os.path.exists)
- [ ] Normalizar path (os.path.normpath, expandvars)

---

### FASE 1: Banco de Dados (Branch: `feat/database`)

#### 1.1 Modelagem (Skill SQL: Análise de Requisitos → Modelo)
**Entidades identificadas:**
- `environment_variables` - Variáveis salvas pelo usuário
- `path_entries` - Entradas do PATH gerenciadas
- `backups` - Snapshots do PATH para restore
- `operation_log` - Auditoria de operações

#### 1.2 Schema SQLite (DDL - Skill SQL Aula 3)
```sql
-- environment_variables
CREATE TABLE env_vars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('user', 'system')),
    description TEXT,
    encrypted BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- path_entries (entidades do PATH gerenciadas)
CREATE TABLE path_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('user', 'system')),
    active BOOLEAN DEFAULT 1,
    position INTEGER,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(path, scope)
);

-- backups (snapshots completos do PATH)
CREATE TABLE backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('user', 'system')),
    path_snapshot TEXT NOT NULL,  -- JSON array of paths
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- operation_log (auditoria)
CREATE TABLE operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation VARCHAR(50) NOT NULL,  -- ADD, REMOVE, BACKUP, RESTORE, VALIDATE
    scope VARCHAR(10),
    target_path TEXT,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'partial')),
    error_message TEXT,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX idx_path_entries_scope_active ON path_entries(scope, active);
CREATE INDEX idx_backups_scope_created ON backups(scope, created_at DESC);
CREATE INDEX idx_op_log_created ON operation_log(created_at DESC);
```

#### 1.3 Repository Pattern (Skill Python: Funções Puras + Separação)
```python
# repositories.py
class EnvVarRepository:
    def get_all(self, scope: str = None) -> List[EnvVar]
    def get_by_name(self, name: str, scope: str) -> EnvVar | None
    def create(self, env_var: EnvVar) -> EnvVar
    def update(self, env_var: EnvVar) -> EnvVar
    def delete(self, name: str, scope: str) -> bool

class PathEntryRepository:
    def get_all(self, scope: str, active_only: bool = True) -> List[PathEntry]
    def get_by_path(self, path: str, scope: str) -> PathEntry | None
    def create(self, entry: PathEntry) -> PathEntry
    def update(self, entry: PathEntry) -> PathEntry
    def delete(self, path: str, scope: str) -> bool
    def reorder(self, entries: List[PathEntry]) -> None

class BackupRepository:
    def create(self, backup: Backup) -> Backup
    def get_latest(self, scope: str) -> Backup | None
    def get_by_id(self, backup_id: int) -> Backup | None
    def list_all(self, scope: str = None, limit: int = 50) -> List[Backup]

class OperationLogRepository:
    def log(self, log: OperationLog) -> OperationLog
    def get_recent(self, limit: int = 100) -> List[OperationLog]
```

#### 1.4 Database Manager
- [ ] `db.py`: conexão singleton, migrações, transações
- [ ] Context manager para transações (`with db.transaction():`)
- [ ] `init_db()` - cria tabelas se não existem
- [ ] `migrate()` - migrações versionadas (simples: versão em tabela `schema_version`)

---

### FASE 2: Operações de PATH (Branch: `feat/path-operations`)

#### 2.1 Core Service (Skill Python: Validação Defensiva + Funções Puras)
```python
# core.py
class PathService:
    def __init__(self, repo: PathEntryRepository, win_api: WindowsPathAPI, logger)
    
    def list_paths(self, scope: str) -> List[PathEntry]
    def add_path(self, path: str, scope: str, description: str = "") -> PathEntry
    def remove_path(self, path: str, scope: str) -> bool
    def validate_paths(self, scope: str) -> ValidationResult
    def reorder_paths(self, entries: List[PathEntry]) -> None
    def sync_from_system(self, scope: str) -> SyncResult
```

#### 2.2 Windows API Wrapper (Skill Python: Módulos `os`, `winreg`)
```python
# windows_api.py
class WindowsPathAPI:
    def get_system_path(self) -> List[str]
    def get_user_path(self) -> List[str]
    def set_system_path(self, paths: List[str]) -> None  # requer admin
    def set_user_path(self, paths: List[str]) -> None
    def broadcast_environment_change(self) -> None
```

#### 2.3 Validações (Skill Python: Checklist - Casos de Fronteira)
- [ ] Path existe no filesystem?
- [ ] Path já está no PATH (duplicado)?
- [ ] Path é válido (não vazio, caracteres válidos)?
- [ ] Permissão admin para system scope?
- [ ] Variáveis de ambiente expandidas (%VAR%)?

#### 2.4 Sincronização
- [ ] `sync_from_system()` - lê PATH real do Windows e atualiza DB
- [ ] Detectar drift (DB ≠ Windows real)
- [ ] Relatório de diferenças

---

### FASE 3: Backup & Restore (Branch: `feat/backup-restore`)

#### 3.1 Backup Service (Skill SQL: Transações + Procedures)
```python
# backup_service.py
class BackupService:
    def create_backup(self, scope: str, name: str, description: str) -> Backup
    def restore_backup(self, backup_id: int, scope: str) -> RestoreResult
    def list_backups(self, scope: str = None) -> List[Backup]
    def delete_backup(self, backup_id: int) -> bool
    def auto_backup_before_change(self, scope: str) -> Backup  # hook
```

#### 3.2 Restore Strategy
- [ ] Full restore (substitui PATH atual)
- [ ] Merge restore (adiciona paths faltantes)
- [ ] Dry-run (simula sem aplicar)
- [ ] Rollback automático se falhar

#### 3.3 Histórico e Auditoria
- [ ] `operation_log` preenchido em cada operação
- [ ] CLI `pathpilot history` mostra últimos 50 ops
- [ ] Filtro por escopo, status, data

---

### FASE 4: Segurança (Branch: `feat/security`)

#### 4.1 Criptografia (Skill Python: Fernet AES-128-CBC + HMAC)
```python
# crypto.py
class CryptoService:
    def __init__(self, key: bytes)  # de env FERNET_KEY
    def encrypt(self, plaintext: str) -> str  # retorna base64
    def decrypt(self, ciphertext: str) -> str
    def hash_value(self, value: str) -> str  # SHA-256 para integridade
```

#### 4.2 Aplicação
- [ ] Criptografar `value` em `env_vars` quando `encrypted=True`
- [ ] Chave Fernet em `.env` (nunca no código - Skill Python: Nunca hardcode)
- [ ] Hash SHA-256 de backups para verificação de integridade

#### 4.3 Validações Extras
- [ ] Sanitização de input (path traversal, injection)
- [ ] Rate limiting em CLI (opcional)
- [ ] Confirmação interativa para operações destrutivas

---

### FASE 5: Testes (Branch: `feat/tests`)

#### 5.1 Unitários (Skill Python: pytest + Testes de Mesa)
```python
# tests/test_core.py
def test_add_path_duplicate_raises()
def test_remove_nonexistent_returns_false()
def test_validate_detects_broken_paths()
def test_reorder_preserves_all_entries()
```

#### 5.2 Integração
```python
# tests/test_integration.py
def test_full_add_remove_cycle(tmp_path)
def test_backup_restore_roundtrip(tmp_path)
def test_sync_from_system_detects_drift()
```

#### 5.3 Fixtures
- [ ] `tmp_db` - SQLite em memória/arquivo temp
- [ ] `mock_windows_api` - mock do registro do Windows
- [ ] `sample_paths` - dados de teste realistas

#### 5.4 Cobertura
- [ ] `pytest --cov=src/pathpilot --cov-report=term-missing`
- [ ] Meta: >80% cobertura em core/repositories

---

### FASE 6: Polimento (Branch: `feat/polish`)

#### 6.1 Qualidade de Código
- [ ] `ruff check .` - zero warnings
- [ ] `ruff format .` - formatação consistente
- [ ] `mypy src/` - tipagem estrita

#### 6.2 Documentação
- [ ] README atualizado com exemplos reais
- [ ] `--help` completo em todos comandos
- [ ] Docstrings em funções públicas (Google style)
- [ ] CHANGELOG.md

#### 6.3 Packaging
- [ ] `pyproject.toml` completo (build-system, entry-points, optional deps)
- [ ] `pip install -e .` funciona
- [ ] Executável `pathpilot` instalado no PATH do venv

#### 6.4 CI/CD (GitHub Actions)
```yaml
# .github/workflows/ci.yml
- lint (ruff, mypy)
- test (pytest + coverage)
- build (pip wheel)
- publish to TestPyPI on tag
```

---

## Checklist por Branch (Definição de Pronto)

| Branch | Critérios de Aceite |
|--------|---------------------|
| `feat/core-cli` | `pathpilot --help` funciona, comandos skeleton registrados, config carrega `.env` |
| `feat/database` | `init_db()` cria tabelas, CRUD repos testados, migrações versionadas |
| `feat/path-operations` | Add/remove/list/validate funcionam contra Windows real, sync detecta drift |
| `feat/backup-restore` | Backup cria snapshot, restore recupera, history mostra log |
| `feat/security` | Valores sensíveis criptografados, chave em env, hash verifica integridade |
| `feat/tests` | >80% coverage, CI verde, testes isolados (mock Windows API) |
| `feat/polish` | Ruff/mypy limpos, package instalável, docs completas, CI pipeline |

---

## Ordem de Execução Recomendada

```
1. feat/core-cli      (base)
2. feat/database      (foundation)
3. feat/path-operations  (core feature)
4. feat/backup-restore   (depends on path-operations)
5. feat/security      (cross-cutting)
6. feat/tests         (valida tudo)
7. feat/polish        (entrega)
```

Cada branch → PR → review → merge para `develop` → próxima branch.

---

## Estimativa de Esforço (Referência)

| Fase | Complexidade | Dias Estimados |
|------|--------------|----------------|
| Setup + CLI | Baixa | 1-2 |
| Database | Média | 2-3 |
| PATH Operations | Alta | 3-4 |
| Backup/Restore | Média | 2 |
| Security | Média | 1-2 |
| Tests | Média | 2 |
| Polish | Baixa | 1 |
| **Total** | | **12-16 dias** |

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Permissão admin no Windows | Alta | Alto | Detectar cedo, fallback user-scope, docs claras |
| Drift DB vs Windows real | Média | Alto | Sync automático antes de operações, validação |
| Paths com espaços/caracteres especiais | Média | Médio | Normalização rigorosa, testes com casos reais |
| Quebra de PATH do sistema | Baixa | Crítico | Backup obrigatório antes de qualquer write, dry-run |
| Chave Fernet perdida | Baixa | Alto | Documentar backup de chave, gerar na primeira execução |

---

## Próximos Passos Imediatos

1. **Criar branch `feat/core-cli`** e implementar skeleton
2. **Definir `pyproject.toml`** com dependências: `typer`, `pydantic`, `pydantic-settings`, `cryptography`, `pytest`, `ruff`
3. **Criar estrutura `src/pathpilot/`** com arquivos vazios
4. **Implementar `cli.py`** com Typer e comandos placeholder
5. **Testar:** `python -m pathpilot --help` funciona

---

*Plano baseado nas skills: Python (Pensar Cursos) - validação defensiva, funções puras, Fernet, checklist; SQL (Pensar Cursos) - modelagem, DDL, repositories, transações, backup; Lógica - pseudocódigo, trace tables, padrões de algoritmo.*