"""Wrapper para API do Windows Registry (PATH)."""

import winreg

from .models import Scope
from .utils import broadcast_environment_change, join_path, normalize_path, split_path


class WindowsPathAPI:
    """Acesso ao PATH do sistema/usuário via Registry."""

    USER_KEY = r'Environment'
    SYSTEM_KEY = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
    PATH_VALUE = 'Path'

    def __init__(self):
        self._user_hkey = winreg.HKEY_CURRENT_USER
        self._system_hkey = winreg.HKEY_LOCAL_MACHINE

    def _open_key(self, scope: Scope, write: bool = False):
        """Abre chave do registry."""
        if scope == Scope.USER:
            hkey = self._user_hkey
            subkey = self.USER_KEY
        else:
            hkey = self._system_hkey
            subkey = self.SYSTEM_KEY

        access = winreg.KEY_READ | (winreg.KEY_SET_VALUE if write else 0)
        return winreg.OpenKey(hkey, subkey, 0, access)

    def get_path(self, scope: Scope) -> list[str]:
        """Lê PATH do registry."""
        try:
            with self._open_key(scope) as key:
                value, _ = winreg.QueryValueEx(key, self.PATH_VALUE)
                return split_path(value)
        except FileNotFoundError:
            return []
        except Exception as e:
            raise RuntimeError(f'Erro ao ler PATH ({scope.value}): {e}')

    def set_path(self, scope: Scope, paths: list[str]) -> None:
        """Escreve PATH no registry."""
        normalized = [normalize_path(p) for p in paths]
        value = join_path(normalized)

        try:
            with self._open_key(scope, write=True) as key:
                winreg.SetValueEx(key, self.PATH_VALUE, 0, winreg.REG_EXPAND_SZ, value)
            broadcast_environment_change()
        except PermissionError:
            raise PermissionError(
                f'Sem permissão para escrever PATH do {scope.value}. Execute como admin.'
            )
        except Exception as e:
            raise RuntimeError(f'Erro ao escrever PATH ({scope.value}): {e}')

    def get_user_path(self) -> list[str]:
        return self.get_path(Scope.USER)

    def get_system_path(self) -> list[str]:
        return self.get_path(Scope.SYSTEM)

    def set_user_path(self, paths: list[str]) -> None:
        self.set_path(Scope.USER, paths)

    def set_system_path(self, paths: list[str]) -> None:
        self.set_path(Scope.SYSTEM, paths)
