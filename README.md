# PathPilot

Sistema Python para gerenciar variáveis de ambiente e paths no Windows de forma prática e padronizada.

## Sobre

PathPilot é uma ferramenta CLI que permite registrar, listar e gerenciar variáveis de ambiente (especialmente o PATH) no Windows de forma organizada, seguindo boas práticas de mercado.

## Funcionalidades

- ✅ Adicionar paths ao PATH do sistema/usuário
- ✅ Remover paths do PATH
- ✅ Listar paths atuais
- ✅ Backup e restore do PATH
- ✅ Validação de paths duplicados
- ✅ Interface de linha de comando intuitiva

## Instalação

```bash
# Clone o repositório
git clone <url-do-repo>
cd PathPilot

# Crie ambiente virtual
python -m venv venv
venv\Scripts\activate

# Instale dependências
pip install -r requirements.txt
```

## Configuração

1. Copie `.env.example` para `.env`
2. Ajuste as variáveis conforme necessário

## Uso

```bash
# Ver ajuda
python -m pathpilot --help

# Listar paths atuais
python -m pathpilot list

# Adicionar path
python -m pathpilot add "C:\Meu\Path"

# Remover path
python -m pathpilot remove "C:\Meu\Path"

# Backup do PATH atual
python -m pathpilot backup

# Restaurar backup
python -m pathpilot restore
```

## Estrutura do Projeto

```
PathPilot/
├── src/
│   └── pathpilot/
│       ├── __init__.py
│       ├── cli.py
│       ├── core.py
│       └── utils.py
├── tests/
├── .gitignore
├── .env
├── .env.example
├── README.md
├── requirements.txt
└── pyproject.toml
```

## Desenvolvimento

```bash
# Rodar testes
pytest

# Linting
ruff check .

# Formatação
ruff format .
```

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.