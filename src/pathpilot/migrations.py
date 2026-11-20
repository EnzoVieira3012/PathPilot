"""Sistema de migracoes versionadas do banco de dados."""

import os
from collections.abc import Callable
from dataclasses import dataclass

from .db import SCHEMA_VERSION, get_db
from .utils import print_error, print_info, print_success, print_warning


@dataclass
class Migration:
    version: int
    description: str
    up: Callable
    down: Callable = None


MIGRATIONS: list[Migration] = []


def migration(version: int, description: str):
    """Decorator para registrar migracao."""

    def decorator(func):
        MIGRATIONS.append(Migration(version=version, description=description, up=func))
        return func

    return decorator


@migration(1, 'Schema inicial: env_vars, path_entries, backups, operation_log')
def v1_initial_schema(db):
    """Ja executada pelo init_db() - placeholder."""
    pass


@migration(2, 'Adiciona coluna checksum nos backups')
def v2_backup_checksum(db):
    with db.transaction() as conn:
        row = conn.execute('PRAGMA table_info(backups)').fetchall()
        cols = [r['name'] for r in row]
        if 'checksum' not in cols:
            conn.execute('ALTER TABLE backups ADD COLUMN checksum TEXT')


@migration(3, 'Adiciona indices compostos para performance')
def v3_composite_indexes(db):
    with db.transaction() as conn:
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_path_entries_scope_active_pos ON path_entries(scope, active, position)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_op_log_op_scope_created ON operation_log(operation, scope, created_at DESC)'
        )


@migration(4, 'Adiciona tabela de configuracoes do usuario')
def v4_user_settings(db):
    with db.transaction() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


@migration(5, 'Seed: paths padrao do Windows')
def v5_seed_default_paths(db):
    from .models import PathEntry, Scope
    from .repositories import PathEntryRepository
    from .windows_api import WindowsPathAPI

    repo = PathEntryRepository()
    win_api = WindowsPathAPI()

    default_user_paths = [
        r'%USERPROFILE%\AppData\Local\Microsoft\WindowsApps',
        r'%USERPROFILE%\.local\bin',
        r'%USERPROFILE%\bin',
        r'%LOCALAPPDATA%\Programs',
    ]

    default_system_paths = [
        r'C:\Windows',
        r'C:\Windows\System32',
        r'C:\Windows\System32\Wbem',
        r'C:\Windows\System32\WindowsPowerShell\v1.0',
    ]

    for scope, paths in [(Scope.USER, default_user_paths), (Scope.SYSTEM, default_system_paths)]:
        try:
            existing = {normalize_path(p.path) for p in repo.get_all(scope, active_only=False)}
            for idx, path in enumerate(paths):
                norm = normalize_path(path)
                if norm not in existing:
                    entry = PathEntry(
                        path=norm,
                        scope=scope,
                        active=True,
                        position=len(existing) + idx,
                        description=f'Seed: path padrao {scope.value}',
                    )
                    repo.create(entry)
                    print_info(f'Seed: {scope.value} -> {norm}')
        except Exception as e:
            print_warning(f'Seed {scope.value} falhou: {e}')


def normalize_path(path: str) -> str:
    return os.path.normpath(os.path.expandvars(path.strip()))


def get_current_version() -> int:
    db = get_db()
    row = db.fetchone('SELECT version FROM schema_version')
    return row['version'] if row else 0


def get_pending_migrations() -> list[Migration]:
    current = get_current_version()
    return [m for m in MIGRATIONS if m.version > current]


def run_migrations(target_version: int = None) -> bool:
    """Executa migracoes pendentes."""
    db = get_db()
    pending = get_pending_migrations()

    if target_version:
        pending = [m for m in pending if m.version <= target_version]

    if not pending:
        print_info('Nenhuma migracao pendente')
        return True

    print_info(f'Executando {len(pending)} migracao(oes)...')

    for mig in pending:
        try:
            print_info(f'  v{mig.version}: {mig.description}')
            mig.up(db)
            with db.transaction() as conn:
                conn.execute('UPDATE schema_version SET version = ?', (mig.version,))
            print_success(f'  v{mig.version} OK')
        except Exception as e:
            print_error(f'  v{mig.version} FALHOU: {e}')
            return False

    print_success('Todas migracoes executadas com sucesso')
    return True


def rollback_migration(version: int) -> bool:
    """Rollback de uma migracao especifica (se tiver down)."""
    db = get_db()
    mig = next((m for m in MIGRATIONS if m.version == version), None)

    if not mig:
        print_error(f'Migracao v{version} nao encontrada')
        return False

    if not mig.down:
        print_error(f'Migracao v{version} nao tem rollback (down)')
        return False

    try:
        print_info(f'Rollback v{version}: {mig.description}')
        mig.down(db)
        with db.transaction() as conn:
            conn.execute('UPDATE schema_version SET version = ?', (version - 1,))
        print_success(f'Rollback v{version} OK')
        return True
    except Exception as e:
        print_error(f'Rollback v{version} FALHOU: {e}')
        return False


def migration_status() -> dict:
    """Retorna status das migracoes."""
    current = get_current_version()
    pending = get_pending_migrations()

    return {
        'current_version': current,
        'target_version': SCHEMA_VERSION,
        'pending_count': len(pending),
        'pending': [{'version': m.version, 'description': m.description} for m in pending],
        'applied': [
            {'version': m.version, 'description': m.description}
            for m in MIGRATIONS
            if m.version <= current
        ],
    }
