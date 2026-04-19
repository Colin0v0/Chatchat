import unittest

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


if __name__ == "__main__":
    unittest.main()
