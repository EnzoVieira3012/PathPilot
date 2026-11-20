"""Modelos de dados do PathPilot."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Scope(str, Enum):
    USER = 'user'
    SYSTEM = 'system'

    @property
    def label(self) -> str:
        return '[USER] Usuario' if self == Scope.USER else '[SYS] Sistema'

    @property
    def emoji(self) -> str:
        return '[USER]' if self == Scope.USER else '[SYS]'


class OperationStatus(str, Enum):
    SUCCESS = 'success'
    FAILED = 'failed'
    PARTIAL = 'partial'


class OperationType(str, Enum):
    ADD = 'add'
    REMOVE = 'remove'
    BACKUP = 'backup'
    RESTORE = 'restore'
    VALIDATE = 'validate'
    SYNC = 'sync'
    REORDER = 'reorder'


@dataclass
class PathEntry:
    id: int | None = None
    path: str = ''
    scope: Scope = Scope.USER
    active: bool = True
    position: int = 0
    description: str = ''
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator('path', mode='before')
    @classmethod
    def normalize_path(cls, v: str) -> str:
        import os

        return os.path.normpath(os.path.expandvars(v.strip()))


@dataclass
class EnvVar:
    id: int | None = None
    name: str = ''
    value: str = ''
    scope: Scope = Scope.USER
    description: str = ''
    encrypted: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Backup:
    id: int | None = None
    name: str = ''
    scope: Scope = Scope.USER
    path_snapshot: list[str] = None
    description: str = ''
    created_at: datetime | None = None

    def __post_init__(self):
        if self.path_snapshot is None:
            self.path_snapshot = []


@dataclass
class OperationLog:
    id: int | None = None
    operation: OperationType = OperationType.ADD
    scope: Scope | None = None
    target_path: str = ''
    status: OperationStatus = OperationStatus.SUCCESS
    error_message: str = ''
    metadata: dict = None
    created_at: datetime | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ValidationResult(BaseModel):
    valid: list[str] = Field(default_factory=list)
    invalid: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    duplicates: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.invalid) == 0 and len(self.missing) == 0

    @property
    def summary(self) -> str:
        return f'[+] {len(self.valid)} validos | [-] {len(self.invalid)} invalidos | [!] {len(self.missing)} ausentes | [~] {len(self.duplicates)} duplicados'


class SyncResult(BaseModel):
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    drift_detected: bool = False
