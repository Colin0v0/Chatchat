import unittest
from pathlib import Path
from unittest.mock import patch

from app.storage.database import _is_windows_mounted_path, _sqlite_pragma_settings


class StorageDatabaseConfigTests(unittest.TestCase):
    def test_uses_delete_journal_on_windows_mounted_path(self):
        settings = _sqlite_pragma_settings("sqlite:////mnt/e/vscodeproject/chatchat/storage/app.db")

        self.assertEqual(settings["journal_mode"], "DELETE")
        self.assertEqual(settings["synchronous"], "FULL")

    def test_uses_wal_on_native_linux_path(self):
        settings = _sqlite_pragma_settings("sqlite:////home/user/chatchat/storage/app.db")

        self.assertEqual(settings["journal_mode"], "WAL")
        self.assertEqual(settings["synchronous"], "NORMAL")

    def test_prefers_explicit_sqlite_pragma_overrides(self):
        with patch("app.storage.database.settings.sqlite_journal_mode", "delete"), patch(
            "app.storage.database.settings.sqlite_synchronous",
            "full",
        ):
            settings = _sqlite_pragma_settings("sqlite:////home/user/chatchat/storage/app.db")

        self.assertEqual(settings["journal_mode"], "DELETE")
        self.assertEqual(settings["synchronous"], "FULL")

    def test_detects_windows_mounted_path(self):
        self.assertTrue(_is_windows_mounted_path(Path("/mnt/e/chatchat/storage/app.db")))
        self.assertFalse(_is_windows_mounted_path(Path("/home/user/chatchat/storage/app.db")))


if __name__ == "__main__":
    unittest.main()
