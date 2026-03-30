import time
import unittest

from app.llm.ollama_runtime import ollama_keep_alive_value


class OllamaRuntimeTests(unittest.TestCase):
    def test_keep_alive_defaults_to_immediate_unload_when_non_positive(self):
        self.assertEqual(ollama_keep_alive_value(0), 0)
        self.assertEqual(ollama_keep_alive_value(-1), 0)

    def test_keep_alive_preserves_positive_seconds(self):
        self.assertEqual(ollama_keep_alive_value(60), 60)


if __name__ == "__main__":
    unittest.main()
