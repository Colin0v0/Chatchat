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
            "native_multimodal": True,
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
            "native_multimodal": False,
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
            "native_multimodal": True,
            "supports_thinking": True,
        }

        with patch("app.llm.service.resolve_model_route", return_value=route), patch(
            "app.llm.service.settings.openai_local_upstream_service_base_url",
            "",
        ):
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
