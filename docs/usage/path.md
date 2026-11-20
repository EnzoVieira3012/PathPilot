# Gerenciamento de PATH

## Listar Paths

```bash
# Todos (ativo + inativo)
pathpilot list --scope user

# Apenas ativos
pathpilot list --scope user --active-only

# Sistema (requer admin)
pathpilot list --scope system
```

### Saída Exemplo

```
┌─────┬──────────────────────────────┬────────┬──────────┬─────────────────────┐
│ #   │ Path                         │ Active │ Position │ Description         │
├─────┼──────────────────────────────┼────────┼──────────┼─────────────────────┤
│ 1   │ C:\Windows\System32          │ ✓      │ 0        │ System              │
│ 2   │ C:\Python311                 │ ✓      │ 1        │ Python              │
│ 3   │ C:\Tools\bin                 │ ✓      │ 2        │ Ferramentas         │
│ 4   │ C:\Old\Path                  │ ✗      │ 3        │ Antigo (inativo)    │
└─────┴──────────────────────────────┴────────┴──────────┴─────────────────────┘
```

## Adicionar Path

```bash
# Básico
pathpilot add "C:\MeusScripts" --scope user

# Com descrição
pathpilot add "C:\MeusScripts" --scope user --desc "Scripts pessoais"

# Em posição específica
pathpilot add "C:\Priority" --scope user --position 0
```

### Comportamento

- **Duplicado ativo**: Rejeita com erro
- **Duplicado inativo**: Reativa (define active=true)
- **Path inválido**: Validação básica (chars proibidos, traversal)
- **Broadcast**: Notifica Windows da mudança automaticamente

## Remover Path

```bash
# Desativa (mantém no DB)
pathpilot remove "C:\MeusScripts" --scope user

# Remove completamente do DB (não implementado - use delete manual se necessário)
```

### Comportamento

- Define `active=false` no DB
- Remove do PATH real do Windows
- Mantém histórico para restore

## Reordenar

### Move Up/Down (Relativo)

```bash
# Move uma posição para cima
pathpilot reorder "C:\MeusScripts" --direction up --scope user

# Move uma posição para baixo
pathpilot reorder "C:\MeusScripts" --direction down --scope user
```

### Move To (Absoluto)

```bash
# Move para posição 0 (primeiro)
pathpilot move-to "C:\MeusScripts" 0 --scope user

# Move para posição 5
pathpilot move-to "C:\MeusScripts" 5 --scope user
```

### Prioritize (Múltiplos)

```bash
# Define ordem de prioridade para lista
pathpilot prioritize --paths "C:\Python311,C:\Python311\Scripts,C:\Tools\bin" --scope user
# Resultado: Python311=0, Scripts=1, Tools=2, resto mantém ordem relativa
```

## Validação

### Simples

```bash
pathpilot validate --scope user
```

Verifica: existência no filesystem, duplicados, paths inválidos.

### Detalhada

```bash
pathpilot validate-detailed --scope user
```

```
┌────────────────────┬──────────────────────────────────────┐
│ Categoria          │ Paths                                │
├────────────────────┼──────────────────────────────────────┤
│ ✓ Válidos (3)      │ C:\Windows\System32                  │
│                    │ C:\Python311                         │
│                    │ C:\Tools\bin                         │
├────────────────────┼──────────────────────────────────────┤
│ ✗ Faltando (1)     │ C:\Old\Removed                       │
├────────────────────┼──────────────────────────────────────┤
│ ⚠ Duplicados (1)   │ C:\Duplicate (2 entradas)            │
├────────────────────┼──────────────────────────────────────┤
│ ✗ Inválidos (0)    │ (nenhum)                             │
└────────────────────┴──────────────────────────────────────┘
```

## Expansão de Variáveis

```bash
# Expande %VAR% no DB para valores reais
pathpilot expand-vars --scope user
```

Útil para paths como `%USERPROFILE%\AppData\Local\Microsoft\WindowsApps`.

## Sync com Windows

```bash
# Detecta drift (diferença DB vs Windows)
pathpilot sync --scope user --dry-run

# Aplica sync
pathpilot sync --scope user
```

### Conflitos Avançados

```bash
# Estratégias:
# keep_db  - Mantém DB, ignora Windows
# keep_win - Mantém Windows, ignora DB
# merge    - Une ambos (padrão)
pathpilot sync-conflicts --strategy merge --scope user
```

## Bulk Operations

### Add Bulk

```bash
pathpilot add-bulk --paths "C:\A,C:\B,C:\C" --scope user
# Output: 3 sucessos, 0 falhas
```

### Remove Bulk

```bash
pathpilot remove-bulk --paths "C:\A,C:\B" --scope user
# Output: 2 sucessos, 0 falhas
```

## Dicas

1. **Use `--dry-run`** antes de operações destrutivas
2. **Faça backup** antes de bulk operations grandes
3. **Valide depois** de mudanças: `pathpilot validate-detailed`
4. **Scope system** requer terminal como Administrador
5. **Positions** são reindexadas automaticamente após insert/delete