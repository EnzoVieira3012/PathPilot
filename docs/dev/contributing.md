# Contribuindo

## Setup Desenvolvimento

```bash
git clone https://github.com/EnzoVieira3012/PathPilot
cd PathPilot

python -m venv .venv
.venv\Scripts\activate  # Windows

pip install -e ".[dev]"

# Pre-commit hooks
pre-commit install
```

## Workflow

```bash
# 1. Cria branch
git checkout develop
git pull origin develop
git checkout -b feat/minha-feature

# 2. Desenvolve + testes
# ... código ...
pytest tests/ -v

# 3. Lint & Type Check
ruff check src/ tests/
ruff format src/ tests/
mypy src/pathpilot

# 4. Commit (conventional commits)
git add .
git commit -m "feat: adiciona nova funcionalidade X"

# 5. Push + PR
git push origin feat/minha-feature
# Abre PR no GitHub para develop
```

## Padrões de Código

### Python

- **Type hints** obrigatórios em funções públicas
- **Docstrings** Google style para funções públicas
- **Line length** 100 chars (ruff)
- **Imports** organizados: stdlib → third-party → local
- **Naming**: `snake_case` funções/vars, `PascalCase` classes, `UPPER_CASE` constants

### Commits (Conventional Commits)

```
feat: nova funcionalidade
fix: correção de bug
docs: documentação
style: formatação (ruff)
refactor: refatoração sem mudança comportamento
test: testes
chore: manutenção (deps, config)
perf: performance
ci: CI/CD
```

Exemplos:
```
feat: adiciona comando env-rotate para rotação de chaves
fix: corrige validação de path UNC no Windows
docs: atualiza README com exemplos de backup
test: adiciona testes para CryptoService
```

### Branches

| Prefixo | Uso |
|---------|-----|
| `feat/` | Nova feature |
| `fix/` | Bug fix |
| `docs/` | Documentação |
| `refactor/` | Refatoração |
| `test/` | Testes |
| `chore/` | Manutenção |
| `release/` | Preparação release |

## Testes

```bash
# Todos
pytest tests/ -v

# Unitários (sem CLI)
pytest tests/test_models.py tests/test_utils.py tests/test_crypto.py tests/test_db.py tests/test_repositories.py tests/test_core.py tests/test_migrations.py tests/test_windows_api.py tests/test_config.py -v

# CLI
pytest tests/test_cli.py -v

# Com coverage
pytest tests/ --cov=pathpilot --cov-report=term-missing --cov-report=html

# Marcar
pytest tests/ -m "unit" -v
pytest tests/ -m "integration" -v
pytest tests/ -m "cli" -v
```

### Fixtures

```python
# conftest.py fornece:
mock_db        # DB SQLite temporário com migrações
temp_db_path   # Path para arquivo .db temporário
sample_paths   # Lista paths exemplo
sample_env_vars # Lista env vars exemplo

def test_exemplo(mock_db):
    from pathpilot.core import PathService
    service = PathService()
    # ...
```

## Linting

```bash
# Check
ruff check src/ tests/

# Auto-fix
ruff check --fix src/ tests/

# Format
ruff format src/ tests/

# Format check
ruff format --check src/ tests/
```

### Config (ruff)

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "W", "UP", "B", "C4", "DTZ", "T10", "T20", "PTH", "PD", "PGH", "PL", "TRY", "SIM", "NPY", "RSE", "RET", "ERA", "ARG", "TID", "PIE", "TCH", "INP", "ISC", "ICN", "PT", "FLY", "QF"]
ignore = ["E501", "SIM102", "SIM103", "T201", "T203", "PD011", "ARG001", "ARG002", "TRY003", "PTH118", "PTH123"]
```

## Type Checking

```bash
mypy src/pathpilot
```

### Config (mypy)

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
plugins = ["pydantic.mypy"]
```

## Documentação

```bash
# Serve local
mkdocs serve

# Build
mkdocs build

# Deploy (GitHub Pages)
mkdocs gh-deploy
```

### Estrutura

```
docs/
├── index.md
├── install.md
├── config.md
├── usage/
│   ├── overview.md
│   ├── path.md
│   ├── backup.md
│   ├── env.md
│   ├── database.md
│   └── interactive.md
├── api/
│   ├── overview.md
│   ├── cli.md
│   ├── core.md
│   └── ...
├── dev/
│   ├── contributing.md
│   ├── testing.md
│   ├── linting.md
│   └── release.md
├── architecture.md
├── security.md
└── CHANGELOG.md
```

## Pull Request Checklist

- [ ] Testes passam (`pytest tests/`)
- [ ] Lint limpo (`ruff check src/ tests/`)
- [ ] Type check limpo (`mypy src/pathpilot`)
- [ ] Documentação atualizada (se aplicável)
- [ ] CHANGELOG.md atualizado
- [ ] Commits conventional
- [ ] Branch atualizada com develop (`git rebase develop`)
- [ ] PR description clara

## Release Process

```bash
# 1. Atualiza versão
# pyproject.toml: version = "0.7.0"

# 2. Atualiza CHANGELOG.md

# 3. Commit
git commit -am "chore: release v0.7.0"

# 4. Tag
git tag v0.7.0

# 5. Push
git push origin develop --tags

# 6. GitHub Actions faz build + publish PyPI
# 7. Cria GitHub Release com artifacts
```

## Code of Conduct

- Seja respeitoso e inclusivo
- Foque no código, não na pessoa
- Aceite críticas construtivas
- Ajude novatos