import math
import struct
import unittest
import wave
from io import BytesIO

from app.audio.transcriber import AudioTranscriber, OpenAICompatibleAudioTranscriber


def _wav_bytes(samples: list[int], *, sample_rate: int = 16000) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))
    return buffer.getvalue()


def _tone_wav(*, duration_ms: int, amplitude: int = 2400) -> bytes:
    sample_rate = 16000
    sample_count = int(sample_rate * duration_ms / 1000)
    samples = [
        int(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
        for index in range(sample_count)
    ]
    return _wav_bytes(samples, sample_rate=sample_rate)


class AudioTranscriberTests(unittest.TestCase):
    def test_short_audio_is_skipped_before_api_request(self):
        transcriber = AudioTranscriber(
            model_name="qwen3-asr-flash",
            enabled=True,
            min_duration_ms=650,
        )
        wav_bytes = _tone_wav(duration_ms=300)

        decision = transcriber._inspect_audio(wav_bytes, duration_ms=300)
        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "too_short")

    def test_silent_audio_is_skipped_before_api_request(self):
        transcriber = AudioTranscriber(
            model_name="qwen3-asr-flash",
            enabled=True,
            min_duration_ms=650,
            min_rms_dbfs=-52,
        )
        wav_bytes = _wav_bytes([0] * 16000)

        decision = transcriber._inspect_audio(wav_bytes, duration_ms=1000)
        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "too_quiet")

    def test_audible_audio_is_not_skipped(self):
        transcriber = AudioTranscriber(
            model_name="qwen3-asr-flash",
            enabled=True,
            min_duration_ms=650,
            min_rms_dbfs=-52,
        )
        wav_bytes = _tone_wav(duration_ms=1000)

        self.assertFalse(transcriber._should_skip_audio(wav_bytes, duration_ms=1000))

    def test_openai_compatible_audio_transcriber_builds_qwen_asr_payload(self):
        transcriber = OpenAICompatibleAudioTranscriber(
            model_name="qwen3-asr-flash",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="test-key",
            enabled=True,
        )
        payload = transcriber._request_payload("data:audio/wav;base64,AAAA")

        self.assertEqual(payload["model"], "qwen3-asr-flash")
        message = payload["messages"][0]
        audio_block = message["content"][0]
        self.assertEqual(audio_block["type"], "input_audio")
        self.assertEqual(audio_block["input_audio"]["data"], "data:audio/wav;base64,AAAA")
        self.assertEqual(payload["asr_options"], {"enable_itn": False, "language": "zh"})

    def test_openai_compatible_audio_transcriber_extracts_text(self):
        transcriber = OpenAICompatibleAudioTranscriber(
            model_name="qwen3-asr-flash",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="test-key",
            enabled=True,
        )

        text = transcriber._extract_api_text(
            {"choices": [{"message": {"content": "你好"}}]}
        )

        self.assertEqual(text, "你好")


if __name__ == "__main__":
    unittest.main()
