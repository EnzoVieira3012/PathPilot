"""Pytest fixtures and configuration for PathPilot tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all module-level singletons before each test."""
    import pathpilot.db as db_module
    import pathpilot.repositories as repo_module
    import pathpilot.core as core_module
    import pathpilot.crypto as crypto_module
    import pathpilot.config as config_module
    import pathpilot.migrations as migrations_module

    db_module._db_instance = None
    repo_module._path_entry_repo = None
    repo_module._env_var_repo = None
    repo_module._backup_repo = None
    repo_module._operation_log_repo = None
    repo_module._user_settings_repo = None
    crypto_module._crypto_service = None
    migrations_module._migration_status = None
    
    yield
    
    # Cleanup after test
    db_module._db_instance = None
    repo_module._path_entry_repo = None
    repo_module._env_var_repo = None
    repo_module._backup_repo = None
    repo_module._operation_log_repo = None
    repo_module._user_settings_repo = None
    crypto_module._crypto_service = None
    migrations_module._migration_status = None


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Close any open connections first
    import pathpilot.db as db_module
    if db_module._db_instance:
        db_module._db_instance.close()
        db_module._db_instance = None
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass
    wal_path = db_path.with_suffix(".db-wal")
    if wal_path.exists():
        try:
            wal_path.unlink()
        except PermissionError:
            pass
    shm_path = db_path.with_suffix(".db-shm")
    if shm_path.exists():
        try:
            shm_path.unlink()
        except PermissionError:
            pass


@pytest.fixture
def mock_db(temp_db_path, reset_singletons):
    """Create a fresh database instance for each test."""
    import pathpilot.config as config_module
    import pathpilot.db as db_module
    import pathpilot.core as core_module
    import pathpilot.crypto as crypto_module
    
    # Create a test settings object with the temp db
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class TestSettings(BaseSettings):
        model_config = SettingsConfigDict(env_file=None, case_sensitive=False)
        db_path: Path = temp_db_path
        fernet_key: str = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw="
        hmac_key: str = "test-hmac-key-for-testing-purposes-only-32chars"
        default_scope: str = "user"
        auto_backup: bool = False
        confirm_destructive: bool = True
        theme: str = "default"
        show_progress: bool = True
        use_emoji: bool = True
    
    test_settings = TestSettings()
    
    # Patch the settings in all modules that import it
    original_settings = config_module.settings
    config_module.settings = test_settings
    
    original_db_settings = db_module.settings
    db_module.settings = test_settings
    
    original_core_settings = core_module.settings
    core_module.settings = test_settings
    
    original_crypto_settings = crypto_module.settings
    crypto_module.settings = test_settings
    
    from pathpilot.db import init_db, get_db
    init_db(run_migrations=True)
    db = get_db()
    # Add path attribute for CLI tests
    db.path = temp_db_path
    yield db
    
    # Restore original settings
    config_module.settings = original_settings
    db_module.settings = original_db_settings
    core_module.settings = original_core_settings
    crypto_module.settings = original_crypto_settings


@pytest.fixture
def sample_paths():
    """Sample paths for testing."""
    return [
        r"C:\Windows\System32",
        r"C:\Python311",
        r"C:\Program Files\Git\bin",
        r"%USERPROFILE%\AppData\Local\Microsoft\WindowsApps",
    ]


@pytest.fixture
def sample_env_vars():
    """Sample environment variables for testing."""
    return [
        {"name": "TEST_VAR1", "value": "test_value_1", "scope": "user", "encrypted": False},
        {"name": "TEST_VAR2", "value": "secret_value", "scope": "user", "encrypted": True},
        {"name": "SYSTEM_VAR", "value": "system_value", "scope": "system", "encrypted": False},
    ]