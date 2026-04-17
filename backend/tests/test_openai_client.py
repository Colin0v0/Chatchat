import unittest

import httpx

from app.llm.openai_client import (
    _decode_responses_stream_payload,
    _extract_responses_output,
    _decode_openai_stream_payload,
    _iter_openai_stream_payloads,
    _parse_openai_json_response,
    apply_reasoning_controls,
    apply_responses_reasoning_controls,
    openai_base_url,
    openai_headers,
    responses_message_payload,
    supports_chat_completions_streaming,
)


async def _aiter(lines: list[str]):
    for line in lines:
        yield line


class OpenAIClientStreamParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_iter_openai_stream_payloads_skips_sse_comments_and_collects_data_frames(self):
        payloads = []
        async for payload in _iter_openai_stream_payloads(
            _aiter(
                [
                    ": ping",
                    "",
                    "event: message",
                    'data: {"choices":[{"delta":{"content":"Hi"}}]}',
                    "",
                    ' {"choices":[{"delta":{"content":" there"}}]} ',
                ]
            )
        ):
            payloads.append(payload)

        self.assertEqual(
            payloads,
            [
                '{"choices":[{"delta":{"content":"Hi"}}]}',
                '{"choices":[{"delta":{"content":" there"}}]}',
            ],
        )

    def test_decode_openai_stream_payload_returns_empty_for_non_json_heartbeat(self):
        self.assertEqual(_decode_openai_stream_payload("event: ping"), {})

    def test_decode_openai_stream_payload_extracts_message_reasoning_and_done(self):
        payload = (
            '{"choices":[{"delta":{"content":"answer","reasoning_content":"trace"},"finish_reason":"stop"}]}'
        )

        self.assertEqual(
            _decode_openai_stream_payload(payload),
            {
                "done": True,
                "message": {"content": "answer"},
                "reasoning": {"content": "trace"},
            },
        )

    def test_decode_openai_stream_payload_raises_for_malformed_json_chunk(self):
        payload = '{"choices":[{"delta":{"content":"answer"}}'

        with self.assertRaises(RuntimeError):
            _decode_openai_stream_payload(payload)

    def test_parse_openai_json_response_rejects_non_json_payload(self):
        response = httpx.Response(
            200,
            text="Waiting for application startup.\\nINFO: Application startup complete.",
        )

        with self.assertRaises(RuntimeError) as ctx:
            _parse_openai_json_response(response, context="chat.completions")

        self.assertIn("non-JSON response", str(ctx.exception))
        self.assertIn("chat.completions", str(ctx.exception))

    def test_decode_responses_stream_payload_extracts_text_reasoning_and_done(self):
        self.assertEqual(
            _decode_responses_stream_payload('{"type":"response.output_text.delta","delta":"answer"}'),
            {"message": {"content": "answer"}},
        )
        self.assertEqual(
            _decode_responses_stream_payload('{"type":"response.reasoning_summary_text.delta","delta":"plan"}'),
            {"reasoning": {"content": "plan"}},
        )
        self.assertEqual(
            _decode_responses_stream_payload('{"type":"response.completed"}'),
            {"done": True},
        )

    def test_extract_responses_output_collects_message_and_reasoning_summary(self):
        payload = {
            "output": [
                {"type": "reasoning", "summary": [{"type": "summary_text", "text": "step 1"}]},
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "answer"}],
                },
            ]
        }

        self.assertEqual(
            _extract_responses_output(payload),
            {"message": "answer", "reasoning": "step 1"},
        )


class OpenAIReasoningControlsTests(unittest.TestCase):
    def test_apply_reasoning_controls_uses_local_thinking_flag_for_openai_local(self):
        payload: dict[str, object] = {}

        apply_reasoning_controls(payload, provider="openai_local", thinking_enabled=True)

        self.assertEqual(payload, {"thinking": {"type": "enabled"}})

    def test_apply_reasoning_controls_uses_reasoning_effort_for_codex(self):
        payload: dict[str, object] = {}

        apply_reasoning_controls(payload, provider="codex", thinking_enabled=True)

        self.assertEqual(payload, {"reasoning_effort": "medium"})

    def test_apply_reasoning_controls_disables_reasoning_for_codex(self):
        payload: dict[str, object] = {}

        apply_reasoning_controls(payload, provider="codex", thinking_enabled=False)

        self.assertEqual(payload, {"reasoning_effort": "none"})

    def test_apply_reasoning_controls_skips_openai_provider(self):
        payload: dict[str, object] = {}

        apply_reasoning_controls(payload, provider="openai", thinking_enabled=True)

        self.assertEqual(payload, {})


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_openai_base_url_reads_trio_settings(self):
        from app.core.config import settings

        original = settings.trio_base_url
        settings.trio_base_url = "https://pytrio.cn/api/v1"
        try:
            self.assertEqual(openai_base_url("trio"), "https://pytrio.cn/api/v1")
        finally:
            settings.trio_base_url = original

    def test_openai_headers_reads_trio_api_key(self):
        from app.core.config import settings

        original = settings.trio_api_key
        settings.trio_api_key = "sk-trio"
        try:
            self.assertEqual(openai_headers("trio"), {"Authorization": "Bearer sk-trio"})
        finally:
            settings.trio_api_key = original

    def test_supports_chat_completions_streaming_disables_trio(self):
        self.assertFalse(supports_chat_completions_streaming("trio"))

    def test_apply_responses_reasoning_controls_enables_summary_for_reasoning_models(self):
        payload: dict[str, object] = {}

        apply_responses_reasoning_controls(payload, thinking_enabled=True)

        self.assertEqual(payload, {"reasoning": {"effort": "medium", "summary": "auto"}})

    def test_apply_responses_reasoning_controls_disables_reasoning_without_summary(self):
        payload: dict[str, object] = {}

        apply_responses_reasoning_controls(payload, thinking_enabled=False)

        self.assertEqual(payload, {"reasoning": {"effort": "none"}})


class ResponsesPayloadTests(unittest.TestCase):
    def test_responses_message_payload_supports_mixed_multimodal_inputs(self):
        from app.chat.types import ChatFileReferencePayload, ChatImagePayload, ChatMessagePayload

        payload = responses_message_payload(
            ChatMessagePayload(
                role="user",
                content="look at these",
                images=(ChatImagePayload(mime_type="image/png", data_url="data:image/png;base64,ZmFrZQ=="),),
                files=(ChatFileReferencePayload(file_id="file_demo"),),
            )
        )

        self.assertEqual(
            payload,
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "look at these"},
                    {"type": "input_image", "image_url": "data:image/png;base64,ZmFrZQ=="},
                    {"type": "input_file", "file_id": "file_demo"},
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
