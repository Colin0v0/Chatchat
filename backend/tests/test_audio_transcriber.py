import logging
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


class _FakeSenseVoiceModel:
    def __init__(self):
        self.vad_model = object()
        self.calls: list[bool] = []

    def generate(self, **_kwargs):
        self.calls.append(self.vad_model is not None)
        if self.vad_model is None:
            return [{"text": "<|zh|><|NEUTRAL|>你好"}]
        return [{"text": ""}]


class AudioTranscriberTests(unittest.TestCase):
    def test_suppress_third_party_info_logs_temporarily_raises_levels_to_warning(self):
        transcriber = AudioTranscriber(
            model_name="test-model",
            device="cpu",
            enabled=True,
        )
        root_logger = logging.getLogger()
        funasr_logger = logging.getLogger("funasr")
        modelscope_logger = logging.getLogger("modelscope")

        original_root_level = root_logger.level
        original_funasr_level = funasr_logger.level
        original_modelscope_level = modelscope_logger.level

        try:
            root_logger.setLevel(logging.INFO)
            funasr_logger.setLevel(logging.NOTSET)
            modelscope_logger.setLevel(logging.INFO)

            with transcriber._suppress_third_party_info_logs():
                self.assertEqual(root_logger.level, logging.WARNING)
                self.assertGreaterEqual(funasr_logger.getEffectiveLevel(), logging.WARNING)
                self.assertEqual(modelscope_logger.level, logging.WARNING)

            self.assertEqual(root_logger.level, logging.INFO)
            self.assertEqual(funasr_logger.level, logging.NOTSET)
            self.assertEqual(modelscope_logger.level, logging.INFO)
        finally:
            root_logger.setLevel(original_root_level)
            funasr_logger.setLevel(original_funasr_level)
            modelscope_logger.setLevel(original_modelscope_level)

    def test_short_audio_is_skipped_before_model_inference(self):
        transcriber = AudioTranscriber(
            model_name="test-model",
            device="cpu",
            enabled=True,
            min_duration_ms=650,
        )
        wav_bytes = _tone_wav(duration_ms=300)

        decision = transcriber._inspect_audio(wav_bytes, duration_ms=300)
        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "too_short")

    def test_silent_audio_is_skipped_before_model_inference(self):
        transcriber = AudioTranscriber(
            model_name="test-model",
            device="cpu",
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
            model_name="test-model",
            device="cpu",
            enabled=True,
            min_duration_ms=650,
            min_rms_dbfs=-52,
        )
        wav_bytes = _tone_wav(duration_ms=1000)

        self.assertFalse(transcriber._should_skip_audio(wav_bytes, duration_ms=1000))

    def test_raw_result_rejects_unwanted_auto_detected_languages(self):
        transcriber = AudioTranscriber(
            model_name="test-model",
            device="cpu",
            enabled=True,
            allowed_languages="zh,en",
        )

        self.assertTrue(transcriber._should_drop_raw_result("<|ja|><|NEUTRAL|>ヱ."))
        self.assertTrue(transcriber._should_drop_raw_result("<|nospeech|><|NEUTRAL|>"))
        self.assertFalse(transcriber._should_drop_raw_result("<|zh|><|NEUTRAL|>你好"))

    def test_low_confidence_short_symbol_transcripts_are_rejected(self):
        transcriber = AudioTranscriber(
            model_name="test-model",
            device="cpu",
            enabled=True,
        )

        self.assertTrue(transcriber._is_low_confidence_transcript("ヱ."))
        self.assertTrue(transcriber._is_low_confidence_transcript("..."))
        self.assertFalse(transcriber._is_low_confidence_transcript("你好"))
        self.assertFalse(transcriber._is_low_confidence_transcript("hello"))

    def test_empty_vad_result_retries_without_vad(self):
        transcriber = AudioTranscriber(
            model_name="test-model",
            device="cpu",
            enabled=True,
        )
        fake_model = _FakeSenseVoiceModel()
        original_vad_model = fake_model.vad_model
        transcriber._model = fake_model
        transcriber._postprocess = lambda _raw_text: "你好"
        transcriber._vad_enabled = True

        text = transcriber._transcribe_wav(_tone_wav(duration_ms=1000))

        self.assertEqual(text, "你好")
        self.assertEqual(fake_model.calls, [True, False])
        self.assertIs(fake_model.vad_model, original_vad_model)

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
