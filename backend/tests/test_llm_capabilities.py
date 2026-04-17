import unittest

from app.llm.capabilities import (
    filter_chat_model_names,
    is_non_chat_model_name,
    model_provider_and_name,
    normalize_base_url,
    present_model_name,
)


class LlmCapabilitiesTests(unittest.TestCase):
    def test_translation_models_are_filtered_without_model_specific_hardcode(self):
        self.assertTrue(is_non_chat_model_name("translategemma:latest"))
        self.assertTrue(is_non_chat_model_name("translation-helper:1b"))
        self.assertFalse(is_non_chat_model_name("gemma4:e4b"))

    def test_filter_chat_model_names_excludes_embedding_and_translation_models(self):
        filtered = filter_chat_model_names(
            [
                "qwen3:4b",
                "qwen3-embedding:0.6b",
                "translategemma:latest",
                "my-translation-model:latest",
            ]
        )

        self.assertEqual(filtered, ["qwen3:4b"])

    def test_normalize_base_url_supports_localhost_shorthand(self):
        self.assertEqual(
            normalize_base_url(":18000/v1"),
            "http://127.0.0.1:18000/v1",
        )
        self.assertEqual(
            normalize_base_url("localhost:18000/v1"),
            "http://localhost:18000/v1",
        )
        self.assertEqual(
            normalize_base_url("http://127.0.0.1:18000/v1/"),
            "http://127.0.0.1:18000/v1",
        )

    def test_codex_provider_is_recognized_by_model_parser(self):
        self.assertEqual(
            model_provider_and_name("codex:gpt-5.3-codex"),
            ("codex", "gpt-5.3-codex"),
        )

    def test_gemini_provider_is_recognized_by_model_parser(self):
        self.assertEqual(
            model_provider_and_name("gemini:gemini-3-flash"),
            ("gemini", "gemini-3-flash"),
        )

    def test_trio_provider_is_recognized_by_model_parser(self):
        self.assertEqual(
            model_provider_and_name("trio:my-model-path"),
            ("trio", "my-model-path"),
        )

    def test_present_model_name_hides_codex_namespace(self):
        self.assertEqual(
            present_model_name("codex:gpt-5.3-codex"),
            "gpt-5.3-codex",
        )

    def test_present_model_name_hides_gemini_namespace(self):
        self.assertEqual(
            present_model_name("gemini:gemini-3-flash"),
            "gemini-3-flash",
        )

    def test_present_model_name_hides_trio_namespace(self):
        self.assertEqual(
            present_model_name("trio:my-model-path"),
            "my-model-path",
        )


if __name__ == "__main__":
    unittest.main()
