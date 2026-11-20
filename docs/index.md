# PathPilot

**Gerencie seu PATH do Windows com estilo** — CLI moderna, bonita e responsiva construída com **Typer + Rich + Questionary**.

## ✨ Características

- **Interface Rica** — Tabelas coloridas, painéis, árvores, barras de progresso
- **Prompts Interativos** — Seleção fuzzy, confirmações, inputs validados
- **PATH Inteligente** — Listar, adicionar, remover, reordenar, priorizar, validar
- **Bulk Operations** — Adicionar/remover múltiplos paths de uma vez
- **Import/Export** — JSON e CSV com metadados
- **Backup & Restore** — Snapshots com checksum SHA-256, merge, restore full, agendamento
- **Variáveis Criptografadas** — Fernet (AES-128-CBC + HMAC) para secrets
- **Auditoria Completa** — Log de operações com assinatura HMAC-SHA256
- **Database SQLite** — WAL mode, migrations versionadas, repositórios tipados
- **Windows Native** — Registry API via `winreg`, broadcast de mudanças

## 🚀 Instalação Rápida

```bash
# Via pipx (recomendado)
pipx install pathpilot

# Via pip
pip install pathpilot

# Desenvolvimento
git clone https://github.com/EnzoVieira3012/PathPilot
cd PathPilot
pip install -e ".[dev]"
```

## 📋 Comandos Principais

| Comando | Descrição |
|---------|-----------|
| `pathpilot list` | Lista paths do usuário/sistema |
| `pathpilot add` | Adiciona path |
| `pathpilot remove` | Remove path |
| `pathpilot reorder` | Move path up/down |
| `pathpilot prioritize` | Prioriza múltiplos paths |
| `pathpilot add-bulk` | Adiciona múltiplos paths |
| `pathpilot export` | Exporta para JSON/CSV |
| `pathpilot import-cmd` | Importa de JSON/CSV |
| `pathpilot sync` | Sincroniza com Windows |
| `pathpilot validate` | Valida paths |
| `pathpilot backup` | Cria backup |
| `pathpilot restore` | Restaura backup |
| `pathpilot env-add` | Adiciona variável (opcional criptografada) |
| `pathpilot interactive` | Modo interativo TUI |

## 🔐 Segurança

- **Fernet** (AES-128-CBC + HMAC) para criptografia de variáveis sensíveis
- **HMAC-SHA256** para integridade do log de operações
- **Sanitização** de paths (prevenção traversal, null bytes)
- **Scope isolation** — usuário vs sistema

## 📖 Documentação

- [Instalação](install.md)
- [Configuração](config.md)
- [Guia de Uso](usage/overview.md)
- [Referência da API](api/overview.md)
- [Arquitetura](architecture.md)
- [Segurança](security.md)

## 👨‍💻 Autor

**Enzo Vieira**
- GitHub: [@EnzoVieira3012](https://github.com/EnzoVieira3012)
- LinkedIn: [enzovieira3012](https://www.linkedin.com/in/enzovieira3012/)

## 📄 Licença

MIT License — veja [LICENSE](license.md) para detalhes.