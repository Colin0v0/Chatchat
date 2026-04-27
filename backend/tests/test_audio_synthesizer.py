import unittest

from app.audio.synthesizer import (
    AudioSynthesisError,
    AudioSynthesisRequest,
    DashScopeSpeechSynthesizer,
)


def make_synthesizer(**overrides):
    options = {
        "model_name": "cosyvoice-v3-flash",
        "base_url": "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer",
        "api_key": "test-key",
        "enabled": True,
        "voice": "longanyang",
        "audio_format": "mp3",
        "sample_rate": 24000,
        "timeout_seconds": 30.0,
        "max_chars": 3000,
    }
    options.update(overrides)
    return DashScopeSpeechSynthesizer(**options)


class DashScopeSpeechSynthesizerTests(unittest.TestCase):
    def test_request_payload_uses_cosyvoice_v3_voice_and_parameters(self):
        synthesizer = make_synthesizer()

        payload = synthesizer._request_payload(text="你好", voice="longanhuan", rate=1.2)

        self.assertEqual(payload["model"], "cosyvoice-v3-flash")
        self.assertEqual(
            payload["input"],
            {
                "text": "你好",
                "voice": "longanhuan",
                "format": "mp3",
                "sample_rate": 24000,
                "rate": 1.2,
            },
        )

    def test_parse_response_extracts_audio_url(self):
        synthesizer = make_synthesizer()

        result = synthesizer._parse_response(
            {
                "request_id": "req-1",
                "output": {
                    "audio": {
                        "id": "audio-1",
                        "url": "https://example.com/audio.mp3",
                        "expires_at": 1770000000,
                    }
                },
                "usage": {"characters": 2},
            },
            voice="longanyang",
        )

        self.assertEqual(result.url, "https://example.com/audio.mp3")
        self.assertEqual(result.content_type, "audio/mpeg")
        self.assertEqual(result.model, "cosyvoice-v3-flash")
        self.assertEqual(result.voice, "longanyang")
        self.assertEqual(result.audio_id, "audio-1")
        self.assertEqual(result.expires_at, 1770000000)
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(result.characters, 2)

    def test_missing_api_key_is_reported_when_synthesizing(self):
        synthesizer = make_synthesizer(api_key="")

        with self.assertRaisesRegex(AudioSynthesisError, "API key"):
            synthesizer.synthesize(AudioSynthesisRequest(text="你好"))


if __name__ == "__main__":
    unittest.main()
