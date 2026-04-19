import logging
import unittest

from app.audio.transcriber import AudioTranscriber


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


if __name__ == "__main__":
    unittest.main()
