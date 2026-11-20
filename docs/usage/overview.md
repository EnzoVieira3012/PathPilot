# Guia de Uso

## Visão Geral

O PathPilot gerencia o PATH do Windows (usuário e sistema) através de uma CLI rica e intuitiva.

### Conceitos Chave

- **Scope**: `user` (HKCU) ou `system` (HKLM) — requer admin
- **Active/Inactive**: Paths ativos aparecem no PATH real; inativos ficam salvos no DB
- **Position**: Ordem de prioridade no PATH (0 = primeiro)
- **Backup**: Snapshot do PATH com checksum SHA-256
- **Env Vars**: Variáveis de ambiente com criptografia opcional

## Fluxo Básico

```bash
# 1. Veja o estado atual
pathpilot list --scope user

# 2. Adicione um path
pathpilot add "C:\MeusScripts" --scope user --desc "Meus scripts pessoais"

# 3. Valide
pathpilot validate --scope user

# 4. Faça backup antes de mudanças grandes
pathpilot backup "antes-mudancas" --scope user

# 5. Se algo der errado, restaure
pathpilot restore "antes-mudancas" --scope user
```

## Comandos por Categoria

### PATH Management

```bash
# Listar
pathpilot list [--scope user|system] [--active-only]

# Adicionar
pathpilot add "C:\Path" [--scope user|system] [--desc "descricao"] [--position N]

# Remover
pathpilot remove "C:\Path" [--scope user|system]

# Reordenar
pathpilot reorder "C:\Path" --direction up|down [--scope user|system]
pathpilot move-to "C:\Path" 0 [--scope user|system]  # posição absoluta

# Priorizar múltiplos
pathpilot prioritize --paths "C:\A,C:\B,C:\C" [--scope user|system]

# Bulk
pathpilot add-bulk --paths "C:\A,C:\B,C:\C" [--scope user|system]
pathpilot remove-bulk --paths "C:\A,C:\B" [--scope user|system]
```

### Validação & Sync

```bash
# Validação simples
pathpilot validate [--scope user|system]

# Validação detalhada (existentes, faltando, duplicados, inválidos)
pathpilot validate-detailed [--scope user|system]

# Expande variáveis (%VAR%) no DB
pathpilot expand-vars [--scope user|system]

# Sincroniza com Windows (detecta drift)
pathpilot sync [--scope user|system] [--dry-run]

# Conflitos avançados
pathpilot sync-conflicts [--strategy keep_db|keep_win|merge] [--scope user|system]
```

### Import/Export

```bash
# Exporta para JSON (com metadados)
pathpilot export paths.json --scope user --format json

# Exporta para CSV
pathpilot export paths.csv --scope user --format csv

# Importa de JSON
pathpilot import-cmd paths.json --scope user [--dry-run]
```

### Backup & Restore

```bash
# Backup manual
pathpilot backup "nome-backup" [--scope user|system] [--desc "descricao"]

# Lista backups
pathpilot backups [--scope user|system]

# Verifica integridade
pathpilot backup-verify 1 [--scope user|system]

# Restore merge (adiciona paths faltando)
pathpilot restore 1 --merge [--scope user|system] [--dry-run]

# Restore full (substitui tudo)
pathpilot restore 1 --full [--scope user|system] [--dry-run]

# Agendamento
pathpilot backup-schedule --enable --interval 24 --max-backups 30

# Limpeza
pathpilot backup-cleanup [--max-backups 10] [--max-age-days 30] [--scope user|system]
```

### Variáveis de Ambiente

```bash
# Adicionar (plain)
pathpilot env-add MINHA_VAR "valor" --scope user

# Adicionar criptografada
pathpilot env-add SECRETO "senha123" --scope user --encrypt

# Obter valor (descriptografa se --show)
pathpilot env-get MINHA_VAR [--show] [--scope user|system]

# Listar
pathpilot env-list [--scope user|system] [--encrypted-only]

# Criptografar existente
pathpilot env-encrypt MINHA_VAR [--scope user|system]

# Descriptografar (remove flag encrypted)
pathpilot env-decrypt MINHA_VAR [--scope user|system]

# Gerar chave
pathpilot crypto-keygen
```

### Database & Auditoria

```bash
# Stats do banco
pathpilot db-stats

# Migrações
pathpilot migrate

# Histórico de operações
pathpilot history [--limit 50] [--scope user|system]

# Verifica integridade HMAC dos logs
pathpilot log-verify
```

### Modo Interativo

```bash
# Menu TUI completo
pathpilot interactive
```

## Exemplos Práticos

### Setup Inicial Completo

```bash
# 1. Configura chaves
pathpilot crypto-keygen
# Copia para .env

# 2. Backup do estado original
pathpilot backup "estado-original" --scope user --desc "Backup antes de começar"
pathpilot backup "estado-original-system" --scope system --desc "Backup system"

# 3. Adiciona paths de desenvolvimento
pathpilot add-bulk --paths "C:\Python311,C:\Python311\Scripts,C:\Tools\bin" --scope user

# 4. Prioriza Python
pathpilot prioritize --paths "C:\Python311,C:\Python311\Scripts" --scope user

# 5. Valida tudo
pathpilot validate-detailed --scope user
```

### Migração de Máquina

```bash
# Máquina origem
pathpilot export meus-paths.json --scope user --format json
pathpilot export meus-paths-system.json --scope system --format json

# Máquina destino
pathpilot import-cmd meus-paths.json --scope user
pathpilot import-cmd meus-paths-system.json --scope system
```

### Segurança - Secrets

```bash
# Armazena token API criptografado
pathpilot env-add GITHUB_TOKEN "ghp_xxx" --scope user --encrypt
pathpilot env-add AWS_SECRET "xxx" --scope user --encrypt

# Verifica (descriptografa na hora)
pathpilot env-get GITHUB_TOKEN --show --scope user

# Auditoria
pathpilot log-verify
```