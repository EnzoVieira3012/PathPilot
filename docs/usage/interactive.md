# Modo Interativo

## Iniciar

```bash
pathpilot interactive
```

## Interface

```
╭─────────────────────────────────────────────────────────────╮
│                        PATHPILOT                            │
│          Gerenciador de PATH do Windows v0.6.0              │
╰─────────────────────────────────────────────────────────────╯

┌─────────────────────────────────────────────────────────────┐
│ [1] Listar PATHs              [6] Backup & Restore          │
│ [2] Adicionar PATH            [7] Variáveis de Ambiente     │
│ [3] Remover PATH              [8] Configurações             │
│ [4] Reordenar / Priorizar     [9] Database & Auditoria      │
│ [5] Validar / Sync            [0] Sair                      │
└─────────────────────────────────────────────────────────────┘

Escolha uma opção: 
```

## Navegação

- **Números**: Seleção direta (1-9, 0)
- **Setas**: Navegação em listas
- **Enter**: Confirma seleção
- **Esc / Ctrl+C**: Volta / Sai
- **Tab**: Auto-complete em inputs

## Fluxos Principais

### 1. Listar PATHs

```
┌─────────────────────────────────────────────────────────────┐
│ PATHs do Usuário (12 ativos, 3 inativos)                   │
├────┬──────────────────────────────┬────────┬────────────────┤
│ #  │ Path                         │ Status │ Descrição      │
├────┼──────────────────────────────┼────────┼────────────────┤
│ 1  │ C:\Windows\System32          │ ✓ Ativo│ Sistema        │
│ 2  │ C:\Python311                 │ ✓ Ativo│ Python         │
│ 3  │ C:\Tools\bin                 │ ✓ Ativo│ Ferramentas    │
│ 4  │ C:\Old\Path                  │ ✗ Inat.│ Antigo         │
└────┴──────────────────────────────┴────────┴────────────────┘

[A]tivar  [D]esativar  [R]emover  [M]over  [V]oltar
```

### 2. Adicionar PATH

```
┌─────────────────────────────────────────────────────────────┐
│ Adicionar Novo PATH                                         │
├─────────────────────────────────────────────────────────────┤
│ Path: C:\MeusScripts                                        │
│ Scope: [U]suário  [S]istema                                 │
│ Descrição: Scripts pessoais                                 │
│ Posição (opcional): 0                                       │
│ Criptografar? [s/N]: N                                      │
└─────────────────────────────────────────────────────────────┘
```

### 3. Reordenar

```
┌─────────────────────────────────────────────────────────────┐
│ Reordenar PATHs                                             │
├─────────────────────────────────────────────────────────────┤
│ Selecione PATHs na ordem de prioridade (Enter para mover)  │
│                                                             │
│ ▸ C:\Python311          (pos 0)                            │
│   C:\Python311\Scripts  (pos 1)                            │
│   C:\Tools\bin          (pos 2)                            │
│   C:\Windows\System32   (pos 3)                            │
└─────────────────────────────────────────────────────────────┘
```

### 4. Backup & Restore

```
┌─────────────────────────────────────────────────────────────┐
│ Backup & Restore                                            │
├─────────────────────────────────────────────────────────────┤
│ [1] Criar Backup                                           │
│ [2] Listar Backups                                         │
│ [3] Verificar Integridade                                  │
│ [4] Restore Merge (adiciona faltando)                      │
│ [5] Restore Full (substitui tudo)                          │
│ [6] Agendamento Automático                                 │
│ [7] Limpar Backups Antigos                                 │
│ [0] Voltar                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 5. Variáveis de Ambiente

```
┌─────────────────────────────────────────────────────────────┐
│ Variáveis de Ambiente                                       │
├─────────────────────────────────────────────────────────────┤
│ [1] Listar (todas)                                         │
│ [2] Listar (criptografadas)                                │
│ [3] Adicionar (plain)                                      │
│ [4] Adicionar (criptografada)                              │
│ [5] Obter Valor (--show)                                   │
│ [6] Criptografar Existente                                 │
│ [7] Descriptografar Existente                              │
│ [8] Gerar Chave Fernet                                     │
│ [0] Voltar                                                 │
└─────────────────────────────────────────────────────────────┘
```

## Atalhos Globais

| Tecla | Ação |
|-------|------|
| `Ctrl+C` | Sai do programa |
| `Ctrl+L` | Limpa tela / Redesenha |
| `?` | Ajuda contextual |
| `q` | Volta menu anterior |
| `h` | Home (menu principal) |

## Dicas

1. **Use Tab** para auto-complete de paths
2. **Confirmações** aparecem para operações destrutivas
3. **Dry-run** disponível em restore/sync
4. **Validação** roda automaticamente após mudanças
5. **Logs** ficam em `operation_log` (auditoria)
6. **Exit code** 0 = sucesso, 1 = erro, 130 = Ctrl+C

## Sair

- Menu principal → `0` ou `Ctrl+C`
- Submenu → `0` ou `q` ou `Esc`
- Input → `Ctrl+C` cancela