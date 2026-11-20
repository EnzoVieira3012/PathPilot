# Variáveis de Ambiente

## Visão Geral

O PathPilot gerencia variáveis de ambiente com **criptografia opcional** via Fernet (AES-128-CBC + HMAC).

- **Scope**: `user` (HKCU\Environment) ou `system` (HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment)
- **Criptografia**: Transparente — descriptografa automaticamente ao ler
- **HMAC**: Logs de operações assinados para integridade

## Adicionar Variáveis

### Plain (Não Criptografada)

```bash
pathpilot env-add MINHA_VAR "valor_simples" --scope user
pathpilot env-add CAMINHO "C:\MeusScripts" --scope user --desc "Path personalizado"
```

### Criptografada

```bash
# Adiciona já criptografada
pathpilot env-add API_TOKEN "sk-xxx" --scope user --encrypt
pathpilot env-add DB_PASSWORD "senha123" --scope user --encrypt --desc "Banco produção"
```

## Obter Valor

```bash
# Valor mascarado (padrão)
pathpilot env-get API_TOKEN --scope user
# Output: ***CRIPTOGRAFADO***

# Valor descriptografado (--show)
pathpilot env-get API_TOKEN --scope user --show
# Output: sk-xxx
```

## Listar Variáveis

```bash
# Todas
pathpilot env-list --scope user

# Apenas criptografadas
pathpilot env-list --scope user --encrypted-only
```

### Saída

```
┌────────────────────┬────────────┬─────────┬────────────────────┐
│ Nome               │ Scope      │ Encrypt │ Descrição          │
├────────────────────┼────────────┼─────────┼────────────────────┤
│ PATH               │ user       │ ✗       │ System PATH        │
│ MINHA_VAR          │ user       │ ✗       │ Variável simples   │
│ API_TOKEN          │ user       │ ✓       │ Token API GitHub   │
│ DB_PASSWORD        │ user       │ ✓       │ Banco produção     │
└────────────────────┴────────────┴─────────┴────────────────────┘
```

## Criptografar/Descriptografar Existentes

```bash
# Criptografa variável plain existente
pathpilot env-encrypt MINHA_VAR --scope user

# Descriptografa (remove flag encrypted, mantém valor plain)
pathpilot env-decrypt API_TOKEN --scope user
```

## Gerar Chave Fernet

```bash
pathpilot crypto-keygen
# Output: MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw=
# Copie para PATHPILOT_FERNET_KEY no .env
```

## Segurança

### Como Funciona

1. **Chave Fernet**: 32 bytes base64 (`PATHPILOT_FERNET_KEY`)
2. **Criptografia**: Fernet (AES-128-CBC + HMAC-SHA256)
3. **Armazenamento**: Valor criptografado + flag `encrypted=1` no DB
4. **Leitura**: Descriptografa automaticamente se flag=1
5. **HMAC Logs**: Operações de env var assinadas com `PATHPILOT_HMAC_KEY`

### Threat Model

| Ameaça | Mitigação |
|--------|-----------|
| Leitura DB local | Valores sensíveis criptografados |
| Tampering logs | HMAC-SHA256 em cada entry |
| Key rotation | Re-criptografar com nova chave |
| Memory dump | Chaves apenas em memória durante ops |

### Key Rotation

```bash
# 1. Gera nova chave
pathpilot crypto-keygen

# 2. Atualiza .env com nova chave
# PATHPILOT_FERNET_KEY=nova_chave

# 3. Re-criptografa todas vars (manual via script ou re-add)
# Vars antigas ficam ilegíveis até re-criptografadas
```

## Integração com Windows

Variáveis adicionadas via PathPilot aparecem no:
- **User**: `Painel de Controle > Sistema > Variáveis de Ambiente > Variáveis do Usuário`
- **System**: `Painel de Controle > Sistema > Variáveis de Ambiente > Variáveis do Sistema` (admin)

### Broadcast

Mudanças notificam Windows automaticamente via `WM_SETTINGCHANGE`:
```python
# Interno - broadcast_environment_change()
ctypes.windll.user32.SendMessageTimeoutW(
    HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment"
)
```

Apps novos herdam variáveis; apps existentes podem precisar restart.

## Boas Práticas

1. **Sempre criptografe** secrets (tokens, senhas, chaves)
2. **Use `--show`** apenas quando necessário
3. **Audite logs** com `pathpilot log-verify`
4. **Rotacione chaves** periodicamente
5. **Backup .env** em local seguro (não commite!)
6. **Scope system** apenas para variáveis globais necessárias
7. **Descrições** ajudam auditoria futura

## Troubleshooting

| Problema | Solução |
|----------|---------|
| `Fernet key invalid` | `pathpilot crypto-keygen` e atualize `.env` |
| `Decryption failed` | Chave errada ou dado corrompido |
| `HMAC verification failed` | Log tampered ou `PATHPILOT_HMAC_KEY` mudou |
| Variável não aparece no Windows | Restart terminal / Explorer / app |