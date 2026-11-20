# Testes

## Estrutura

```
tests/
├── conftest.py              # Fixtures globais + singleton reset
├── test_models.py           # Dataclasses, enums
├── test_utils.py            # Helpers paths, validação
├── test_crypto.py           # CryptoService (Fernet, HMAC, SHA-256)
├── test_db.py               # Database singleton, health, schema
├── test_repositories.py     # 5 Repositories (CRUD, queries)
├── test_core.py             # PathService, BackupService
├── test_cli.py              # CLI commands (Typer runner)
├── test_migrations.py       # 5 migrações + seeds + triggers
├── test_windows_api.py      # WindowsPathAPI (registry)
└── test_config.py           # Settings model
```

## Rodando Testes

```bash
# Todos
pytest tests/ -v

# Por arquivo
pytest tests/test_core.py -v

# Por marcador
pytest tests/ -m "unit" -v
pytest tests/ -m "integration" -v
pytest tests/ -m "cli" -v

# Excluir marcadores
pytest tests/ -m "not cli" -v

# Parallel (pytest-xdist)
pytest tests/ -n auto -v

# Coverage
pytest tests/ --cov=pathpilot --cov-report=term-missing --cov-report=html
# Abre htmlcov/index.html
```

## Fixtures

### `mock_db` (Principal)

```python
def test_com_mock_db(mock_db):
    from pathpilot.core import PathService
    from pathpilot.models import Scope, PathEntry
    
    service = PathService()
    service.path_repo.create(PathEntry(path=r"C:\Teste", scope=Scope.USER))
    
    # mock_db é Database instância
    # mock_db.path = caminho do arquivo .db
```

Características:
- SQLite temporário (arquivo único por teste)
- Migrações aplicadas (v1-v5 + seeds)
- Singletons resetados antes/depois
- Isolamento total entre testes

### `temp_db_path`

```python
def test_com_temp_path(temp_db_path):
    # Path para arquivo .db temporário
    # Limpeza automática (arquivo + -wal + -shm)
```

### `sample_paths` / `sample_env_vars`

```python
def test_com_samples(sample_paths, sample_env_vars):
    # sample_paths = [r"C:\Windows\System32", r"C:\Python311", ...]
    # sample_env_vars = [{"name": "VAR1", "value": "val", ...}, ...]
```

## Marcadores

```python
# pytest.ini define:
markers = [
    "unit: Testes unitários rápidos",
    "integration: Testes integração (DB, filesystem)",
    "cli: Testes CLI (Typer runner)",
    "slow: Testes lentos (>1s)",
    "windows: Testes específicos Windows",
]
```

Uso:
```python
@pytest.mark.unit
def test_model_creation():
    ...

@pytest.mark.integration
def test_db_transaction(mock_db):
    ...

@pytest.mark.cli
def test_cli_list(mock_db):
    ...

@pytest.mark.slow
def test_large_bulk_operation(mock_db):
    ...

@pytest.mark.windows
def test_windows_registry():
    ...
```

## Padrões de Teste

### Unitário (Model/Util)

```python
def test_path_entry_creation():
    entry = PathEntry(path=r"C:\Test", scope=Scope.USER)
    assert entry.path == r"C:\Test"
    assert entry.scope == Scope.USER
    assert entry.active is True
```

### Integração (Repository/Service)

```python
def test_path_repo_crud(mock_db):
    repo = PathEntryRepository()
    
    # Create
    entry = repo.create(PathEntry(path=r"C:\Test", scope=Scope.USER))
    assert entry.id is not None
    
    # Read
    fetched = repo.get_by_path(r"C:\Test", Scope.USER)
    assert fetched.id == entry.id
    
    # Update
    entry.description = "Updated"
    updated = repo.update(entry)
    assert updated.description == "Updated"
    
    # Delete
    repo.delete(entry.id)
    assert repo.get_by_id(entry.id) is None
```

### CLI (Typer Runner)

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_cli_list(mock_db):
    result = runner.invoke(app, ["list", "--scope", "user"], 
                           env={"PATHPILOT_DB_PATH": str(mock_db.path)})
    assert result.exit_code == 0
    assert "Test" in result.output
```

### Mock Windows API

```python
from unittest.mock import patch, MagicMock

def test_add_path_mocked(mock_db):
    service = PathService()
    
    with patch.object(service, 'win_api', new_callable=MagicMock) as mock_win:
        mock_win.get_path.return_value = []
        mock_win.set_path.return_value = None
        
        result = service.add_path(r"C:\New", Scope.USER)
        assert result.success is True
        mock_win.set_path.assert_called_once()
```

## Coverage Targets

| Módulo | Target |
|--------|--------|
| models | 100% |
| utils | 95% |
| crypto | 100% |
| db | 90% |
| repositories | 95% |
| core | 85% |
| cli | 70% |
| migrations | 90% |
| windows_api | 80% |
| config | 90% |

## CI/CD Tests

GitHub Actions roda:
- Ubuntu: lint + typecheck + tests + coverage
- Windows: tests (sem CLI) + entry point test

```yaml
# .github/workflows/ci.yml
test:
  runs-on: ubuntu-latest
  steps:
    - pytest tests/ -v --tb=short
    
windows-build:
  runs-on: windows-latest
  steps:
    - pytest tests/ -v -k "not cli"
```

## Debugging Tests

```bash
# Verbose + traceback completo
pytest tests/test_core.py::TestPathService::test_add_path_success -v --tb=long

# Para no primeiro erro
pytest tests/ -x

# Drop to debugger on failure
pytest tests/ --pdb

# Log output
pytest tests/ -v --log-cli-level=DEBUG

# Profile
pytest tests/ --profile
```

## Test Data Isolation

Cada teste:
1. Recebe `mock_db` fresco (arquivo .db único)
2. Singletons resetados (`conftest.py` autouse)
3. Limpeza automática no teardown

```python
# conftest.py - reset_singletons fixture autouse
@pytest.fixture(autouse=True)
def reset_singletons():
    import pathpilot.db as db_module
    import pathpilot.repositories as repo_module
    # ... reset all _instance = None
    yield
    # ... cleanup
```

## Adding New Tests

1. Crie `tests/test_novo_modulo.py`
2. Use fixtures existentes (`mock_db`, `tmp_path`)
3. Siga naming: `test_<funcionalidade>_<cenario>`
4. Adicione marcador apropriado
5. Rode: `pytest tests/test_novo_modulo.py -v`