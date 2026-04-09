import unittest

from app.llm.capabilities import filter_chat_model_names, is_non_chat_model_name


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


if __name__ == "__main__":
    unittest.main()
