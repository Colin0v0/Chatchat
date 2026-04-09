import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.retrieval.websearch.translator import (
    WebSearchTranslationError,
    translate_query_for_search,
)


class WebSearchTranslatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_underspecified_translation_preserves_original_cjk_query(self):
        settings = SimpleNamespace(web_search_translation_model="openai_local:claude-haiku-4-5")

        with patch("app.retrieval.websearch.translator.complete_chat", return_value="today"):
            translated = await translate_query_for_search("今天是周几", settings)

        self.assertEqual(translated, "今天是周几")

    async def test_underspecified_translation_allows_single_latin_subject(self):
        settings = SimpleNamespace(web_search_translation_model="openai_local:claude-haiku-4-5")

        with patch("app.retrieval.websearch.translator.complete_chat", return_value="Tinker"):
            translated = await translate_query_for_search("你给我详细介绍一下Tinker", settings)

        self.assertEqual(translated, "Tinker")

    async def test_invalid_translation_still_raises(self):
        settings = SimpleNamespace(web_search_translation_model="openai_local:claude-haiku-4-5")

        with patch(
            "app.retrieval.websearch.translator.complete_chat",
            return_value="Sorry, please provide the Chinese text.",
        ):
            with self.assertRaises(WebSearchTranslationError):
                await translate_query_for_search("今天是周几", settings)


if __name__ == "__main__":
    unittest.main()
