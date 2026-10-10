"""Deployment-adapter tests; do not require external services or credentials."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.db import PostgreSQLCursor, PostgreSQLConnection, get_db_connection, init_db


class FakeCursor:
    def __init__(self):
        self.sql = None
        self.params = None
        self.rowcount = 2

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return {'ok': True}

    def fetchall(self):
        return [{'ok': True}]


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


class RailwayReadinessTests(unittest.TestCase):
    def test_qmark_parameters_to_postgres(self):
        raw = FakeCursor()
        cursor = PostgreSQLCursor(raw)
        self.assertIs(cursor.execute('SELECT * FROM t WHERE a=? AND b=?', ('a','b')), cursor)
        self.assertEqual(raw.sql, 'SELECT * FROM t WHERE a=%s AND b=%s')
        self.assertEqual(raw.params, ('a','b'))
        self.assertEqual(cursor.fetchone(), {'ok': True})
        self.assertEqual(cursor.fetchall(), [{'ok': True}])
        self.assertEqual(cursor.rowcount, 2)

    def test_pg_connection_compatible_api(self):
        raw = FakeConn()
        conn = PostgreSQLConnection(raw)
        self.assertEqual(conn.execute('SELECT ?', (1,)).fetchone(), {'ok': True})
        conn.commit(); conn.rollback(); conn.close()
        self.assertEqual((raw.commits,raw.rollbacks,raw.closed),(1,1,1))

    def test_db_path_override_never_uses_network(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td,'isolated.sqlite')
            with patch.dict(os.environ, {'DATABASE_URL':'postgresql://unused:password@invalid/unused'}):
                init_db(path)
                conn = get_db_connection(path)
                try:
                    self.assertIsNotNone(conn.execute('SELECT name FROM sqlite_master WHERE name=?', ('users',)).fetchone())
                finally:
                    conn.close()

    def test_production_refuses_missing_postgres(self):
        env = {**os.environ, 'ENVIRONMENT':'production', 'JWT_SECRET_KEY':'x'*40}
        env.pop('DATABASE_URL',None)
        result = subprocess.run([sys.executable, '-c','import app.config'],env=env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('PostgreSQL DATABASE_URL',result.stderr)

    def test_production_refuses_weak_secret(self):
        env = {**os.environ, 'ENVIRONMENT':'production', 'JWT_SECRET_KEY':'weak',
               'DATABASE_URL':'postgresql://unused/unused'}
        result = subprocess.run([sys.executable, '-c','import app.config'],env=env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('JWT_SECRET_KEY',result.stderr)
