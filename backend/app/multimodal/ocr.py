from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import gc

from ..core.idle_runtime import IdleRuntime


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float


class ImageOcr:
    def __init__(self, *, min_confidence: float, idle_timeout_seconds: float):
        self._min_confidence = min_confidence
        self._runtime = IdleRuntime(
            runtime_name="image.ocr",
            loader=self._load_engine,
            unloader=self._unload_engine,
            idle_timeout_seconds=idle_timeout_seconds,
        )

    def extract_lines(self, image_path: Path) -> list[OcrLine]:
        with self._runtime.lease() as engine:
            result, _ = engine(image_path)
        if not result:
            return []

        lines: list[OcrLine] = []
        for item in result:
            if len(item) < 3:
                continue

            text = str(item[1]).strip()
            confidence = float(item[2])
            if not text or confidence < self._min_confidence:
                continue

            lines.append(OcrLine(text=text, confidence=confidence))
        return lines

    def _load_engine(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise RuntimeError(
                "rapidocr-onnxruntime is required for image OCR. "
                f"Install backend dependencies first. Original error: {exc}"
            ) from exc

        return RapidOCR()

    def _unload_engine(self, engine) -> None:
        del engine
        gc.collect()
