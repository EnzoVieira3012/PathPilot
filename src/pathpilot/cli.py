"""CLI do PathPilot - Typer + Rich + Questionary."""

import os
import sys
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .config import settings
from .core import PathService
from .db import init_db
from .models import Scope, SyncResult, ValidationResult
from .utils import print_error, print_info, print_success, print_warning, require_admin

# Console com encoding explicito para Windows
console = Console(force_terminal=True, color_system="truecolor", legacy_windows=False)


# Typer app com Rich markup
app = typer.Typer(
    name="pathpilot",
    help="[bold cyan]PathPilot[/] - Gerencie seu PATH do Windows com estilo",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]PathPilot[/] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback, is_eager=True, help="Mostra versao"),
    verbose: bool = typer.Option(False, "--verbose", help="Output verboso"),
):
    """PathPilot - Gerencie seu PATH do Windows com estilo"""
    init_db()


# ==================== COMANDOS ====================

@app.command()
def list(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    show_inactive: bool = typer.Option(False, "--all", "-a", help="Mostrar inativos"),
    format: str = typer.Option("table", "--format", "-f", help="Formato: table|tree|json"),
):
    """Lista paths gerenciados"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        entries = service.list_paths(sc, active_only=not show_inactive)
        _render_entries(entries, sc, format)


@app.command()
def add(
    path: str = typer.Argument(..., help="Caminho para adicionar"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    desc: str = typer.Option("", "--desc", "-d", help="Descricao opcional"),
    force: bool = typer.Option(False, "--force", "-f", help="Ignora validacoes"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Modo interativo"),
):
    """Adiciona path ao PATH do Windows"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    if interactive:
        path = questionary.path("Caminho do path:").ask() or ""
        sc = Scope(questionary.select("Escopo:", choices=["user", "system"]).ask())
        desc = questionary.text("Descricao (opcional):").ask() or ""

    if not path:
        print_error("Path nao informado")
        raise typer.Exit(1)

    result = service.add_path(path, sc, desc)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def remove(
    path: str = typer.Argument(..., help="Caminho para remover"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    force: bool = typer.Option(False, "--force", "-f", help="Nao confirma"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Modo interativo"),
):
    """Remove path do PATH do Windows"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    if interactive:
        entries = service.list_paths(sc, active_only=True)
        if not entries:
            print_warning("Nenhum path ativo para remover")
            raise typer.Exit()
        choices = [f"{e.path}" for e in entries]
        selected = questionary.select("Selecione o path para remover:", choices=choices).ask()
        if not selected:
            raise typer.Exit()
        path = selected

    if not force and settings.confirm_destructive and not Confirm.ask(f"[warning]Remover [path]{path}[/] do [scope.{sc.value}]{sc.label}[/]?"):
            print_info("Cancelado")
            raise typer.Exit()

    result = service.remove_path(path, sc)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def validate(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    fix: bool = typer.Option(False, "--fix", help="Remove entradas invalidas automaticamente"),
):
    """Valida paths (existe no disco, duplicados, etc)"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        result = service.validate_paths(sc)
        _render_validation(result, sc)

        if fix and (result.missing or result.duplicates or result.invalid):
            msg = f"Remover {len(result.missing)} ausentes + {len(result.duplicates)} duplicados + {len(result.invalid)} invalidos?"
            if Confirm.ask(msg):
                for p in result.missing + result.duplicates + result.invalid:
                    service.remove_path(p, sc)
                print_success("Limpeza concluida")


@app.command()
def sync(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Apenas mostra o que faria"),
):
    """Sincroniza DB com PATH real do Windows"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        if require_admin(sc) and not dry_run:
            print_error("Escopo 'system' requer admin para sincronizar")
            continue

        result = service.sync_from_system(sc)
        _render_sync(result, sc)

        if not dry_run and result.drift_detected:
            print_success(f"Sincronizado: +{len(result.added)} -{len(result.removed)}")


# ==================== REORDER COMMANDS ====================

@app.command()
def reorder(
    path: str = typer.Argument(..., help="Path para mover"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    direction: str = typer.Option("up", "--direction", "-d", help="Direcao: up|down"),
):
    """Move path uma posicao (up/down)"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    if direction == "up":
        result = service.move_path_up(path, sc)
    elif direction == "down":
        result = service.move_path_down(path, sc)
    else:
        print_error("Direcao invalida: use 'up' ou 'down'")
        raise typer.Exit(1)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def move_to(
    path: str = typer.Argument(..., help="Path para mover"),
    position: int = typer.Argument(..., help="Nova posicao (1-indexed)"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
):
    """Move path para posicao especifica"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    result = service.move_path_to_position(path, sc, position - 1)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def prioritize(
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    paths: str = typer.Option(None, "--paths", help="Paths separados por virgula (ordem = prioridade)"),
):
    """Coloca paths no topo na ordem especificada (--paths 'p1,p2,p3')"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    all_paths = []
    if paths:
        all_paths.extend([p.strip() for p in paths.split(",") if p.strip()])

    if not all_paths:
        print_error("Nenhum path informado (use --paths 'p1,p2,p3')")
        raise typer.Exit(1)

    result = service.reorder_by_priority(sc, all_paths)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


# ==================== BULK COMMANDS ====================

@app.command()
def add_bulk(
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    desc: str = typer.Option("", "--desc", "-d", help="Descricao para todos"),
    file: str = typer.Option(None, "--file", "-f", help="Arquivo com paths (um por linha)"),
    paths: str = typer.Option(None, "--paths", help="Paths separados por virgula"),
):
    """Adiciona multiplos paths de uma vez (--paths 'p1,p2' ou --file)"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    all_paths = []
    if paths:
        all_paths.extend([p.strip() for p in paths.split(",") if p.strip()])
    if file:
        try:
            all_paths.extend(Path(file).read_text(encoding="utf-8").strip().splitlines())
        except Exception as e:
            print_error(f"Erro ao ler arquivo: {e}")
            raise typer.Exit(1)

    if not all_paths:
        print_error("Nenhum path informado (use --paths 'p1,p2' ou --file)")
        raise typer.Exit(1)

    result = service.add_paths_bulk(all_paths, sc, desc)

    print_success(f"Sucesso: {result.success} | Falharam: {result.failed}")
    if result.errors:
        for err in result.errors:
            print_error(f"  {err}")


@app.command()
def remove_bulk(
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    file: str = typer.Option(None, "--file", "-f", help="Arquivo com paths (um por linha)"),
    force: bool = typer.Option(False, "--force", help="Nao confirma"),
    paths: str = typer.Option(None, "--paths", help="Paths separados por virgula"),
):
    """Remove multiplos paths de uma vez (--paths 'p1,p2' ou --file)"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    all_paths = []
    if paths:
        all_paths.extend([p.strip() for p in paths.split(",") if p.strip()])
    if file:
        try:
            all_paths.extend(Path(file).read_text(encoding="utf-8").strip().splitlines())
        except Exception as e:
            print_error(f"Erro ao ler arquivo: {e}")
            raise typer.Exit(1)

    if not all_paths:
        print_error("Nenhum path informado (use --paths 'p1,p2' ou --file)")
        raise typer.Exit(1)

    if not force and settings.confirm_destructive:
        if not Confirm.ask(f"Remover {len(all_paths)} paths do {sc.label}?"):
            print_info("Cancelado")
            raise typer.Exit()

    result = service.remove_paths_bulk(all_paths, sc)

    print_success(f"Sucesso: {result.success} | Falharam: {result.failed}")
    if result.errors:
        for err in result.errors:
            print_error(f"  {err}")


# ==================== IMPORT/EXPORT COMMANDS ====================

@app.command()
def export(
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    file: str = typer.Argument(..., help="Arquivo de saida"),
    format: str = typer.Option("json", "--format", "-f", help="Formato: json|csv"),
    active_only: bool = typer.Option(True, "--active-only/--all", help="So ativos"),
):
    """Exporta paths para JSON ou CSV"""
    service = PathService()
    sc = Scope(scope)

    if format == "json":
        result = service.export_to_json(sc, file, active_only)
    elif format == "csv":
        result = service.export_to_csv(sc, file, active_only)
    else:
        print_error("Formato invalido: use 'json' ou 'csv'")
        raise typer.Exit(1)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def import_cmd(
    file: str = typer.Argument(..., help="Arquivo para importar"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    format: str = typer.Option("json", "--format", "-f", help="Formato: json|csv"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Mesclar com existentes"),
):
    """Importa paths de JSON ou CSV"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    if format == "json":
        result = service.import_from_json(file, sc, merge)
    elif format == "csv":
        result = service.import_from_csv(file, sc, merge)
    else:
        print_error("Formato invalido: use 'json' ou 'csv'")
        raise typer.Exit(1)

    print_success(f"Importados: {result.imported} | Ignorados: {result.skipped}")
    if result.errors:
        for err in result.errors:
            print_error(f"  {err}")


# ==================== ADVANCED SYNC ====================

@app.command()
def sync_conflicts(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    strategy: str = typer.Option("keep_db", "--strategy", help="keep_db|keep_windows|keep_both"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Apenas detecta conflitos"),
):
    """Sync avancado com deteccao e resolucao de conflitos"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        if require_admin(sc) and not dry_run:
            print_error("Escopo 'system' requer admin para sincronizar")
            continue

        if dry_run:
            conflicts = service.detect_conflicts(sc)
            _render_conflicts(conflicts, sc)
        else:
            result = service.sync_with_conflicts(sc, strategy)
            _render_sync(result, sc)
            if result.drift_detected:
                print_success(f"Sincronizado: +{len(result.added)} -{len(result.removed)}")


@app.command()
def expand_vars(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
):
    """Expande variaveis de ambiente (%VAR%) nos paths do DB"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        if require_admin(sc):
            print_error("Escopo 'system' requer admin")
            continue

        result = service.expand_variables_in_db(sc)
        if result.success:
            print_success(result.message)
        else:
            print_error(result.message)


@app.command()
def validate_detailed(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    fix: bool = typer.Option(False, "--fix", help="Remove invalidos"),
):
    """Validacao avancada com expansao de variaveis"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        result = service.validate_paths_detailed(sc)
        _render_validation(result, sc)

        if fix and (result.missing or result.duplicates or result.invalid):
            msg = f"Remover {len(result.missing)} ausentes + {len(result.duplicates)} duplicados + {len(result.invalid)} invalidos?"
            if Confirm.ask(msg):
                for p in result.missing + result.duplicates + result.invalid:
                    service.remove_path(p, sc)
                print_success("Limpeza concluida")


def _render_conflicts(conflicts, scope: Scope):
    if not conflicts:
        print_success(f"Nenhum conflito detectado em {scope.label}")
        return

    scope_icon = "[USER]" if scope == Scope.USER else "[SYS]"
    console.print(Panel.fit(
        f"[bold]{scope_icon} {scope.label}[/]\nConflitos: [red]{len(conflicts)}[/]",
        title="[!] Conflitos de Sync",
        border_style="yellow",
    ))

    table = Table(title="Conflitos Detectados", show_header=True, header_style="bold cyan")
    table.add_column("Path", style="green", overflow="fold")
    table.add_column("No Windows", justify="center")
    table.add_column("No DB", justify="center")
    table.add_column("DB Ativo", justify="center")
    table.add_column("Resolucao", style="yellow")

    for c in conflicts:
        table.add_row(
            c.path,
            "[+]" if c.in_windows else "[-]",
            "[+]" if c.in_db else "[-]",
            "[+]" if c.db_active else "[-]",
            c.resolution
        )

    console.print(table)


@app.command()
def backup(
    name: str = typer.Argument(..., help="Nome do backup"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    desc: str = typer.Option("", "--desc", "-d", help="Descricao"),
):
    """Cria backup do PATH atual"""
    from .models import Backup
    from .repositories import BackupRepository
    from .windows_api import WindowsPathAPI

    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer admin")
        raise typer.Exit(1)

    win_api = WindowsPathAPI()
    paths = win_api.get_path(sc)

    backup = Backup(name=name, scope=sc, path_snapshot=paths, description=desc)
    BackupRepository().create(backup)

    print_success(f"Backup '[bold]{name}[/]' criado com {len(paths)} paths")


@app.command()
def restore(
    backup_id: int = typer.Argument(..., help="ID do backup"),
    scope: str = typer.Option(None, "--scope", "-s", help="Forcar escopo (padrao: do backup)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula sem aplicar"),
):
    """Restaura backup do PATH"""
    from .models import PathEntry
    from .repositories import BackupRepository, PathEntryRepository
    from .windows_api import WindowsPathAPI

    backup = BackupRepository().get_by_id(backup_id)
    if not backup:
        print_error(f"Backup {backup_id} nao encontrado")
        raise typer.Exit(1)

    sc = Scope(scope) if scope else backup.scope

    if require_admin(sc):
        print_error("Escopo 'system' requer admin")
        raise typer.Exit(1)

    if dry_run:
        print_info(f"[DRY-RUN] Restauraria {len(backup.path_snapshot)} paths no {sc.label}")
        for p in backup.path_snapshot:
            console.print(f"  [dim]->[/] {p}")
        raise typer.Exit()

    if settings.confirm_destructive and not Confirm.ask(f"[warning]Restaurar backup '[bold]{backup.name}[/]' ({len(backup.path_snapshot)} paths) no {sc.label}?"):
            print_info("Cancelado")
            raise typer.Exit()

    win_api = WindowsPathAPI()
    win_api.set_path(sc, backup.path_snapshot)

    # Atualiza DB
    repo = PathEntryRepository()
    for idx, p in enumerate(backup.path_snapshot):
        entry = repo.get_by_path(p, sc)
        if entry:
            entry.active = True
            entry.position = idx
            repo.update(entry)
        else:
            repo.create(PathEntry(path=p, scope=sc, active=True, position=idx))

    print_success(f"Backup '[bold]{backup.name}[/]' restaurado no {sc.label}")


# ==================== BACKUP/RESTORE ADVANCED ====================

@app.command()
def backup_verify(
    backup_id: int = typer.Argument(None, help="ID do backup (opcional com --all)"),
    all: bool = typer.Option(False, "--all", "-a", help="Verifica todos"),
    scope: str = typer.Option(None, "--scope", "-s", help="Escopo: user|system"),
):
    """Verifica integridade do backup (checksum SHA-256)"""
    service = PathService()

    if all:
        scopes = [Scope.USER, Scope.SYSTEM] if scope is None else [Scope(scope)]
        for sc in scopes:
            results = service.verify_all_backups(sc)
            print_info(f"{sc.label}: {len(results)} backups")
            for bid, ok in results:
                status = "[green]OK[/]" if ok else "[red]FALHOU[/]"
                console.print(f"  Backup #{bid}: {status}")
    else:
        if backup_id is None:
            print_error("Informe backup_id ou use --all")
            raise typer.Exit(1)
        ok = service.verify_backup(backup_id)
        status = "[green]OK[/]" if ok else "[red]FALHOU[/]"
        console.print(f"Backup #{backup_id}: {status}")
        if not ok:
            raise typer.Exit(1)


@app.command()
def restore_merge(
    backup_id: int = typer.Argument(..., help="ID do backup"),
    scope: str = typer.Option(None, "--scope", "-s", help="Escopo: user|system"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula sem aplicar"),
):
    """Restore merge: adiciona paths que faltam (nao remove existentes)"""
    service = PathService()

    backup = service.backup_repo.get_by_id(backup_id)
    if not backup:
        print_error(f"Backup {backup_id} nao encontrado")
        raise typer.Exit(1)

    sc = Scope(scope) if scope else backup.scope

    if require_admin(sc):
        print_error("Escopo 'system' requer admin")
        raise typer.Exit(1)

    result = service.restore_backup_merge(backup_id, sc, dry_run)

    console.print(Panel.fit(
        f"[bold]Backup:[/] {backup.name}\n"
        f"[bold]Escopo:[/] {sc.label}\n"
        f"[bold]Restaurados:[/] [green]{result.restored}[/]\n"
        f"[bold]Ignorados (ja existem):[/] [yellow]{result.skipped}[/]\n"
        f"[bold]Falharam:[/] [red]{result.failed}[/]",
        title="[+] Restore Merge" if not dry_run else "[i] DRY-RUN Restore Merge",
        border_style="green" if not dry_run else "yellow",
    ))

    if result.errors:
        for err in result.errors:
            print_error(f"  {err}")

    if not dry_run and result.restored > 0:
        print_success(f"Merge concluido: {result.restored} paths adicionados")


@app.command()
def backup_cleanup(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    max_backups: int = typer.Option(10, "--max", "-m", help="Maximo de backups para manter"),
    max_age_days: int = typer.Option(90, "--max-age", "-d", help="Idade maxima em dias"),
    dry_run: bool = typer.Option(False, "--dry-run", help="So mostra o que removeria"),
):
    """Remove backups antigos (mantem mais recentes e remove > idade)"""
    from datetime import datetime, timedelta

    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == "both" else [Scope(scope)]

    for sc in scopes:
        if require_admin(sc) and not dry_run:
            print_error("Escopo 'system' requer admin")
            continue

        if dry_run:
            backups = service.backup_repo.list_all(sc, limit=1000)
            to_remove = []
            cutoff = datetime.now() - timedelta(days=max_age_days)
            for b in backups:
                if b.created_at and b.created_at < cutoff:
                    to_remove.append(b)
            if len(backups) > max_backups:
                to_remove.extend(backups[max_backups:])

            if to_remove:
                console.print(f"[yellow]Removeria {len(to_remove)} backups em {sc.label}:[/]")
                for b in to_remove:
                    console.print(f"  {b.id}: {b.name} ({b.created_at})")
            else:
                print_success(f"Nada para remover em {sc.label}")
        else:
            removed = service.cleanup_backups(sc, max_backups, max_age_days)
            print_success(f"Removidos {removed} backups antigos em {sc.label}")


@app.command()
def backup_schedule(
    enabled: bool = typer.Argument(None, help="Ativar/desativar agendamento"),
    interval: int = typer.Option(24, "--interval", "-i", help="Intervalo em horas"),
    scope: str = typer.Option("user", "--scope", "-s", help="Escopo: user|system"),
    max_backups: int = typer.Option(10, "--max", "-m", help="Maximo de backups para manter"),
    status: bool = typer.Option(False, "--status", help="So mostra status"),
):
    """Configura agendamento automatico de backups"""
    service = PathService()
    sc = Scope(scope)

    if status:
        st = service.get_backup_schedule_status()
        console.print(Panel.fit(
            f"[bold]Ativo:[/] {'[green]SIM[/]' if st['enabled'] else '[red]NAO[/]'}\n"
            f"[bold]Intervalo:[/] {st['interval_hours']}h\n"
            f"[bold]Escopo:[/] {st['scope']}\n"
            f"[bold]Max backups:[/] {st['max_backups']}\n"
            f"[bold]Proximo:[/] {st['next_run'] or 'N/A'}",
            title="[*] Backup Schedule Status",
            border_style="cyan",
        ))
        return

    if require_admin(sc) and enabled:
        print_error("Escopo 'system' requer admin para agendar")
        raise typer.Exit(1)

    service.set_backup_schedule(enabled, interval, sc, max_backups)

    if enabled:
        print_success(f"Agendamento ativado: a cada {interval}h no {sc.label} (max {max_backups} backups)")
    else:
        print_success("Agendamento desativado")


@app.command()
def backup_auto(
    scope: str = typer.Option("both", "--scope", "-s", help="Escopo: user|system|both"),
    enable: bool = typer.Option(True, "--enable/--disable", help="Ativar/desativar auto-backup"),
):
    """Ativa/desativa auto-backup antes de operacoes destrutivas"""
    from .config import settings
    settings.auto_backup = enable
    print_success(f"Auto-backup {'ativado' if enable else 'desativado'}")


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Numero de entradas"),
    scope: str = typer.Option(None, "--scope", "-s", help="Filtrar por escopo"),
):
    """Historico de operacoes"""
    from .models import OperationStatus
    from .repositories import OperationLogRepository

    logs = OperationLogRepository().get_recent(limit)

    if scope:
        logs = [log_entry for log_entry in logs if log_entry.scope and log_entry.scope.value == scope]

    table = Table(title="Historico de Operacoes", show_header=True, header_style="bold cyan")
    table.add_column("Quando", style="dim", width=16)
    table.add_column("Op", width=10)
    table.add_column("Escopo", width=10)
    table.add_column("Path", overflow="fold")
    table.add_column("Status", justify="center")

    for log_entry in logs:
        status_color = {
            OperationStatus.SUCCESS: "green",
            OperationStatus.FAILED: "red",
            OperationStatus.PARTIAL: "yellow",
        }.get(log_entry.status, "white")

        scope_label = log_entry.scope.label if log_entry.scope else "-"
        table.add_row(
            log_entry.created_at.strftime("%Y-%m-%d %H:%M") if log_entry.created_at else "-",
            log_entry.operation.value.upper(),
            scope_label,
            log_entry.target_path or "-",
            f"[{status_color}]{log_entry.status.value}[/]",
        )

    console.print(table)


# ==================== MIGRATION COMMANDS ====================

@app.command()
def migrate(
    version: int = typer.Option(None, "--version", "-v", help="Versao alvo (padrao: latest)"),
    status: bool = typer.Option(False, "--status", "-s", help="So mostra status"),
):
    """Gerencia migracoes do banco de dados"""
    from .migrations import migration_status as get_status
    from .migrations import rollback_migration, run_migrations

    if status:
        st = get_status()
        _render_migration_status(st)
        return

    if version is not None:
        current = get_status()["current_version"]
        if version < current:
            # Rollback
            for v in range(current, version, -1):
                if not rollback_migration(v):
                    raise typer.Exit(1)
        else:
            # Forward to specific version
            run_migrations(version)
    else:
        # Run all pending
        run_migrations()


@app.command(name="db-stats")
def db_stats():
    """Mostra estatisticas do banco de dados"""
    from .db import get_db

    db = get_db()
    stats = db.get_stats()

    table = Table(title="Estatisticas do Banco", show_header=True, header_style="bold cyan")
    table.add_column("Tabela", style="cyan")
    table.add_column("Registros", justify="right", style="green")

    for table_name in ["env_vars", "path_entries", "backups", "operation_log", "user_settings"]:
        count = stats.get(table_name, 0)
        table.add_row(table_name, str(count))

    table.add_row("schema_version", str(stats.get("schema_version", 0)))
    size_mb = stats.get("db_size_bytes", 0) / (1024 * 1024)
    table.add_row("tamanho (MB)", f"{size_mb:.2f}")

    console.print(table)

    # Health check
    healthy = db.health_check()
    if healthy:
        print_success("Banco saudavel")
    else:
        print_error("Banco com problemas")


def _render_migration_status(st: dict):
    table = Table(title="Status das Migracoes", show_header=True, header_style="bold cyan")
    table.add_column("Versao", justify="right", width=8)
    table.add_column("Descricao", style="green")
    table.add_column("Status", justify="center", width=12)

    for m in st["applied"]:
        table.add_row(str(m["version"]), m["description"], "[green]OK[/]")

    for m in st["pending"]:
        table.add_row(str(m["version"]), m["description"], "[yellow]PENDENTE[/]")

    console.print(table)
    console.print(
        f"\nVersao atual: [bold]{st['current_version']}[/] | "
        f"Alvo: [bold]{st['target_version']}[/] | "
        f"Pendentes: [bold]{st['pending_count']}[/]"
    )


@app.command()
def interactive():
    """Modo interativo (menu)"""
    _interactive_menu()


# ==================== RENDERERS ====================

def _render_entries(entries, scope: Scope, format: str):
    if format == "json":
        import json
        console.print_json(json.dumps([{"path": e.path, "active": e.active, "desc": e.description} for e in entries]))
        return

    if format == "tree":
        scope_icon = "[USER]" if scope == Scope.USER else "[SYS]"
        tree = Tree(f"{scope_icon} [bold]{scope.label}[/] ({len(entries)} paths)")
        for e in entries:
            status = "[+]" if e.active else "[-]"
            desc_part = f" [dim]({e.description})[/]" if e.description else ""
            tree.add(f"{status} [path]{e.path}[/]{desc_part}")
        console.print(tree)
        return

    # Table (default)
    scope_icon = "[USER]" if scope == Scope.USER else "[SYS]"
    table = Table(
        title=f"{scope_icon} PATH - {scope.label}",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Path", style="green", overflow="fold", ratio=1)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Pos", justify="right", width=4)
    table.add_column("Descricao", style="dim", overflow="fold")

    for idx, e in enumerate(entries, 1):
        status = "[green][+] Ativo[/]" if e.active else "[red][-] Inativo[/]"
        table.add_row(str(idx), e.path, status, str(e.position), e.description or "-")

    console.print(table)


def _render_validation(result: ValidationResult, scope: Scope):
    scope_icon = "[USER]" if scope == Scope.USER else "[SYS]"
    console.print(Panel.fit(
        f"[bold]{scope_icon} {scope.label}[/]\n{result.summary}",
        title="[+] Validacao",
        border_style="green" if result.is_valid else "yellow",
    ))

    if result.missing:
        console.print("[red][-] Ausentes no disco:[/]")
        for p in result.missing:
            console.print(f"  [dim]->[/] {p}")

    if result.duplicates:
        console.print("[yellow][~] Duplicados:[/]")
        for p in result.duplicates:
            console.print(f"  [dim]->[/] {p}")

    if result.invalid:
        console.print("[red][!] Invalidos:[/]")
        for p in result.invalid:
            console.print(f"  [dim]->[/] {p}")


def _render_sync(result: SyncResult, scope: Scope):
    scope_icon = "[USER]" if scope == Scope.USER else "[SYS]"
    drift_text = "[red]SIM[/]" if result.drift_detected else "[green]NAO[/]"
    console.print(Panel.fit(
        f"[bold]{scope_icon} {scope.label}[/]\n"
        f"[+] Adicionados: [green]{len(result.added)}[/]\n"
        f"[-] Removidos: [red]{len(result.removed)}[/]\n"
        f"[=] Inalterados: [dim]{len(result.unchanged)}[/]\n"
        f"Drift: {drift_text}",
        title="[~] Sync",
        border_style="blue",
    ))

    if result.added:
        console.print("[green]Novos no Windows:[/]")
        for p in result.added:
            console.print(f"  [dim]+[/] {p}")

    if result.removed:
        console.print("[red]Removidos do Windows:[/]")
        for p in result.removed:
            console.print(f"  [dim]-[/] {p}")


# ==================== MENU INTERATIVO ====================

def _interactive_menu():
    service = PathService()

    while True:
        console.print()
        console.print(Panel.fit(
            "[bold cyan]PathPilot[/] - Menu Interativo",
            border_style="cyan",
        ))

        action = questionary.select(
            "O que deseja fazer?",
            choices=[
                "Listar paths (user)",
                "Listar paths (system)",
                "Adicionar path",
                "Remover path",
                "Validar paths",
                "Sincronizar com Windows",
                "Criar backup",
                "Restaurar backup",
                "Ver historico",
                "Sair",
            ],
            style=questionary.Style([
                ('selected', 'fg:#00d7ff bold'),
                ('pointer', 'fg:#ff6b6b bold'),
                ('highlighted', 'fg:#00d7ff'),
                ('question', 'bold'),
            ]),
        ).ask()

        if not action or action == "Sair":
            print_success("Ate mais!")
            break

        try:
            if "Listar paths (user)" in action:
                _render_entries(service.list_paths(Scope.USER), Scope.USER, "table")
            elif "Listar paths (system)" in action:
                _render_entries(service.list_paths(Scope.SYSTEM), Scope.SYSTEM, "table")
            elif "Adicionar" in action:
                path = questionary.path("Caminho:").ask()
                if path:
                    scope = Scope(questionary.select("Escopo:", choices=["user", "system"]).ask())
                    desc = questionary.text("Descricao (opcional):").ask() or ""
                    result = service.add_path(path, scope, desc)
                    if result.success:
                        print_success(result.message)
                    else:
                        print_error(result.message)
            elif "Remover" in action:
                scope = Scope(questionary.select("Escopo:", choices=["user", "system"]).ask())
                entries = service.list_paths(scope, active_only=True)
                if not entries:
                    print_warning("Nenhum path ativo")
                    continue
                choices = [f"{e.path}" for e in entries]
                selected = questionary.select("Path para remover:", choices=choices).ask()
                if selected:
                    if Confirm.ask(f"Remover {selected}?"):
                        result = service.remove_path(selected, scope)
                        if result.success:
                            print_success(result.message)
                        else:
                            print_error(result.message)
            elif "Validar" in action:
                scope = Scope(questionary.select("Escopo:", choices=["user", "system", "both"]).ask())
                sc = [Scope.USER, Scope.SYSTEM] if scope == "both" else [scope]
                for s in sc:
                    _render_validation(service.validate_paths(s), s)
            elif "Sincronizar" in action:
                scope = Scope(questionary.select("Escopo:", choices=["user", "system", "both"]).ask())
                sc = [Scope.USER, Scope.SYSTEM] if scope == "both" else [scope]
                for s in sc:
                    _render_sync(service.sync_from_system(s), s)
            elif "Criar backup" in action:
                name = questionary.text("Nome do backup:").ask()
                scope = Scope(questionary.select("Escopo:", choices=["user", "system"]).ask())
                desc = questionary.text("Descricao (opcional):").ask() or ""
                from .models import Backup
                from .repositories import BackupRepository
                from .windows_api import WindowsPathAPI
                paths = WindowsPathAPI().get_path(scope)
                BackupRepository().create(Backup(name=name, scope=scope, path_snapshot=paths, description=desc))
                print_success(f"Backup '{name}' criado")
            elif "Restaurar backup" in action:
                from .repositories import BackupRepository
                backups = BackupRepository().list_all(limit=20)
                if not backups:
                    print_warning("Nenhum backup")
                    continue
                choices = [f"{b.id}: {b.name} ({b.scope.label}) - {len(b.path_snapshot)} paths" for b in backups]
                selected = questionary.select("Backup:", choices=choices).ask()
                if selected:
                    backup_id = int(selected.split(":")[0])
                    if Confirm.ask("Confirmar restauracao?"):
                        print_info("Use: pathpilot restore <id>")
            elif "Historico" in action:
                from .repositories import OperationLogRepository
                logs = OperationLogRepository().get_recent(20)
                _render_history(logs)

        except KeyboardInterrupt:
            print_info("Cancelado")
        except Exception as e:
            print_error(f"Erro: {e}")


def _render_history(logs):
    from .models import OperationStatus
    table = Table(title="Historico Recente", show_header=True, header_style="bold cyan")
    table.add_column("Quando", style="dim", width=16)
    table.add_column("Op", width=10)
    table.add_column("Escopo", width=10)
    table.add_column("Path", overflow="fold")
    table.add_column("Status", justify="center")

    for log_entry in logs:
        status_color = {
            OperationStatus.SUCCESS: "green",
            OperationStatus.FAILED: "red",
            OperationStatus.PARTIAL: "yellow",
        }.get(log_entry.status, "white")

        scope_label = log_entry.scope.label if log_entry.scope else "-"
        table.add_row(
            log_entry.created_at.strftime("%Y-%m-%d %H:%M") if log_entry.created_at else "-",
            log_entry.operation.value.upper(),
            scope_label,
            log_entry.target_path or "-",
            f"[{status_color}]{log_entry.status.value}[/]",
        )
    console.print(table)


if __name__ == "__main__":
    app()
