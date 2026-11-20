# Build & Release

## Versionamento

**SemVer**: `MAJOR.MINOR.PATCH`

| Tipo | Quando | Exemplo |
|------|--------|---------|
| MAJOR | Breaking changes API/CLI | `1.0.0` → `2.0.0` |
| MINOR | Nova feature compatível | `0.6.0` → `0.7.0` |
| PATCH | Bug fix | `0.6.0` → `0.6.1` |

Pré-releases: `0.7.0-alpha.1`, `0.7.0-beta.2`, `0.7.0-rc.1`

## Release Process

### 1. Preparação

```bash
# Atualiza develop
git checkout develop
git pull origin develop

# Cria release branch
git checkout -b release/v0.7.0

# Atualiza versão
# pyproject.toml: version = "0.7.0"
# src/pathpilot/__init__.py: __version__ = "0.7.0"

# Atualiza CHANGELOG.md
# ## [0.7.0] - 2024-01-15
# ### Added
# - Nova feature X
# ### Fixed
# - Bug Y
# ### Changed
# - Mudança Z

# Commit
git add pyproject.toml src/pathpilot/__init__.py CHANGELOG.md
git commit -m "chore: release v0.7.0"
```

### 2. Testes Finais

```bash
# CI completo local
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/pathpilot
pytest tests/ -v --tb=short

# Build teste
pip install build
python -m build
twine check dist/*
```

### 3. Tag & Push

```bash
# Tag anotada
git tag -a v0.7.0 -m "Release v0.7.0"

# Push branch + tag
git push origin release/v0.7.0
git push origin v0.7.0
```

### 4. GitHub Release

GitHub Actions (`.github/workflows/ci.yml`) faz automaticamente:
1. Build wheel + sdist
2. Publish PyPI (se `PYPI_API_TOKEN` configurado)
3. Cria GitHub Release com artifacts
4. Gera release notes automáticas

### 5. Merge & Cleanup

```bash
# Merge release → main
git checkout main
git merge release/v0.7.0 --no-ff
git push origin main

# Merge release → develop
git checkout develop
git merge release/v0.7.0 --no-ff
git push origin develop

# Delete release branch
git branch -d release/v0.7.0
git push origin --delete release/v0.7.0
```

## PyPI Publishing

### Configuração

1. PyPI: Account → API tokens → Add token (scope: entire account)
2. GitHub: Settings → Secrets → `PYPI_API_TOKEN`

### Manual (se necessário)

```bash
pip install build twine
python -m build
twine upload dist/*
# Username: __token__
# Password: pypi-<token>
```

## GitHub Actions Workflow

### CI (`.github/workflows/ci.yml`)

```yaml
jobs:
  lint-and-typecheck:  # ruff + mypy
  test:                # pytest + coverage
  build:               # python -m build + twine check
  windows-build:       # testes Windows
  release:             # publish PyPI + GitHub Release (on tag)
```

### Triggers

- `push` to `develop`/`main` → CI completo
- `pull_request` to `develop`/`main` → CI
- `release published` → Build + Publish PyPI + GitHub Release

## Changelog

### Formato (Keep a Changelog)

```markdown
# Changelog

## [0.7.0] - 2024-01-15
### Added
- Novo comando `env-rotate` para rotação de chaves
- Suporte a paths UNC (`\\server\share`)
- Tema `dark`/`light` no CLI

### Changed
- `list` agora mostra descrição por padrão
- Backup agendado usa WAL checkpoint

### Fixed
- Validação de path com espaços no `add-bulk`
- Race condition em migração concorrente
- Encoding Unicode no Windows Terminal

### Security
- Atualização `cryptography` 42.0.0 → 43.0.0
```

### Categorias

- `Added` — Novas features
- `Changed` — Mudanças em features existentes
- `Deprecated` — Features marcadas para remoção
- `Removed` — Features removidas
- `Fixed` — Bug fixes
- `Security` — Vulnerabilidades corrigidas

## Artifacts

### Wheel (`.whl`)

```bash
# Instalação
pip install pathpilot-0.7.0-py3-none-any.whl

# Inspeciona
unzip -l pathpilot-0.7.0-py3-none-any.whl
```

### Source Distribution (`.tar.gz`)

```bash
# Inspeciona
tar -tzf pathpilot-0.7.0.tar.gz
```

### Windows Installer (Futuro)

```bash
# cx_Freeze
pip install cx_Freeze
python setup.py build_exe

# PyInstaller
pip install pyinstaller
pyinstaller --onefile --name pathpilot src/pathpilot/__main__.py

# Output: dist/pathpilot.exe
```

## Verificação Pós-Release

```bash
# PyPI
pip install pathpilot==0.7.0
pathpilot --version  # 0.7.0

# GitHub Release
# Verifica: https://github.com/EnzoVieira3012/PathPilot/releases/tag/v0.7.0

# Docs
# Verifica: https://enzovieira3012.github.io/PathPilot/
```

## Rollback

Se release tem problema crítico:

```bash
# 1. Yank PyPI (remove do index, mantém arquivos)
twine upload --repository pypi --skip-existing dist/*  # não funciona para yank
# Use: https://pypi.org/manage/project/pathpilot/releases/ → Yank

# 2. Hotfix branch
git checkout -b hotfix/v0.7.1 v0.7.0
# ... fix ...
git tag v0.7.1
git push origin hotfix/v0.7.1 v0.7.1

# 3. GitHub Actions faz novo release
```

## Checklist Release

- [ ] Versão bumpada em `pyproject.toml` e `__init__.py`
- [ ] `CHANGELOG.md` atualizado
- [ ] Testes passam (Linux + Windows)
- [ ] Lint + Typecheck limpos
- [ ] Build artifacts válidos (`twine check`)
- [ ] Tag criada e pushada
- [ ] GitHub Actions release job sucesso
- [ ] PyPI package instalável
- [ ] GitHub Release criado com notes
- [ ] Docs deployadas (GitHub Pages)
- [ ] Merge release → main + develop
- [ ] Branch release deletada
- [ ] Anúncio (se aplicável)