import unittest
from unittest.mock import patch

from app.storage import database
from app.storage.database import _validate_database_backend


class StorageDatabaseConfigTests(unittest.TestCase):
    def test_accepts_postgresql_backend(self):
        _validate_database_backend("postgresql")

    def test_rejects_sqlite_backend(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_database_backend("sqlite")

        self.assertIn("SQLite startup support has been removed", str(ctx.exception))
        self.assertIn("PostgreSQL + pgvector", str(ctx.exception))

    def test_rejects_other_database_backends(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_database_backend("mysql")

        self.assertIn("Unsupported database backend 'mysql'", str(ctx.exception))

    def test_get_db_rolls_back_on_route_exception(self):
        class FakeSession:
            def __init__(self):
                self.rolled_back = False
                self.closed = False

            def rollback(self):
                self.rolled_back = True

            def close(self):
                self.closed = True

        fake_session = FakeSession()
        with patch.object(database, "_schema_ready", True), patch.object(
            database,
            "SessionLocal",
            return_value=fake_session,
        ):
            dependency = database.get_db()
            self.assertIs(next(dependency), fake_session)
            with self.assertRaises(RuntimeError):
                dependency.throw(RuntimeError("route failed"))

        self.assertTrue(fake_session.rolled_back)
        self.assertTrue(fake_session.closed)


if __name__ == "__main__":
    unittest.main()
