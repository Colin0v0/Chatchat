import unittest
from collections.abc import AsyncIterator
from unittest.mock import patch

from app.chat.types import ChatDocumentPayload, ChatImagePayload, ChatMessagePayload
from app.provider_codecs.gemini import (
    _decode_gemini_stream_payload,
    _extract_gemini_output,
    gemini_request_payload,
)
from app.provider_transports.gemini import (
    stream_gemini_chat,
)


async def _drain(generator):
    items = []
    async for item in generator:
        items.append(item)
    return items


class _FakeGeminiStreamResponse:
    def __init__(self, *, lines: list[str], status_code: int = 200) -> None:
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


class _FakeGeminiStreamContext:
    def __init__(self, response: _FakeGeminiStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeGeminiStreamResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeGeminiClient:
    def __init__(self, *, lines: list[str]) -> None:
        self.lines = lines
        self.stream_calls: list[tuple[str, str, dict[str, object]]] = []
        self.post_calls: list[tuple[str, dict[str, object]]] = []

    def stream(self, method: str, url: str, *, json: dict[str, object]) -> _FakeGeminiStreamContext:
        self.stream_calls.append((method, url, json))
        return _FakeGeminiStreamContext(_FakeGeminiStreamResponse(lines=self.lines))

    async def post(self, url: str, *, json: dict[str, object]):
        self.post_calls.append((url, json))
        raise AssertionError("Gemini multimodal requests should not fall back to non-streaming POST.")


class GeminiClientTests(unittest.TestCase):
    def test_gemini_request_payload_maps_system_user_and_assistant_roles(self):
        payload = gemini_request_payload(
            [
                ChatMessagePayload(role="system", content="You are helpful."),
                ChatMessagePayload(role="user", content="Hello"),
                ChatMessagePayload(role="assistant", content="Hi"),
            ]
        )

        self.assertEqual(
            payload,
            {
                "contents": [
                    {"role": "user", "parts": [{"text": "Hello"}]},
                    {"role": "model", "parts": [{"text": "Hi"}]},
                ],
                "systemInstruction": {"parts": [{"text": "You are helpful."}]},
            },
        )

    def test_gemini_request_payload_supports_inline_images(self):
        payload = gemini_request_payload(
            [
                ChatMessagePayload(
                    role="user",
                    content="Describe this image",
                    images=(ChatImagePayload(mime_type="image/png", data_url="data:image/png;base64,ZmFrZQ=="),),
                )
            ]
        )

        self.assertEqual(
            payload,
            {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": "Describe this image"},
                            {"inlineData": {"mimeType": "image/png", "data": "ZmFrZQ=="}},
                        ],
                    }
                ]
            },
        )

    def test_gemini_request_payload_supports_inline_pdf_documents(self):
        payload = gemini_request_payload(
            [
                ChatMessagePayload(
                    role="user",
                    content="Summarize this PDF",
                    documents=(
                        ChatDocumentPayload(
                            mime_type="application/pdf",
                            filename="demo.pdf",
                            base64_data="JVBERi0xLjc=",
                        ),
                    ),
                )
            ]
        )

        self.assertEqual(
            payload,
            {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": "Summarize this PDF"},
                            {"inlineData": {"mimeType": "application/pdf", "data": "JVBERi0xLjc="}},
                        ],
                    }
                ]
            },
        )

    def test_decode_gemini_stream_payload_extracts_message_and_done(self):
        self.assertEqual(
            _decode_gemini_stream_payload(
                '{"candidates":[{"content":{"role":"model","parts":[{"text":"hello"}]},"finishReason":null}]}'
            ),
            {"message": {"content": "hello"}},
        )
        self.assertEqual(
            _decode_gemini_stream_payload(
                '{"candidates":[{"content":{"role":"model","parts":[]},"finishReason":"STOP"}]}'
            ),
            {"done": True},
        )

    def test_extract_gemini_output_collects_message_and_reasoning(self):
        self.assertEqual(
            _extract_gemini_output(
                {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {"thought": True, "text": "step 1"},
                                    {"text": "answer"},
                                ],
                            }
                        }
                    ]
                }
            ),
            {"message": "answer", "reasoning": "step 1"},
        )


class GeminiStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_gemini_chat_streams_inline_image_requests(self):
        fake_client = _FakeGeminiClient(
            lines=[
                'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"hello"}]},"finishReason":null}]}',
                "",
                'data: {"candidates":[{"content":{"role":"model","parts":[]},"finishReason":"STOP"}]}',
                "",
            ]
        )

        with patch("app.provider_transports.gemini._gemini_client", return_value=fake_client):
            result = await _drain(
                stream_gemini_chat(
                    model="gemini-3-flash",
                    messages=[
                        ChatMessagePayload(
                            role="user",
                            content="Describe this image",
                            images=(
                                ChatImagePayload(
                                    mime_type="image/png",
                                    data_url="data:image/png;base64,ZmFrZQ==",
                                ),
                            ),
                        )
                    ],
                )
            )

        self.assertEqual(
            fake_client.stream_calls,
            [
                (
                    "POST",
                    "/v1beta/models/gemini-3-flash:streamGenerateContent?alt=sse",
                    {
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {"text": "Describe this image"},
                                    {"inlineData": {"mimeType": "image/png", "data": "ZmFrZQ=="}},
                                ],
                            }
                        ]
                    },
                )
            ],
        )
        self.assertEqual(fake_client.post_calls, [])
        self.assertEqual(
            result,
            [
                {"message": {"content": "hello"}},
                {"done": True},
            ],
        )

    async def test_stream_gemini_chat_streams_inline_pdf_requests(self):
        fake_client = _FakeGeminiClient(
            lines=[
                'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"summary"}]},"finishReason":"STOP"}]}',
                "",
            ]
        )

        with patch("app.provider_transports.gemini._gemini_client", return_value=fake_client):
            result = await _drain(
                stream_gemini_chat(
                    model="gemini-3-flash",
                    messages=[
                        ChatMessagePayload(
                            role="user",
                            content="Summarize this PDF",
                            documents=(
                                ChatDocumentPayload(
                                    mime_type="application/pdf",
                                    filename="demo.pdf",
                                    base64_data="JVBERi0xLjc=",
                                ),
                            ),
                        )
                    ],
                )
            )

        self.assertEqual(
            fake_client.stream_calls,
            [
                (
                    "POST",
                    "/v1beta/models/gemini-3-flash:streamGenerateContent?alt=sse",
                    {
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {"text": "Summarize this PDF"},
                                    {"inlineData": {"mimeType": "application/pdf", "data": "JVBERi0xLjc="}},
                                ],
                            }
                        ]
                    },
                )
            ],
        )
        self.assertEqual(fake_client.post_calls, [])
        self.assertEqual(
            result,
            [
                {"message": {"content": "summary"}, "done": True},
            ],
        )


if __name__ == "__main__":
    unittest.main()
