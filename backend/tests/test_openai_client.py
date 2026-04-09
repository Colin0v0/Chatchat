import unittest

import httpx

from app.llm.openai_client import (
    _decode_openai_stream_payload,
    _iter_openai_stream_payloads,
    _parse_openai_json_response,
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


if __name__ == "__main__":
    unittest.main()
