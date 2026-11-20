"""CLI do PathPilot - Typer + Rich + Questionary."""

import os
import sys

# Force UTF-8 on Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

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
from .utils import (
    print_error,
    print_info,
    print_success,
    print_warning,
    require_admin,
)

# Console com encoding explicito para Windows
console = Console(force_terminal=True, color_system='truecolor', legacy_windows=False)


# Typer app com Rich markup
app = typer.Typer(
    name='pathpilot',
    help='[bold cyan]PathPilot[/] - Gerencie seu PATH do Windows com estilo',
    rich_markup_mode='rich',
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool):
    if value:
        console.print(f'[bold cyan]PathPilot[/] v{__version__}')
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, '--version', '-v', callback=version_callback, is_eager=True, help='Mostra versao'
    ),
    verbose: bool = typer.Option(False, '--verbose', help='Output verboso'),
):
    """PathPilot - Gerencie seu PATH do Windows com estilo"""
    init_db()


# ==================== COMANDOS ====================


@app.command()
def list(
    scope: str = typer.Option('both', '--scope', '-s', help='Escopo: user|system|both'),
    show_inactive: bool = typer.Option(False, '--all', '-a', help='Mostrar inativos'),
    format: str = typer.Option('table', '--format', '-f', help='Formato: table|tree|json'),
):
    """Lista paths gerenciados"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == 'both' else [Scope(scope)]

    for sc in scopes:
        entries = service.list_paths(sc, active_only=not show_inactive)
        _render_entries(entries, sc, format)


@app.command()
def add(
    path: str = typer.Argument(..., help='Caminho para adicionar'),
    scope: str = typer.Option('user', '--scope', '-s', help='Escopo: user|system'),
    desc: str = typer.Option('', '--desc', '-d', help='Descricao opcional'),
    force: bool = typer.Option(False, '--force', '-f', help='Ignora validacoes'),
    interactive: bool = typer.Option(False, '--interactive', '-i', help='Modo interativo'),
):
    """Adiciona path ao PATH do Windows"""
    service = PathService()
    sc = Scope(scope)

    if require_admin(sc):
        print_error("Escopo 'system' requer execucao como administrador")
        raise typer.Exit(1)

    if interactive:
        path = questionary.path('Caminho do path:').ask() or ''
        sc = Scope(questionary.select('Escopo:', choices=['user', 'system']).ask())
        desc = questionary.text('Descricao (opcional):').ask() or ''

    if not path:
        print_error('Path nao informado')
        raise typer.Exit(1)

    result = service.add_path(path, sc, desc)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def remove(
    path: str = typer.Argument(..., help='Caminho para remover'),
    scope: str = typer.Option('user', '--scope', '-s', help='Escopo: user|system'),
    force: bool = typer.Option(False, '--force', '-f', help='Nao confirma'),
    interactive: bool = typer.Option(False, '--interactive', '-i', help='Modo interativo'),
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
            print_warning('Nenhum path ativo para remover')
            raise typer.Exit()
        choices = [f'{e.path}' for e in entries]
        selected = questionary.select('Selecione o path para remover:', choices=choices).ask()
        if not selected:
            raise typer.Exit()
        path = selected

    if not force and settings.confirm_destructive:
        if not Confirm.ask(f'[warning]Remover [path]{path}[/] do [scope.{sc.value}]{sc.label}[/]?'):
            print_info('Cancelado')
            raise typer.Exit()

    result = service.remove_path(path, sc)

    if result.success:
        print_success(result.message)
    else:
        print_error(result.message)
        raise typer.Exit(1)


@app.command()
def validate(
    scope: str = typer.Option('both', '--scope', '-s', help='Escopo: user|system|both'),
    fix: bool = typer.Option(False, '--fix', help='Remove entradas invalidas automaticamente'),
):
    """Valida paths (existe no disco, duplicados, etc)"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == 'both' else [Scope(scope)]

    for sc in scopes:
        result = service.validate_paths(sc)
        _render_validation(result, sc)

        if fix and (result.missing or result.duplicates or result.invalid):
            if Confirm.ask(
                f'Remover {len(result.missing)} ausentes + {len(result.duplicates)} duplicados + {len(result.invalid)} invalidos?'
            ):
                for p in result.missing + result.duplicates + result.invalid:
                    service.remove_path(p, sc)
                print_success('Limpeza concluida')


