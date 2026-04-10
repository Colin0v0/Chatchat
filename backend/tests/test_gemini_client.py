import unittest

from app.chat.types import ChatDocumentPayload, ChatImagePayload, ChatMessagePayload
from app.llm.gemini_client import _decode_gemini_stream_payload, _extract_gemini_output, gemini_request_payload


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


if __name__ == "__main__":
    unittest.main()
