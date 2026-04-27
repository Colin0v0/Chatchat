import os
import unittest
from unittest.mock import patch

from app.providers.catalog import _parse_profiles, _resolve_api_key, _resolve_env_value, resolve_native_multimodal_mode


class ModelCatalogConfigResolutionTests(unittest.TestCase):
    def test_resolve_env_value_uses_settings_when_os_env_missing(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.providers.catalog.settings.codex_base_url",
            "https://api.openai.com/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${CODEX_BASE_URL}"),
                "https://api.openai.com/v1",
            )

    def test_resolve_env_value_prefers_os_env_over_settings(self):
        with patch.dict(os.environ, {"CODEX_BASE_URL": "https://custom.example.com/v1"}, clear=True), patch(
            "app.providers.catalog.settings.codex_base_url",
            "https://api.openai.com/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${CODEX_BASE_URL}"),
                "https://custom.example.com/v1",
            )

    def test_resolve_api_key_uses_settings_when_os_env_missing(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.providers.catalog.settings.codex_api_key",
            "sk-codex-from-settings",
        ):
            self.assertEqual(
                _resolve_api_key(api_key=None, api_key_env="CODEX_API_KEY"),
                "sk-codex-from-settings",
            )

    def test_resolve_env_value_reads_codex_base_url_from_settings(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.providers.catalog.settings.codex_base_url",
            "https://api.openai.com/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${CODEX_BASE_URL}"),
                "https://api.openai.com/v1",
            )

    def test_resolve_env_value_reads_trio_base_url_from_settings(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.providers.catalog.settings.trio_base_url",
            "https://pytrio.cn/api/v1",
        ):
            self.assertEqual(
                _resolve_env_value("${TRIO_BASE_URL}"),
                "https://pytrio.cn/api/v1",
            )

    def test_parse_profiles_supports_trio_provider_preset(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "app.providers.catalog.settings.trio_model_path",
            "your-model-path",
        ):
            profiles = _parse_profiles(
                {
                    "providers": {
                        "trio_default": {
                            "provider": "trio",
                            "base_url": "${TRIO_BASE_URL}",
                            "api_key_env": "TRIO_API_KEY",
                        }
                    },
                    "models": [
                        {
                            "id": "trio:your-model-path",
                            "provider_ref": "trio_default",
                            "upstream_model": "${TRIO_MODEL_PATH}",
                            "runtime": {
                                "native_multimodal_mode": "false"
                            },
                            "capabilities": {
                                "input": {
                                    "text": True,
                                    "image": False,
                                    "pdf": False,
                                    "other_file": False,
                                    "audio": False
                                },
                                "transport": {
                                    "inline_data": False,
                                    "file_upload": False,
                                    "remote_url": True
                                },
                                "reasoning": {
                                    "control": "none",
                                    "default_profile": "off",
                                    "visible_trace": False,
                                    "summary_only": False
                                },
                                "tools": {
                                    "function_calling": False,
                                    "parallel_calls": False,
                                    "forced_call": False
                                },
                                "stream": {
                                    "text": True,
                                    "reasoning": False,
                                    "tool_call": False,
                                    "usage": False
                                },
                                "state": {
                                    "previous_response": False
                                }
                            }
                        }
                    ],
                }
            )

        self.assertEqual(profiles[0].provider_name, "trio")
        self.assertEqual(profiles[0].upstream_model, "your-model-path")

    def test_parse_profiles_requires_string_native_multimodal_mode(self):
        with self.assertRaisesRegex(RuntimeError, "runtime.native_multimodal_mode"):
            _parse_profiles(
                {
                    "models": [
                        {
                            "id": "codex:gpt-5.4",
                            "provider": "codex",
                            "runtime": {
                                "native_multimodal_mode": True
                            },
                            "capabilities": {
                                "input": {
                                    "text": True,
                                    "image": True,
                                    "pdf": True,
                                    "other_file": True,
                                    "audio": True
                                },
                                "transport": {
                                    "inline_data": True,
                                    "file_upload": True,
                                    "remote_url": True
                                },
                                "reasoning": {
                                    "control": "effort",
                                    "default_profile": "off",
                                    "visible_trace": False,
                                    "summary_only": True
                                },
                                "tools": {
                                    "function_calling": True,
                                    "parallel_calls": True,
                                    "forced_call": True
                                },
                                "stream": {
                                    "text": True,
                                    "reasoning": True,
                                    "tool_call": True,
                                    "usage": True
                                },
                                "state": {
                                    "previous_response": True
                                }
                            }
                        }
                    ]
                }
            )

    def test_resolve_native_multimodal_mode_defaults_to_false_for_unknown_model(self):
        self.assertEqual(resolve_native_multimodal_mode("openai:unknown-model"), "false")


if __name__ == "__main__":
    unittest.main()
