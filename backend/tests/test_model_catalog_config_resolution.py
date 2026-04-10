import os
import unittest
from unittest.mock import patch

from app.llm.catalog import _parse_routes, _resolve_api_key, _resolve_env_value, resolve_native_multimodal_mode


class ModelCatalogConfigResolutionTests(unittest.TestCase):
    def test_resolve_env_value_uses_settings_when_os_env_missing(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.llm.catalog.settings.openai_local_base_url",
            "http://127.0.0.1:18000/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${OPENAI_LOCAL_BASE_URL}"),
                "http://127.0.0.1:18000/v1",
            )

    def test_resolve_env_value_prefers_os_env_over_settings(self):
        with patch.dict(os.environ, {"OPENAI_LOCAL_BASE_URL": "http://localhost:19000/v1"}, clear=True), patch(
            "app.llm.catalog.settings.openai_local_base_url",
            "http://127.0.0.1:18000/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${OPENAI_LOCAL_BASE_URL}"),
                "http://localhost:19000/v1",
            )

    def test_resolve_api_key_uses_settings_when_os_env_missing(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.llm.catalog.settings.openai_local_api_key",
            "sk-local-from-settings",
        ):
            self.assertEqual(
                _resolve_api_key(api_key=None, api_key_env="OPENAI_LOCAL_API_KEY"),
                "sk-local-from-settings",
            )

    def test_resolve_env_value_reads_codex_base_url_from_settings(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.llm.catalog.settings.codex_base_url",
            "https://api.openai.com/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${CODEX_BASE_URL}"),
                "https://api.openai.com/v1",
            )

    def test_parse_routes_requires_string_native_multimodal_mode(self):
        with self.assertRaisesRegex(RuntimeError, "native_multimodal must be string"):
            _parse_routes(
                {
                    "models": [
                        {
                            "id": "codex:gpt-5.4",
                            "provider": "codex",
                            "native_multimodal": True,
                        }
                    ]
                }
            )

    def test_resolve_native_multimodal_mode_defaults_to_false_for_unknown_model(self):
        self.assertEqual(resolve_native_multimodal_mode("openai:unknown-model"), "false")


if __name__ == "__main__":
    unittest.main()
