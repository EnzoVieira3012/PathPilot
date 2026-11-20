"""Tests for PathPilot utils module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pathpilot.utils import (
    normalize_path,
    is_valid_path,
    path_exists,
    expand_path,
    sanitize_path,
    safe_join,
    validate_env_var_name,
    validate_env_var_value,
    broadcast_environment_change,
    split_path,
    join_path,
    confirm_action,
)


class TestNormalizePath:
    """Test normalize_path function."""

    def test_normalizes_windows_path(self):
        assert normalize_path(r"C:\Windows\System32") == r"C:\Windows\System32"
        assert normalize_path(r"C:\\Windows\\System32") == r"C:\Windows\System32"

    def test_removes_trailing_slash(self):
        assert normalize_path(r"C:\Test\\") == r"C:\Test"
        assert normalize_path(r"C:\Test/") == r"C:\Test"

    def test_handles_forward_slashes(self):
        assert normalize_path("C:/Test/Path") == r"C:\Test\Path"

    def test_case_preservation(self):
        assert normalize_path(r"c:\windows") == r"c:\windows"

    def test_empty_string(self):
        assert normalize_path("") == ""

    def test_unc_paths(self):
        assert normalize_path(r"\\Server\Share\Path") == r"\\Server\Share\Path"


class TestIsValidPath:
    """Test is_valid_path function."""

    def test_valid_absolute_paths(self):
        assert is_valid_path(r"C:\Windows") is True
        assert is_valid_path(r"D:\Program Files\App") is True
        assert is_valid_path(r"\\Server\Share") is True

    def test_valid_with_env_vars(self):
        assert is_valid_path(r"%USERPROFILE%\AppData") is True
        assert is_valid_path(r"$HOME/bin") is True

    def test_invalid_relative(self):
        assert is_valid_path(r".\relative") is False
        assert is_valid_path(r"..\parent") is False

    def test_invalid_empty(self):
        assert is_valid_path("") is False
        assert is_valid_path("   ") is False

    def test_invalid_chars(self):
        assert is_valid_path(r"C:\Test<invalid>") is False
        assert is_valid_path(r"C:\Test|pipe") is False


class TestPathExists:
    """Test path_exists function."""

    def test_existing_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert path_exists(tmpdir) is True

    def test_nonexistent_path(self):
        assert path_exists(r"C:\Nonexistent\Path\12345") is False

    def test_empty_path(self):
        assert path_exists("") is False


class TestExpandPath:
    """Test expand_path function."""

    def test_expands_userprofile(self):
        with patch.dict(os.environ, {"USERPROFILE": r"C:\Users\TestUser"}):
            result = expand_path(r"%USERPROFILE%\Documents")
            assert result == r"C:\Users\TestUser\Documents"

    def test_expands_system_vars(self):
        with patch.dict(os.environ, {"SYSTEMROOT": r"C:\Windows"}):
            result = expand_path(r"%SYSTEMROOT%\System32")
            assert result == r"C:\Windows\System32"

    def test_no_expansion_needed(self):
        result = expand_path(r"C:\Plain\Path")
        assert result == r"C:\Plain\Path"

    def test_missing_var_unchanged(self):
        result = expand_path(r"%NONEXISTENT_VAR%\Path")
        assert result == r"%NONEXISTENT_VAR%\Path"


class TestSanitizePath:
    """Test sanitize_path function."""

    def test_removes_traversal(self):
        result = sanitize_path(r"C:\Test\..\..\Windows")
        assert ".." not in result

    def test_removes_null_bytes(self):
        result = sanitize_path(r"C:\Test\x00.exe")
        assert "\x00" not in result

    def test_normalizes_slashes(self):
        result = sanitize_path(r"C:/Test//Path\\")
        assert result == r"C:\Test\Path"

    def test_empty_input(self):
        result = sanitize_path("")
        assert result == ""


class TestSafeJoin:
    """Test safe_join function."""

    def test_joins_paths(self):
        result = safe_join(r"C:\Base", "subdir", "file.txt")
        assert result == r"C:\Base\subdir\file.txt"

    def test_prevents_traversal(self):
        result = safe_join(r"C:\Base", r"..\..\Windows\System32")
        assert result.startswith(r"C:\Base")

    def test_absolute_second_path_rejected(self):
        result = safe_join(r"C:\Base", r"D:\Other")
        assert result == r"C:\Base"


class TestValidateEnvVarName:
    """Test validate_env_var_name function."""

    def test_valid_names(self):
        assert validate_env_var_name("VALID_NAME") is True
        assert validate_env_var_name("VAR123") is True
        assert validate_env_var_name("_PRIVATE") is True
        assert validate_env_var_name("PATH") is True

    def test_invalid_names(self):
        assert validate_env_var_name("") is False
        assert validate_env_var_name("123INVALID") is False
        assert validate_env_var_name("INVALID-NAME") is False
        assert validate_env_var_name("INVALID NAME") is False
        assert validate_env_var_name("INVALID.NAME") is False


class TestValidateEnvVarValue:
    """Test validate_env_var_value function."""

    def test_valid_values(self):
        assert validate_env_var_value("simple") is True
        assert validate_env_var_value("value with spaces") is True
        assert validate_env_var_value(r"C:\Path\With\Backslashes") is True
        assert validate_env_var_value("") is True

    def test_invalid_values(self):
        assert validate_env_var_value("value\x00null") is False
        assert validate_env_var_value("value\nnewline") is False





class TestBroadcastEnvironmentChange:
    """Test broadcast_environment_change function."""

    def test_returns_none_on_non_windows(self):
        with patch("sys.platform", "linux"):
            result = broadcast_environment_change()
            assert result is None

    def test_calls_windows_api_on_windows(self):
        with patch("sys.platform", "win32"):
            with patch("pathpilot.utils.ctypes") as mock_ctypes:
                result = broadcast_environment_change()
                assert mock_ctypes.windll.user32.SendMessageTimeoutW.called


class TestSplitPath:
    """Test split_path function."""

    def test_splits_semicolon(self):
        result = split_path(r"C:\A;C:\B;C:\C")
        assert result == [r"C:\A", r"C:\B", r"C:\C"]

    def test_handles_empty(self):
        result = split_path("")
        assert result == []

    def test_handles_trailing_semicolon(self):
        result = split_path(r"C:\A;")
        assert result == [r"C:\A"]


class TestJoinPath:
    """Test join_path function."""

    def test_joins_with_semicolon(self):
        result = join_path([r"C:\A", r"C:\B"])
        assert result == r"C:\A;C:\B"

    def test_empty_list(self):
        result = join_path([])
        assert result == ""


class TestConfirmAction:
    """Test confirm_action function."""

    def test_returns_true_for_y(self):
        with patch("builtins.input", return_value="y"):
            result = confirm_action("Continue?")
            assert result is True

    def test_returns_true_for_yes(self):
        with patch("builtins.input", return_value="yes"):
            result = confirm_action("Continue?")
            assert result is True

    def test_returns_false_for_n(self):
        with patch("builtins.input", return_value="n"):
            result = confirm_action("Continue?")
            assert result is False

    def test_returns_false_for_empty(self):
        with patch("builtins.input", return_value=""):
            result = confirm_action("Continue?")
            assert result is False