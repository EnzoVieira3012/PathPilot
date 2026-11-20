"""Gerenciador de banco de dados SQLite."""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import settings
from .utils import print_info

# Versao atual do schema (deve bater com a ultima migracao)
SCHEMA_VERSION = 5

SCHEMA_SQL = """
-- Tabela de versao do schema
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Variaveis de ambiente salvas
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
    checksum TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Log de operacoes (auditoria)
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

-- Configuracoes do usuario
CREATE TABLE IF NOT EXISTS user_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_path_entries_scope_active ON path_entries(scope, active);
CREATE INDEX IF NOT EXISTS idx_path_entries_scope_active_pos ON path_entries(scope, active, position);
CREATE INDEX IF NOT EXISTS idx_backups_scope_created ON backups(scope, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_op_log_created ON operation_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_op_log_op_scope_created ON operation_log(operation, scope, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_env_vars_scope ON env_vars(scope);
"""


class Database:
    """Gerenciador de conexao SQLite com transacoes e thread-local storage."""

    _local = threading.local()

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self._conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Pega conexao thread-local."""
        if not hasattr(Database._local, 'conn') or Database._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('PRAGMA journal_mode = WAL')
            conn.execute('PRAGMA synchronous = NORMAL')
            conn.execute('PRAGMA cache_size = -2000')
            conn.execute('PRAGMA temp_store = MEMORY')
            Database._local.conn = conn
        return Database._local.conn

    def connect(self) -> sqlite3.Connection:
        """Retorna conexao (alias para compatibilidade)."""
        return self._get_connection()

    def close(self) -> None:
        """Fecha conexao da thread atual."""
        if hasattr(Database._local, 'conn') and Database._local.conn:
            Database._local.conn.close()
            Database._local.conn = None

    def close_all(self) -> None:
        """Fecha todas as conexoes (para testes)."""
        self.close()

    @contextmanager
    def transaction(self):
        """Context manager para transacoes."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._get_connection()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        conn = self._get_connection()
        return conn.executemany(sql, params_list)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def health_check(self) -> bool:
        """Verifica se banco esta acessivel."""
        try:
            self.execute('SELECT 1')
            return True
        except Exception:
            return False

    def get_stats(self) -> dict:
        """Estatisticas do banco."""
        try:
            stats = {}
            tables = ['env_vars', 'path_entries', 'backups', 'operation_log', 'user_settings']
            for table in tables:
                row = self.fetchone(f'SELECT COUNT(*) as c FROM {table}')
                stats[table] = row['c'] if row else 0
            stats['schema_version'] = self.get_schema_version()
            stats['db_size_bytes'] = self.db_path.stat().st_size if self.db_path.exists() else 0
            return stats
        except Exception as e:
            return {'error': str(e)}

    def vacuum(self) -> None:
        """VACUUM para otimizar."""
        self.execute('VACUUM')

    def get_schema_version(self) -> int:
        row = self.fetchone('SELECT version FROM schema_version')
        return row['version'] if row else 0


_db_instance: Database | None = None


def get_db() -> Database:
    """Singleton do banco."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def init_db(run_migrations: bool = True) -> None:
    """Inicializa banco: cria tabelas e roda migracoes se necessario."""
    db = get_db()
    with db.transaction() as conn:
        conn.executescript(SCHEMA_SQL)
        # Garante que schema_version existe (nao sobrescreve se ja tiver)
        row = conn.execute('SELECT version FROM schema_version').fetchone()
        if not row:
            conn.execute('INSERT INTO schema_version (version) VALUES (0)')

    # So roda migracoes se o banco for novo (versao 0)
    current = get_schema_version()
    if run_migrations and current == 0:
        from .migrations import run_migrations as _run_migrations

        _run_migrations()

    print_info(f'Banco inicializado em: {settings.db_path} (v{SCHEMA_VERSION})')


def get_schema_version() -> int:
    return get_db().get_schema_version()


def migrate() -> None:
    """Executa migracoes pendentes."""
    from .migrations import run_migrations

    run_migrations()


def migration_status() -> dict:
    from .migrations import migration_status as _status

    return _status()
