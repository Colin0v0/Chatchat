import unittest
from pathlib import Path
from unittest.mock import patch

from app.multimodal.file_parser import FileParser
from app.storage.models import MessageAttachment


class FileParserTests(unittest.TestCase):
    def test_parse_text_file_to_markdown(self):
        parser = FileParser(text_max_chars=2000, table_row_limit=10, table_column_limit=8)
        root = Path(__file__).resolve().parent / "assets"
        file_path = root / "sample-note.md"
        attachment = MessageAttachment(
            kind="file",
            original_name="sample-note.md",
            mime_type="text/markdown",
            relative_path="sample-note.md",
            size_bytes=file_path.stat().st_size,
            extension=".md",
            position=0,
        )

        with patch("app.multimodal.file_parser.MEDIA_ROOT", root):
            markdown = parser.extract_markdown([attachment])

        self.assertIn("### File 1", markdown)
        self.assertIn("name: sample-note.md", markdown)
        self.assertIn("hello file parser", markdown)

    def test_parse_csv_file_to_markdown(self):
        parser = FileParser(text_max_chars=2000, table_row_limit=10, table_column_limit=8)
        root = Path(__file__).resolve().parent / "assets"
        file_path = root / "sample-table.csv"
        attachment = MessageAttachment(
            kind="file",
            original_name="sample-table.csv",
            mime_type="text/csv",
            relative_path="sample-table.csv",
            size_bytes=file_path.stat().st_size,
            extension=".csv",
            position=0,
        )

        with patch("app.multimodal.file_parser.MEDIA_ROOT", root):
            markdown = parser.extract_markdown([attachment])

        self.assertIn("columns: name, score", markdown)
        self.assertIn("row 1: alice, 10", markdown)


if __name__ == "__main__":
    unittest.main()
