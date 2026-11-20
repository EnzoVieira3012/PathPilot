<#
.SYNOPSIS
    PathPilot PowerShell Tab Completion Script

.DESCRIPTION
    Provides tab completion for PathPilot CLI commands, options, and arguments.
    Supports dynamic completion for scopes, backup IDs, paths, etc.

.INSTALLATION
    # Opção 1: Source direto no perfil
    . "C:\caminho\para\pathpilot_completion.ps1"
    
    # Opção 2: Adiciona ao $PROFILE
    Add-Content $PROFILE ". 'C:\caminho\para\pathpilot_completion.ps1'"
    
    # Opção 3: Instala via pipx/pip (quando disponível)
    # pathpilot --install-completion powershell

.EXAMPLE
    pathpilot <TAB>           # Lista comandos
    pathpilot add <TAB>       # Completa paths conhecidos
    pathpilot backup <TAB>    # Sugere nomes de backup
    pathpilot restore <TAB>   # Lista IDs de backup
    pathpilot --scope <TAB>   # user, system
#>

# Verifica se pathpilot está disponível
if (-not (Get-Command pathpilot -ErrorAction SilentlyContinue)) {
    if (Test-Path "$env:USERPROFILE\.local\bin\pathpilot.exe") {
        $env:PATH += ";$env:USERPROFILE\.local\bin"
    } elseif (Test-Path "$env:APPDATA\Python\Scripts\pathpilot.exe") {
        $env:PATH += ";$env:APPDATA\Python\Scripts"
    }
}

# Cache para completions dinâmicas
$script:pathpilotCache = @{
    backups = @{}
    paths   = @{}
    envVars = @{}
    lastUpdate = $null
}

function Update-PathPilotCache {
    param([string]$Scope = "user")
    
    $now = Get-Date
    if ($script:pathpilotCache.lastUpdate -and ($now - $script:pathpilotCache.lastUpdate).TotalSeconds -lt 30) {
        return
    }
    
    try {
        # Backups
        $backups = pathpilot backups --scope $Scope --format json 2>$null | ConvertFrom-Json
        if ($backups) {
            $script:pathpilotCache.backups[$Scope] = $backups | ForEach-Object { $_.id.ToString() }
        }
        
        # Paths (ativos)
        $paths = pathpilot list --scope $Scope --active-only --format json 2>$null | ConvertFrom-Json
        if ($paths) {
            $script:pathpilotCache.paths[$Scope] = $paths | ForEach-Object { $_.path }
        }
        
        # Env vars
        $envVars = pathpilot env-list --scope $Scope --format json 2>$null | ConvertFrom-Json
        if ($envVars) {
            $script:pathpilotCache.envVars[$Scope] = $envVars | ForEach-Object { $_.name }
        }
        
        $script:pathpilotCache.lastUpdate = $now
    } catch {
        # Ignora erros de cache
    }
}

