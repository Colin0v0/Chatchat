from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float


class ImageOcr:
    def __init__(self, *, min_confidence: float):
        self._min_confidence = min_confidence
        self._engine = RapidOCR()

    def extract_lines(self, image_path: Path) -> list[OcrLine]:
        result, _ = self._engine(image_path)
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
