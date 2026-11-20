"""Configuração do PathPilot via pydantic-settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Database
    db_path: Path = Field(default=Path.home() / '.pathpilot' / 'pathpilot.db')

    # Encryption
    fernet_key: str = Field(default='')

    # Defaults
    default_scope: str = Field(default='user')
    auto_backup: bool = Field(default=True)
    confirm_destructive: bool = Field(default=True)

    # UI
    theme: str = Field(default='default')
    show_progress: bool = Field(default=True)
    use_emoji: bool = Field(default=True)


settings = Settings()