# Completion principal
Register-ArgumentCompleter -CommandName pathpilot -ScriptBlock {
    param($commandName, $wordToComplete, $cursorPosition)
    
    $line = $PSReadLine.GetBufferState().ToString()
    $tokens = $line -split '\s+' | Where-Object { $_ }
    
    # Primeiro token é o comando
    if ($tokens.Count -le 1) {
        # Completa subcomandos
        $subcommands = @(
            'list', 'add', 'remove', 'reorder', 'move-to', 'prioritize',
            'add-bulk', 'remove-bulk', 'validate', 'validate-detailed',
            'expand-vars', 'sync', 'sync-conflicts', 'export', 'import-cmd',
            'backup', 'backups', 'restore', 'backup-verify', 'backup-cleanup',
            'backup-schedule', 'env-add', 'env-get', 'env-list', 'env-encrypt',
            'env-decrypt', 'crypto-keygen', 'db-stats', 'migrate', 'history',
            'log-verify', 'interactive', 'config'
        )
        $subcommands | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
        return
    }
    
    $command = $tokens[1]
    $prevToken = if ($tokens.Count -ge 3) { $tokens[$tokens.Count - 2] } else { '' }
    $currentToken = if ($tokens.Count -ge 2) { $tokens[$tokens.Count - 1] } else { '' }
    
    # Determina scope atual
    $scope = "user"
    for ($i = 2; $i -lt $tokens.Count; $i++) {
        if ($tokens[$i] -eq '--scope' -and $i + 1 -lt $tokens.Count) {
            $scope = $tokens[$i + 1]
            break
        }
    }
    
    # Atualiza cache
    Update-PathPilotCache -Scope $scope
    
    $completions = @()
    
    switch -Regex ($command) {
        '^list$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($prevToken -eq '--format') { 'table', 'json', 'csv' }
        }
        '^add$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($prevToken -eq '--position') { '0', '1', '2', '3', '4', '5' }
            else {
                # Sugere paths comuns
                @(
                    'C:\Windows\System32',
                    'C:\Python311',
                    'C:\Python311\Scripts',
                    'C:\Program Files\Git\bin',
                    'C:\Tools\bin',
                    '%USERPROFILE%\AppData\Local\Microsoft\WindowsApps'
                )
            }
        }
        '^remove$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            else { $script:pathpilotCache.paths[$scope] }
        }
        '^reorder$' {
            if ($prevToken -eq '--direction') { 'up', 'down' }
            elseif ($prevToken -eq '--scope') { 'user', 'system' }
            else { $script:pathpilotCache.paths[$scope] }
        }
        '^move-to$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($currentToken -match '^\d+$') { '0', '1', '2', '3', '4', '5', '10' }
            else { $script:pathpilotCache.paths[$scope] }
        }
        '^prioritize$' {
            if ($prevToken -eq '--paths') { $script:pathpilotCache.paths[$scope] }
            elseif ($prevToken -eq '--scope') { 'user', 'system' }
        }
        '^add-bulk$' {
            if ($prevToken -eq '--paths') { $script:pathpilotCache.paths[$scope] }
            elseif ($prevToken -eq '--scope') { 'user', 'system' }
        }
        '^remove-bulk$' {
            if ($prevToken -eq '--paths') { $script:pathpilotCache.paths[$scope] }
            elseif ($prevToken -eq '--scope') { 'user', 'system' }
        }
        '^validate$' { if ($prevToken -eq '--scope') { 'user', 'system' } }
        '^validate-detailed$' { if ($prevToken -eq '--scope') { 'user', 'system' } }
        '^expand-vars$' { if ($prevToken -eq '--scope') { 'user', 'system' } }
        '^sync$' { if ($prevToken -eq '--scope') { 'user', 'system' } }
        '^sync-conflicts$' {
            if ($prevToken -eq '--strategy') { 'keep_db', 'keep_win', 'merge' }
            elseif ($prevToken -eq '--scope') { 'user', 'system' }
        }
        '^export$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($prevToken -eq '--format') { 'json', 'csv' }
            elseif ($currentToken -match '\.(json|csv)$') { } # Arquivo
        }
        '^import-cmd$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($currentToken -match '\.json$') { } # Arquivo
        }
        '^backup$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            else { 'backup-' + (Get-Date -Format 'yyyy-MM-dd') }
        }
        '^backups$' { if ($prevToken -eq '--scope') { 'user', 'system' } }
        '^restore$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($prevToken -eq '--format') { 'merge', 'full' }
            else { $script:pathpilotCache.backups[$scope] }
        }
        '^backup-verify$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            else { $script:pathpilotCache.backups[$scope] }
        }
        '^backup-cleanup$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($prevToken -eq '--max-backups') { '5', '10', '20', '30', '50' }
            elseif ($prevToken -eq '--max-age-days') { '7', '14', '30', '60', '90' }
        }
        '^backup-schedule$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            elseif ($prevToken -eq '--interval') { '6', '12', '24', '48', '168' }
            elseif ($prevToken -eq '--max-backups') { '10', '20', '30', '50', '100' }
        }
        '^env-add$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
        }
        '^env-get$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            else { $script:pathpilotCache.envVars[$scope] }
        }
        '^env-list$' { if ($prevToken -eq '--scope') { 'user', 'system' } }
        '^env-encrypt$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            else { $script:pathpilotCache.envVars[$scope] }
        }
        '^env-decrypt$' {
            if ($prevToken -eq '--scope') { 'user', 'system' }
            else { $script:pathpilotCache.envVars[$scope] }
        }
        '^history$' {
            if ($prevToken -eq '--limit') { '10', '20', '50', '100' }
            elseif ($prevToken -eq '--scope') { 'user', 'system' }
        }
        '^config$' {
            $sub = @('show', 'set', 'get')
            if ($tokens.Count -eq 2) { $sub }
            elseif ($prevToken -eq 'set' -or $prevToken -eq 'get') {
                @(
                    'db_path', 'fernet_key', 'hmac_key', 'default_scope',
                    'auto_backup', 'confirm_destructive', 'theme',
                    'show_progress', 'use_emoji'
                )
            }
        }
        '^interactive$' { }
        '^crypto-keygen$' { }
        '^db-stats$' { }
        '^migrate$' { }
        '^log-verify$' { }
        default {
            # Opções globais
            if ($wordToComplete -like '--*') {
                @(
                    '--help', '--version', '--scope', '--format', '--active-only',
                    '--dry-run', '--force', '--show', '--encrypt', '--decrypt',
                    '--encrypted-only', '--limit', '--position', '--direction',
                    '--strategy', '--interval', '--max-backups', '--max-age-days',
                    '--desc', '--description'
                ) | Where-Object { $_ -like "$wordToComplete*" }
            }
        }
    }
    
    $completions | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}

# Aliases úteis
Set-Alias -Name pp -Value pathpilot -Option AllScope
Set-Alias -Name ppl -Value "pathpilot list" -Option AllScope
Set-Alias -Name ppa -Value "pathpilot add" -Option AllScope
Set-Alias -Name ppr -Value "pathpilot remove" -Option AllScope
Set-Alias -Name ppb -Value "pathpilot backup" -Option AllScope
Set-Alias -Name ppe -Value "pathpilot env-add" -Option AllScope

Write-Host "PathPilot completion loaded. Type 'pathpilot <TAB>' to use." -ForegroundColor Green