@app.command()
def sync(
    scope: str = typer.Option('both', '--scope', '-s', help='Escopo: user|system|both'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Apenas mostra o que faria'),
):
    """Sincroniza DB com PATH real do Windows"""
    service = PathService()

    scopes = [Scope.USER, Scope.SYSTEM] if scope == 'both' else [Scope(scope)]

    for sc in scopes:
        if require_admin(sc) and not dry_run:
            print_error("Escopo 'system' requer admin para sincronizar")
            continue

        result = service.sync_from_system(sc)
        _render_sync(result, sc)

        if not dry_run and result.drift_detected:
            print_success(f'Sincronizado: +{len(result.added)} -{len(result.removed)}')


@app.command()
def backup(
    name: str = typer.Argument(..., help='Nome do backup'),
    scope: str = typer.Option('user', '--scope', '-s', help='Escopo: user|system'),
    desc: str = typer.Option('', '--desc', '-d', help='Descricao'),
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
    backup_id: int = typer.Argument(..., help='ID do backup'),
    scope: str = typer.Option(None, '--scope', '-s', help='Forcar escopo (padrao: do backup)'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Simula sem aplicar'),
):
    """Restaura backup do PATH"""
    from .repositories import BackupRepository, PathEntryRepository
    from .windows_api import WindowsPathAPI

    backup = BackupRepository().get_by_id(backup_id)
    if not backup:
        print_error(f'Backup {backup_id} nao encontrado')
        raise typer.Exit(1)

    sc = Scope(scope) if scope else backup.scope

    if require_admin(sc):
        print_error("Escopo 'system' requer admin")
        raise typer.Exit(1)

    if dry_run:
        print_info(f'[DRY-RUN] Restauraria {len(backup.path_snapshot)} paths no {sc.label}')
        for p in backup.path_snapshot:
            console.print(f'  [dim]->[/] {p}')
        raise typer.Exit()

    if settings.confirm_destructive:
        if not Confirm.ask(
            f"[warning]Restaurar backup '[bold]{backup.name}[/]' ({len(backup.path_snapshot)} paths) no {sc.label}?"
        ):
            print_info('Cancelado')
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


@app.command()
def history(
    limit: int = typer.Option(20, '--limit', '-n', help='Numero de entradas'),
    scope: str = typer.Option(None, '--scope', '-s', help='Filtrar por escopo'),
):
    """Historico de operacoes"""
    from .models import OperationStatus
    from .repositories import OperationLogRepository

    logs = OperationLogRepository().get_recent(limit)

    if scope:
        logs = [l for l in logs if l.scope and l.scope.value == scope]

    table = Table(title='Historico de Operacoes', show_header=True, header_style='bold cyan')
    table.add_column('Quando', style='dim', width=16)
    table.add_column('Op', width=10)
    table.add_column('Escopo', width=10)
    table.add_column('Path', overflow='fold')
    table.add_column('Status', justify='center')

    for log in logs:
        status_color = {
            OperationStatus.SUCCESS: 'green',
            OperationStatus.FAILED: 'red',
            OperationStatus.PARTIAL: 'yellow',
        }.get(log.status, 'white')

        scope_label = log.scope.label if log.scope else '-'
        table.add_row(
            log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else '-',
            log.operation.value.upper(),
            scope_label,
            log.target_path or '-',
            f'[{status_color}]{log.status.value}[/]',
        )

    console.print(table)


@app.command()
def interactive():
    """Modo interativo (menu)"""
    _interactive_menu()


# ==================== RENDERERS ====================


def _render_entries(entries, scope: Scope, format: str):
    if format == 'json':
        import json

        console.print_json(
            json.dumps(
                [{'path': e.path, 'active': e.active, 'desc': e.description} for e in entries]
            )
        )
        return

    if format == 'tree':
        scope_icon = '[USER]' if scope == Scope.USER else '[SYS]'
        tree = Tree(f'{scope_icon} [bold]{scope.label}[/] ({len(entries)} paths)')
        for e in entries:
            status = '[+]' if e.active else '[-]'
            tree.add(
                f'{status} [path]{e.path}[/] [dim]({e.description})[/]'
                if e.description
                else f'{status} [path]{e.path}[/]'
            )
        console.print(tree)
        return

    # Table (default)
    scope_icon = '[USER]' if scope == Scope.USER else '[SYS]'
    table = Table(
        title=f'{scope_icon} PATH - {scope.label}',
        show_header=True,
        header_style='bold cyan',
        border_style='blue',
    )
    table.add_column('#', style='dim', width=4)
    table.add_column('Path', style='green', overflow='fold', ratio=1)
    table.add_column('Status', justify='center', width=10)
    table.add_column('Pos', justify='right', width=4)
    table.add_column('Descricao', style='dim', overflow='fold')

    for idx, e in enumerate(entries, 1):
        status = '[green][+] Ativo[/]' if e.active else '[red][-] Inativo[/]'
        table.add_row(str(idx), e.path, status, str(e.position), e.description or '-')

    console.print(table)


def _render_validation(result: ValidationResult, scope: Scope):
    scope_icon = '[USER]' if scope == Scope.USER else '[SYS]'
    console.print(
        Panel.fit(
            f'[bold]{scope_icon} {scope.label}[/]\n{result.summary}',
            title='[+] Validacao',
            border_style='green' if result.is_valid else 'yellow',
        )
    )

    if result.missing:
        console.print('[red][-] Ausentes no disco:[/]')
        for p in result.missing:
            console.print(f'  [dim]->[/] {p}')

    if result.duplicates:
        console.print('[yellow][~] Duplicados:[/]')
        for p in result.duplicates:
            console.print(f'  [dim]->[/] {p}')

    if result.invalid:
        console.print('[red][!] Invalidos:[/]')
        for p in result.invalid:
            console.print(f'  [dim]->[/] {p}')


def _render_sync(result: SyncResult, scope: Scope):
    scope_icon = '[USER]' if scope == Scope.USER else '[SYS]'
    console.print(
        Panel.fit(
            f'[bold]{scope_icon} {scope.label}[/]\n'
            f'[+] Adicionados: [green]{len(result.added)}[/]\n'
            f'[-] Removidos: [red]{len(result.removed)}[/]\n'
            f'[=] Inalterados: [dim]{len(result.unchanged)}[/]\n'
            f'Drift: {"[red]SIM[/]" if result.drift_detected else "[green]NAO[/]"}',
            title='[~] Sync',
            border_style='blue',
        )
    )

    if result.added:
        console.print('[green]Novos no Windows:[/]')
        for p in result.added:
            console.print(f'  [dim]+[/] {p}')

    if result.removed:
        console.print('[red]Removidos do Windows:[/]')
        for p in result.removed:
            console.print(f'  [dim]-[/] {p}')


# ==================== MENU INTERATIVO ====================


def _interactive_menu():
    service = PathService()

    while True:
        console.print()
        console.print(
            Panel.fit(
                '[bold cyan]PathPilot[/] - Menu Interativo',
                border_style='cyan',
            )
        )

        action = questionary.select(
            'O que deseja fazer?',
            choices=[
                'Listar paths (user)',
                'Listar paths (system)',
                'Adicionar path',
                'Remover path',
                'Validar paths',
                'Sincronizar com Windows',
                'Criar backup',
                'Restaurar backup',
                'Ver historico',
                'Sair',
            ],
            style=questionary.Style(
                [
                    ('selected', 'fg:#00d7ff bold'),
                    ('pointer', 'fg:#ff6b6b bold'),
                    ('highlighted', 'fg:#00d7ff'),
                    ('question', 'bold'),
                ]
            ),
        ).ask()

        if not action or action == 'Sair':
            print_success('Ate mais!')
            break

        try:
            if 'Listar paths (user)' in action:
                _render_entries(service.list_paths(Scope.USER), Scope.USER, 'table')
            elif 'Listar paths (system)' in action:
                _render_entries(service.list_paths(Scope.SYSTEM), Scope.SYSTEM, 'table')
            elif 'Adicionar' in action:
                path = questionary.path('Caminho:').ask()
                if path:
                    scope = Scope(questionary.select('Escopo:', choices=['user', 'system']).ask())
                    desc = questionary.text('Descricao (opcional):').ask() or ''
                    result = service.add_path(path, scope, desc)
                    print_success(result.message) if result.success else print_error(result.message)
            elif 'Remover' in action:
                scope = Scope(questionary.select('Escopo:', choices=['user', 'system']).ask())
                entries = service.list_paths(scope, active_only=True)
                if not entries:
                    print_warning('Nenhum path ativo')
                    continue
                choices = [f'{e.path}' for e in entries]
                selected = questionary.select('Path para remover:', choices=choices).ask()
                if selected and Confirm.ask(f'Remover {selected}?'):
                    result = service.remove_path(selected, scope)
                    print_success(result.message) if result.success else print_error(result.message)
            elif 'Validar' in action:
                scope = Scope(
                    questionary.select('Escopo:', choices=['user', 'system', 'both']).ask()
                )
                sc = [Scope.USER, Scope.SYSTEM] if scope == 'both' else [scope]
                for s in sc:
                    _render_validation(service.validate_paths(s), s)
            elif 'Sincronizar' in action:
                scope = Scope(
                    questionary.select('Escopo:', choices=['user', 'system', 'both']).ask()
                )
                sc = [Scope.USER, Scope.SYSTEM] if scope == 'both' else [scope]
                for s in sc:
                    _render_sync(service.sync_from_system(s), s)
            elif 'Criar backup' in action:
                name = questionary.text('Nome do backup:').ask()
                scope = Scope(questionary.select('Escopo:', choices=['user', 'system']).ask())
                desc = questionary.text('Descricao (opcional):').ask() or ''
                from .models import Backup
                from .repositories import BackupRepository
                from .windows_api import WindowsPathAPI

                paths = WindowsPathAPI().get_path(scope)
                BackupRepository().create(
                    Backup(name=name, scope=scope, path_snapshot=paths, description=desc)
                )
                print_success(f"Backup '{name}' criado")
            elif 'Restaurar backup' in action:
                from .repositories import BackupRepository

                backups = BackupRepository().list_all(limit=20)
                if not backups:
                    print_warning('Nenhum backup')
                    continue
                choices = [
                    f'{b.id}: {b.name} ({b.scope.label}) - {len(b.path_snapshot)} paths'
                    for b in backups
                ]
                selected = questionary.select('Backup:', choices=choices).ask()
                if selected:
                    bid = int(selected.split(':')[0])
                    if Confirm.ask('Confirmar restauracao?'):
                        print_info('Use: pathpilot restore <id>')
            elif 'Historico' in action:
                from .repositories import OperationLogRepository

                logs = OperationLogRepository().get_recent(20)
                _render_history(logs)

        except KeyboardInterrupt:
            print_info('Cancelado')
        except Exception as e:
            print_error(f'Erro: {e}')


def _render_history(logs):
    from .models import OperationStatus

    table = Table(title='Historico Recente', show_header=True, header_style='bold cyan')
    table.add_column('Quando', style='dim', width=16)
    table.add_column('Op', width=10)
    table.add_column('Escopo', width=10)
    table.add_column('Path', overflow='fold')
    table.add_column('Status', justify='center')

    for log in logs:
        status_color = {
            OperationStatus.SUCCESS: 'green',
            OperationStatus.FAILED: 'red',
            OperationStatus.PARTIAL: 'yellow',
        }.get(log.status, 'white')

        scope_label = log.scope.label if log.scope else '-'
        table.add_row(
            log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else '-',
            log.operation.value.upper(),
            scope_label,
            log.target_path or '-',
            f'[{status_color}]{log.status.value}[/]',
        )
    console.print(table)


if __name__ == '__main__':
    app()
