"""Utilitários do PathPilot."""

import ctypes
import os
from pathlib import Path

from rich.console import Console

console = Console()


def is_admin() -> bool:
    """Verifica se está rodando como administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def require_admin(scope: str) -> bool:
    """Verifica se precisa de admin para o escopo."""
    return scope.lower() == 'system' and not is_admin()


def normalize_path(path: str) -> str:
    """Normaliza path: expande vars, resolve, remove aspas."""
    path = path.strip().strip('"').strip("'")
    path = os.path.expandvars(path)
    path = os.path.normpath(path)
    return path


def path_exists(path: str) -> bool:
    """Verifica se path existe no filesystem."""
    return Path(path).exists()


def is_valid_path(path: str) -> bool:
    """Validação básica de path."""
    if not path or not path.strip():
        return False
    try:
        Path(path)
        return True
    except Exception:
        return False


def expand_path(path: str) -> str:
    """Expande variáveis de ambiente no path."""
    return os.path.expandvars(path)


def get_path_separator() -> str:
    """Retorna separador de PATH do Windows."""
    return ';'


def split_path(path_string: str) -> list[str]:
    """Divide string PATH em lista, remove vazios e normaliza."""
    sep = get_path_separator()
    paths = [p.strip() for p in path_string.split(sep) if p.strip()]
    return [normalize_path(p) for p in paths]


def join_path(paths: list[str]) -> str:
    """Junta lista de paths em string PATH."""
    sep = get_path_separator()
    return sep.join(paths)


def broadcast_environment_change() -> None:
    """Notifica Windows sobre mudança de variáveis de ambiente."""
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            'Environment',
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )
    except Exception:
        pass


def confirm_action(message: str, default: bool = False) -> bool:
    """Confirmação interativa via Rich."""
    from rich.prompt import Confirm

    return Confirm.ask(message, default=default)


def print_success(message: str) -> None:
    console.print(f'[success][+] {message}[/]')


def print_error(message: str) -> None:
    console.print(f'[error][-] {message}[/]')


def print_warning(message: str) -> None:
    console.print(f'[warning][!] {message}[/]')


def print_info(message: str) -> None:
    console.print(f'[info][i] {message}[/]')
