"""Gerenciador de banco de dados SQLite."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings
from .utils import print_info

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Tabela de versão do schema
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Variáveis de ambiente salvas
CREATE TABLE IF NOT EXISTS env_vars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('user', 'system')),
    description TEXT,
    encrypted BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Entradas do PATH gerenciadas
CREATE TABLE IF NOT EXISTS path_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('user', 'system')),
    active BOOLEAN DEFAULT 1,
    position INTEGER,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(path, scope)
);

-- Backups (snapshots do PATH)
CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    scope VARCHAR(10) NOT NULL CHECK (scope IN ('user', 'system')),
    path_snapshot TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Log de operações (auditoria)
CREATE TABLE IF NOT EXISTS operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation VARCHAR(50) NOT NULL,
    scope VARCHAR(10),
    target_path TEXT,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'partial')),
    error_message TEXT,
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_path_entries_scope_active ON path_entries(scope, active);
CREATE INDEX IF NOT EXISTS idx_backups_scope_created ON backups(scope, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_op_log_created ON operation_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_env_vars_scope ON env_vars(scope);
"""


class Database:
    """Gerenciador de conexão SQLite com transações."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Cria conexão com row_factory."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute('PRAGMA foreign_keys = ON')
            self._conn.execute('PRAGMA journal_mode = WAL')
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self):
        """Context manager para transações."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self.connect()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        conn = self.connect()
        return conn.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()


_db_instance: Database | None = None


def get_db() -> Database:
    """Singleton do banco."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def init_db() -> None:
    """Inicializa banco: cria tabelas e define versão."""
    db = get_db()
    with db.transaction() as conn:
        conn.executescript(SCHEMA_SQL)
        # Define versão do schema
        conn.execute(
            'INSERT OR REPLACE INTO schema_version (version) VALUES (?)', (SCHEMA_VERSION,)
        )
    print_info(f'Banco inicializado em: {settings.db_path}')


def get_schema_version() -> int:
    db = get_db()
    row = db.fetchone('SELECT version FROM schema_version')
    return row['version'] if row else 0


def migrate() -> None:
    """Migrações futuras (placeholder)."""
    current = get_schema_version()
    if current < SCHEMA_VERSION:
        init_db()
