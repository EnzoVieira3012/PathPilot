"""Tests for PathPilot windows_api module."""

import pytest
from unittest.mock import patch, MagicMock
from pathpilot.windows_api import WindowsPathAPI


class TestWindowsPathAPI:
    """Test WindowsPathAPI class."""

    def test_get_path_user(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.QueryValueEx", return_value=("C:\\A;C:\\B", 0)):
                with patch("winreg.CloseKey"):
                    result = api.get_path("user")
                    assert result == [r"C:\A", r"C:\B"]

    def test_get_path_system(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.QueryValueEx", return_value=("C:\\Sys1;C:\\Sys2", 0)):
                with patch("winreg.CloseKey"):
                    result = api.get_path("system")
                    assert result == [r"C:\Sys1", r"C:\Sys2"]

    def test_get_path_empty(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.QueryValueEx", return_value=("", 0)):
                with patch("winreg.CloseKey"):
                    result = api.get_path("user")
                    assert result == []

    def test_get_path_key_not_found(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            result = api.get_path("user")
            assert result == []

    def test_set_path_user(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.SetValueEx") as mock_set:
                with patch("winreg.CloseKey"):
                    api.set_path([r"C:\A", r"C:\B"], "user")
                    mock_set.assert_called_once()
                    call_args = mock_set.call_args
                    assert "C:\\A;C:\\B" in str(call_args)

    def test_set_path_system(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.SetValueEx") as mock_set:
                with patch("winreg.CloseKey"):
                    api.set_path([r"C:\Sys"], "system")
                    mock_set.assert_called_once()

    def test_add_to_path_user(self):
        api = WindowsPathAPI()
        with patch.object(api, 'get_path', return_value=[r"C:\Existing"]):
            with patch.object(api, 'set_path') as mock_set:
                result = api.add_to_path(r"C:\New", "user")
                assert result is True
                mock_set.assert_called_once()
                args = mock_set.call_args[0]
                assert r"C:\Existing" in args[0]
                assert r"C:\New" in args[0]

    def test_add_to_path_already_exists(self):
        api = WindowsPathAPI()
        with patch.object(api, 'get_path', return_value=[r"C:\Existing"]):
            result = api.add_to_path(r"C:\Existing", "user")
            assert result is False

    def test_remove_from_path_user(self):
        api = WindowsPathAPI()
        with patch.object(api, 'get_path', return_value=[r"C:\A", r"C:\B", r"C:\C"]):
            with patch.object(api, 'set_path') as mock_set:
                result = api.remove_from_path(r"C:\B", "user")
                assert result is True
                mock_set.assert_called_once()
                args = mock_set.call_args[0]
                assert r"C:\A" in args[0]
                assert r"C:\C" in args[0]
                assert r"C:\B" not in args[0]

    def test_remove_from_path_not_found(self):
        api = WindowsPathAPI()
        with patch.object(api, 'get_path', return_value=[r"C:\A", r"C:\C"]):
            result = api.remove_from_path(r"C:\B", "user")
            assert result is False

    def test_reorder_path(self):
        api = WindowsPathAPI()
        with patch.object(api, 'get_path', return_value=[r"C:\A", r"C:\B", r"C:\C"]):
            with patch.object(api, 'set_path') as mock_set:
                result = api.reorder_path([r"C:\C", r"C:\A", r"C:\B"], "user")
                assert result is True
                mock_set.assert_called_once()

    def test_broadcast_change(self):
        api = WindowsPathAPI()
        with patch("ctypes.windll.user32.SendMessageTimeoutW") as mock_send:
            mock_send.return_value = 1
            result = api.broadcast_change()
            assert result is True
            mock_send.assert_called_once()


class TestWindowsPathAPIScope:
    """Test scope-specific behavior."""

    def test_user_scope_uses_hkcu(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.QueryValueEx", return_value=("", 0)):
                with patch("winreg.CloseKey"):
                    api.get_path("user")
                    # Verify HKEY_CURRENT_USER was used
                    call_args = mock_open.call_args[0]
                    assert call_args[0] == 0x80000001  # HKEY_CURRENT_USER

    def test_system_scope_uses_hklm(self):
        api = WindowsPathAPI()
        with patch("winreg.OpenKey") as mock_open:
            with patch("winreg.QueryValueEx", return_value=("", 0)):
                with patch("winreg.CloseKey"):
                    api.get_path("system")
                    # Verify HKEY_LOCAL_MACHINE was used
                    call_args = mock_open.call_args[0]
                    assert call_args[0] == 0x80000002  # HKEY_LOCAL_MACHINE

    def test_invalid_scope_raises(self):
        api = WindowsPathAPI()
        with pytest.raises(ValueError):
            api.get_path("invalid")