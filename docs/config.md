# Configuração

## Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto ou configure as variáveis no sistema:

```bash
# .env
PATHPILOT_DB_PATH=C:\Users\SeuUsuario\.pathpilot\pathpilot.db
PATHPILOT_FERNET_KEY=MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw=
PATHPILOT_HMAC_KEY=sua-chave-hmac-de-32-caracteres-minimo
PATHPILOT_DEFAULT_SCOPE=user
PATHPILOT_AUTO_BACKUP=false
PATHPILOT_CONFIRM_DESTRUCTIVE=true
PATHPILOT_THEME=default
PATHPILOT_SHOW_PROGRESS=true
PATHPILOT_USE_EMOJI=true
```

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `PATHPILOT_DB_PATH` | `%USERPROFILE%\.pathpilot\pathpilot.db` | Caminho do banco SQLite |
| `PATHPILOT_FERNET_KEY` | *(obrigatório)* | Chave base64 32 bytes para Fernet |
| `PATHPILOT_HMAC_KEY` | *(obrigatório)* | Chave HMAC para assinatura logs |
| `PATHPILOT_DEFAULT_SCOPE` | `user` | `user` ou `system` |
| `PATHPILOT_AUTO_BACKUP` | `false` | Backup automático antes de mudanças |
| `PATHPILOT_CONFIRM_DESTRUCTIVE` | `true` | Confirma operações destrutivas |
| `PATHPILOT_THEME` | `default` | `default`, `dark`, `light` |
| `PATHPILOT_SHOW_PROGRESS` | `true` | Barras de progresso |
| `PATHPILOT_USE_EMOJI` | `true` | Emojis na saída |

## Gerar Chaves

```bash
# Gera chave Fernet válida
pathpilot crypto-keygen

# Exemplo output: MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw=
# Copie para PATHPILOT_FERNET_KEY no .env

# HMAC key - qualquer string 32+ chars
# PATHPILOT_HMAC_KEY=minha-chave-hmac-super-secreta-32chars
```

## Estrutura de Diretórios

```
%USERPROFILE%\
├── .pathpilot\
│   ├── pathpilot.db          # Banco SQLite principal
│   ├── pathpilot.db-wal      # WAL mode (concorrência)
│   └── pathpilot.db-shm      # Shared memory
└── exports\                  # Pasta de exportações (gitignored)
    ├── backup-2024-01-15.json
    └── paths-export.csv
```

## Configuração Avançada

### Backup Automático

```bash
# Ativa agendamento a cada 12h, máx 30 backups
pathpilot backup-schedule --enable --interval 12 --max-backups 30

# Backup automático antes de cada mudança
pathpilot config set backup.auto.enabled true
pathpilot config set backup.auto.max_backups 10
```

### Tema e Estilo

```bash
# Tema escuro
pathpilot config set theme dark

# Sem emojis (para terminais legados)
pathpilot config set use_emoji false

# Sem barras de progresso
pathpilot config set show_progress false
```

## Verificação

```bash
# Mostra configuração atual
pathpilot config show

# Testa conexão DB
pathpilot db-stats

# Testa criptografia
pathpilot crypto-keygen
```