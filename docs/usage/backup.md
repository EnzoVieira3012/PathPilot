# Backup & Restore

## Conceitos

- **Snapshot**: Cópia completa do PATH (user ou system) em JSON
- **Checksum**: SHA-256 do snapshot para integridade
- **Merge Restore**: Adiciona paths faltando, mantém existentes
- **Full Restore**: Substitui PATH completamente pelo snapshot
- **Agendamento**: Backup automático por intervalo

## Backup Manual

```bash
# Básico
pathpilot backup "backup-diario" --scope user

# Com descrição
pathpilot backup "antes-atualizacao" --scope user --desc "Antes de atualizar Python"

# Sistema (admin)
pathpilot backup "system-backup" --scope system
```

### Saída

```
✓ Backup criado com sucesso
  ID: 5
  Nome: backup-diario
  Scope: user
  Paths: 12
  Checksum: a1b2c3d4e5f6...
  Criado em: 2024-01-15 14:30:22
```

## Listar Backups

```bash
pathpilot backups --scope user
```

```
┌────┬─────────────────────┬────────┬──────────┬──────────────────────┬──────────┐
│ ID │ Nome                │ Scope  │ Paths    │ Criado em            │ Checksum │
├────┼─────────────────────┼────────┼──────────┼──────────────────────┼──────────┤
│ 1  │ estado-original     │ user   │ 8        │ 2024-01-10 10:00:00  │ abc123   │
│ 2  │ antes-atualizacao   │ user   │ 10       │ 2024-01-12 09:15:00  │ def456   │
│ 3  │ backup-diario       │ user   │ 12       │ 2024-01-15 14:30:22  │ a1b2c3   │
└────┴─────────────────────┴────────┴──────────┴──────────────────────┴──────────┘
```

## Verificar Integridade

```bash
pathpilot backup-verify 3 --scope user
```

Verifica se checksum do snapshot confere com dados atuais no DB.

## Restore

### Merge Restore (Recomendado)

Adiciona paths do backup que não existem no PATH atual. Mantém paths atuais.

```bash
# Dry-run primeiro
pathpilot restore 3 --merge --scope user --dry-run

# Executa
pathpilot restore 3 --merge --scope user
```

```
✓ Restore merge concluído
  Restaurados: 3
  Pulados (já existiam): 9
  Conflitos: 0
```

### Full Restore (Cuidado!)

Substitui **completamente** o PATH pelo snapshot do backup.

```bash
# Dry-run OBRIGATÓRIO primeiro
pathpilot restore 3 --full --scope user --dry-run

# Executa (requer confirmação)
pathpilot restore 3 --full --scope user
```

```
⚠ ATENÇÃO: Isto SUBSTITUIRÁ todo o PATH do usuário!
  Paths atuais serão removidos: 12
  Paths do backup serão aplicados: 10
  Continuar? [y/N]: y

✓ Restore full concluído
  Removidos: 12
  Adicionados: 10
```

## Agendamento Automático

```bash
# Ativa: a cada 12h, máx 30 backups
pathpilot backup-schedule --enable --interval 12 --max-backups 30 --scope user

# Desativa
pathpilot backup-schedule --disable

# Status
pathpilot backup-schedule --status
```

### Config via Settings

```bash
pathpilot config set backup.schedule.enabled true
pathpilot config set backup.schedule.interval_hours 12
pathpilot config set backup.schedule.max_backups 30
```

## Backup Automático (Hooks)

```bash
# Ativa backup antes de cada mudança destrutiva
pathpilot config set backup.auto.enabled true
pathpilot config set backup.auto.max_backups 10
pathpilot config set backup.auto.max_age_days 30
```

Quando ativo, cria backup automático antes de:
- `remove`
- `remove-bulk`
- `restore --full`
- `sync` (com mudanças)

## Limpeza

```bash
# Remove backups antigos (mantém últimos 10, máx 30 dias)
pathpilot backup-cleanup --scope user --max-backups 10 --max-age-days 30

# Dry-run
pathpilot backup-cleanup --scope user --max-backups 10 --dry-run
```

### Critérios

1. **Max backups**: Mantém apenas os N mais recentes
2. **Max age**: Remove backups mais velhos que N dias
3. **Aplica ambos**: Remove os que excederem qualquer limite

## Exportar Backup

```bash
# Exporta backup específico para JSON
pathpilot export backup-3.json --scope user --format json --backup-id 3

# O arquivo contém metadados + snapshot completo
```

## Estrutura do Backup (JSON)

```json
{
  "id": 3,
  "name": "backup-diario",
  "scope": "user",
  "path_snapshot": [
    "C:\\Windows\\System32",
    "C:\\Python311",
    "C:\\Tools\\bin"
  ],
  "description": "Backup diário automático",
  "checksum": "a1b2c3d4e5f6...",
  "created_at": "2024-01-15T14:30:22.123456"
}
```

## Boas Práticas

1. **Sempre faça backup** antes de mudanças grandes
2. **Use merge restore** na maioria dos casos (mais seguro)
3. **Full restore** apenas para disaster recovery
4. **Agende backups** automáticos em produção
5. **Verifique integridade** periodicamente: `backup-verify`
6. **Limpe backups** antigos para economizar espaço
7. **Exporte backups** críticos para armazenamento externo