"""Tests for PathPilot config module."""

import os
from pathlib import Path

import pytest

from pathpilot.config import settings


class TestSettings:
    """Test Settings model."""

    def test_singleton_settings(self):
        assert settings is not None
        assert settings.db_path is not None
        assert isinstance(settings.db_path, Path)

    def test_settings_attributes_exist(self):
        assert hasattr(settings, 'db_path')
        assert hasattr(settings, 'fernet_key')
        assert hasattr(settings, 'default_scope')
        assert hasattr(settings, 'auto_backup')
        assert hasattr(settings, 'confirm_destructive')
        assert hasattr(settings, 'theme')
        assert hasattr(settings, 'show_progress')
        assert hasattr(settings, 'use_emoji')

    def test_db_path_is_path_object(self):
        assert isinstance(settings.db_path, Path)

    def test_fernet_key_is_string(self):
        assert isinstance(settings.fernet_key, str)

    def test_default_scope_is_string(self):
        assert isinstance(settings.default_scope, str)
        assert settings.default_scope in ("user", "system")

    def test_auto_backup_is_bool(self):
        assert isinstance(settings.auto_backup, bool)

    def test_theme_is_string(self):
        assert isinstance(settings.theme, str)
        assert settings.theme in ("default", "dark", "light")