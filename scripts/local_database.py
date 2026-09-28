"""Private native PostgreSQL cluster, scoped to a dedicated directory."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

MIGRATION = Path(__file__).resolve().parents[1] / 'app/migrations/001_durable.sql'


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        # Commands contain no credentials; PostgreSQL logs stay in the private directory.
        raise RuntimeError(f'{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}')
    return result.stdout


@contextmanager
def local_database(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    data = root / 'postgres'
    settings = root / 'settings.json'
    if data.exists() != settings.exists():
        raise RuntimeError('Incomplete local database setup; inspect the dedicated data directory.')
    if not settings.exists():
        config = {role: secrets.token_urlsafe(32) for role in ('owner', 'api', 'worker', 'tools', 'user_token', 'worker_token')}
        with settings.open('x') as output:
            os.chmod(settings, 0o600)
            json.dump(config, output)
        password_file = root / 'init-password'
        try:
            password_file.write_text(config['owner'])
            password_file.chmod(0o600)
            run('initdb', '-D', str(data), '-U', 'lab_owner', '--auth=scram-sha-256',
                '--pwfile=' + str(password_file), '--no-locale', '--encoding=UTF8')
        except Exception:
            settings.unlink(missing_ok=True)
            raise
        finally:
            password_file.unlink(missing_ok=True)
    config = json.loads(settings.read_text())
    # Private Unix socket only: no database TCP listener and no existing cluster changes.
    socket_dir = Path(tempfile.mkdtemp(prefix='agentic-devops-pg-'))
    try:
        run('pg_ctl', '-D', str(data), '-l', str(root / 'postgres.log'), '-o',
            f"-k {socket_dir} -h '' -p 5432", '-w', 'start')
        try:
            dsns = {role: make_conninfo(host=str(socket_dir), port=5432, dbname='postgres',
                                        user='lab_' + role, password=config[role])
                    for role in ('owner', 'api', 'worker', 'tools')}
            with psycopg.connect(dsns['owner']) as conn:
                conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                for role in ('api', 'worker', 'tools'):
                    name = 'lab_' + role
                    if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (name,)).fetchone():
                        conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(
                            sql.Identifier(name), sql.Literal(config[role])))
                conn.execute(MIGRATION.read_text())
            yield dsns, config
        finally:
            run('pg_ctl', '-D', str(data), '-m', 'fast', '-w', 'stop')
    finally:
        shutil.rmtree(socket_dir)
