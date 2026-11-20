# Instalação

## Pré-requisitos

- **Windows 10/11** (para gerenciamento de PATH do Windows)
- **Python 3.11+**
- Permissões de **Administrador** (para escopo `system`)

## Métodos de Instalação

### 1. pipx (Recomendado)

Isola o CLI em ambiente próprio, evita conflitos de dependências.

```bash
pipx install pathpilot
```

Verifique:
```bash
pathpilot --version
pathpilot --help
```

### 2. pip (Global/User)

```bash
# Instalação global (requer admin)
pip install pathpilot

# Instalação user (sem admin)
pip install --user pathpilot
```

### 3. Desenvolvimento

```bash
git clone https://github.com/EnzoVieira3012/PathPilot
cd PathPilot

# Ambiente virtual
python -m venv .venv
.venv\Scripts\activate  # Windows

# Instalação em modo editável com dev deps
pip install -e ".[dev]"

# Verifica
pathpilot --version
pytest tests/
```

### 4. Windows Standalone (Planejado)

```bash
# Futuro: installer .msi ou .exe via cx_Freeze/pyinstaller
# pip install pathpilot[build]
# python -m build --wheel --installer
```

## Pós-Instalação

### Configuração Inicial

```bash
# Gera chave de criptografia (primeira vez)
pathpilot crypto-keygen

# Adiciona ao .env
echo "PATHPILOT_FERNET_KEY=sua_chave_aqui" > .env
```

### Verificação

```bash
# Testa se funciona
pathpilot list --scope user
pathpilot db-stats
```

## Solução de Problemas

| Problema | Solução |
|----------|---------|
| `pathpilot` não encontrado | Verifique se `~/.local/bin` ou pipx bin está no PATH |
| Erro permissão (system) | Execute terminal como Administrador |
| Erro criptografia | Rode `pathpilot crypto-keygen` e configure `PATHPILOT_FERNET_KEY` |
| Python não no PATH | Use `pathpilot.bat` wrapper ou `python -m pathpilot` |

## Desinstalação

```bash
# pipx
pipx uninstall pathpilot

# pip
pip uninstall pathpilot
```