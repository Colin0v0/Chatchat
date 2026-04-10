import unittest
from unittest.mock import patch

from app.chat.types import ChatMessagePayload
from app.llm.service import stream_chat


async def _drain(generator):
    items = []
    async for item in generator:
        items.append(item)
    return items


class NativeMultimodalRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_multimodal_openai_route_uses_upstream_service_base_url(self):
        route = {
            "id": "openai_local:claude-sonnet-4-6",
            "display_name": "Claude Sonnet 4.6",
            "provider": "openai_local",
            "upstream_model": "claude-sonnet-4-6",
            "base_url": "http://127.0.0.1:18000/v1",
            "upstream_service_base_url": "http://127.0.0.1:61527/v1",
            "api_key": None,
            "thinking_mode": "default_on",
            "context_window": 1000000,
            "native_multimodal": "local",
            "supports_thinking": True,
        }
        captured = {}

        async def fake_stream_openai_chat(**kwargs):
            captured.update(kwargs)
            yield {"done": True}

        with patch("app.llm.service.resolve_model_route", return_value=route), patch(
            "app.llm.service.stream_openai_chat",
            side_effect=fake_stream_openai_chat,
        ):
            await _drain(
                stream_chat(
                    model="openai_local:claude-sonnet-4-6",
                    messages=[ChatMessagePayload(role="user", content="hello")],
                )
            )

        self.assertEqual(captured["base_url_override"], "http://127.0.0.1:61527/v1")
        self.assertEqual(captured["model"], "claude-sonnet-4-6")

    async def test_non_native_route_keeps_regular_base_url(self):
        route = {
            "id": "openai_local:claude-sonnet-4-6",
            "display_name": "Claude Sonnet 4.6",
            "provider": "openai_local",
            "upstream_model": "claude-sonnet-4-6",
            "base_url": "http://127.0.0.1:18000/v1",
            "upstream_service_base_url": "http://127.0.0.1:61527/v1",
            "api_key": None,
            "thinking_mode": "default_on",
            "context_window": 1000000,
            "native_multimodal": "false",
            "supports_thinking": True,
        }
        captured = {}

        async def fake_stream_openai_chat(**kwargs):
            captured.update(kwargs)
            yield {"done": True}

        with patch("app.llm.service.resolve_model_route", return_value=route), patch(
            "app.llm.service.stream_openai_chat",
            side_effect=fake_stream_openai_chat,
        ):
            await _drain(
                stream_chat(
                    model="openai_local:claude-sonnet-4-6",
                    messages=[ChatMessagePayload(role="user", content="hello")],
                )
            )

        self.assertEqual(captured["base_url_override"], "http://127.0.0.1:18000/v1")

    async def test_codex_native_image_route_keeps_regular_base_url(self):
        route = {
            "id": "codex:gpt-5.4",
            "display_name": "GPT-5.4",
            "provider": "codex",
            "upstream_model": "gpt-5.4",
            "base_url": "https://api.openai.com/v1",
            "upstream_service_base_url": None,
            "api_key": None,
            "thinking_mode": "force_on",
            "context_window": 1000000,
            "native_multimodal": "codex",
            "supports_thinking": True,
        }
        captured = {}

        async def fake_stream_openai_chat(**kwargs):
            captured.update(kwargs)
            yield {"done": True}

        with patch("app.llm.service.resolve_model_route", return_value=route), patch(
            "app.llm.service.stream_openai_chat",
            side_effect=fake_stream_openai_chat,
        ):
            await _drain(
                stream_chat(
                    model="codex:gpt-5.4",
                    messages=[ChatMessagePayload(role="user", content="hello")],
                )
            )

        self.assertEqual(captured["base_url_override"], "https://api.openai.com/v1")
        self.assertEqual(captured["model"], "gpt-5.4")

    async def test_gemini_native_route_keeps_regular_base_url(self):
        route = {
            "id": "gemini:gemini-3-flash",
            "display_name": "Gemini 3 Flash",
            "provider": "gemini",
            "upstream_model": "gemini-3-flash",
            "base_url": "https://api.ikuncode.cc",
            "upstream_service_base_url": None,
            "api_key": None,
            "thinking_mode": "force_off",
            "context_window": 1000000,
            "native_multimodal": "gemini",
            "supports_thinking": False,
        }
        captured = {}

        async def fake_stream_gemini_chat(**kwargs):
            captured.update(kwargs)
            yield {"done": True}

        with patch("app.llm.service.resolve_model_route", return_value=route), patch(
            "app.llm.service.stream_gemini_chat",
            side_effect=fake_stream_gemini_chat,
        ):
            await _drain(
                stream_chat(
                    model="gemini:gemini-3-flash",
                    messages=[ChatMessagePayload(role="user", content="hello")],
                )
            )

        self.assertEqual(captured["base_url_override"], "https://api.ikuncode.cc")
        self.assertEqual(captured["model"], "gemini-3-flash")

    async def test_native_multimodal_route_without_upstream_endpoint_raises(self):
        route = {
            "id": "openai_local:claude-sonnet-4-6",
            "display_name": "Claude Sonnet 4.6",
            "provider": "openai_local",
            "upstream_model": "claude-sonnet-4-6",
            "base_url": "http://127.0.0.1:18000/v1",
            "upstream_service_base_url": None,
            "api_key": None,
            "thinking_mode": "default_on",
            "context_window": 1000000,
            "native_multimodal": "local",
            "supports_thinking": True,
        }

        with patch("app.llm.service.resolve_model_route", return_value=route):
            with self.assertRaises(RuntimeError) as ctx:
                await _drain(
                    stream_chat(
                        model="openai_local:claude-sonnet-4-6",
                        messages=[ChatMessagePayload(role="user", content="hello")],
                    )
                )

        self.assertIn("Native multimodal endpoint is not configured", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
