from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from PIL import Image


@dataclass(frozen=True)
class VisionDescription:
    summary: str


class ImageVision:
    def __init__(
        self,
        *,
        model_name: str,
        prompt: str,
        max_new_tokens: int,
        num_beams: int,
        device: str,
    ):
        self._model_name = model_name.strip()
        self._prompt = prompt.strip()
        self._max_new_tokens = max_new_tokens
        self._num_beams = num_beams
        self._device_preference = device.strip() or "auto"
        self._lock = Lock()
        self._processor = None
        self._model = None
        self._device = None
        self._torch_dtype = None

    def describe(self, image_path: Path) -> VisionDescription:
        processor, model = self._ensure_runtime()
        image = Image.open(image_path).convert("RGB")
        inputs = processor(text=self._prompt, images=image, return_tensors="pt")
        inputs = inputs.to(self._device, self._torch_dtype)

        import torch

        with torch.inference_mode():
            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=self._max_new_tokens,
                num_beams=self._num_beams,
                do_sample=False,
            )

        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(
            generated_text,
            task=self._prompt,
            image_size=(image.width, image.height),
        )
        summary = self._extract_summary(parsed)
        if not summary:
            raise RuntimeError("The local vision model returned an empty image description.")
        return VisionDescription(summary=summary)

    def _ensure_runtime(self):
        if self._processor is not None and self._model is not None:
            return self._processor, self._model

        with self._lock:
            if self._processor is not None and self._model is not None:
                return self._processor, self._model

            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoProcessor
            except ImportError as exc:
                raise RuntimeError(
                    "Local vision dependencies are missing. Install torch and transformers in the backend environment."
                ) from exc

            self._device = self._resolve_device(torch)
            self._torch_dtype = torch.float16 if self._device.startswith("cuda") else torch.float32
            model_path = self._resolve_model_path()

            self._processor = AutoProcessor.from_pretrained(
                model_path,
                trust_remote_code=True,
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=self._torch_dtype,
            ).to(self._device)
            self._model.eval()
            return self._processor, self._model

    def _resolve_device(self, torch_module) -> str:
        if self._device_preference == "auto":
            return "cuda" if torch_module.cuda.is_available() else "cpu"
        return self._device_preference

    def _resolve_model_path(self) -> str:
        candidate = Path(self._model_name)
        if candidate.exists():
            return str(candidate)

        try:
            from modelscope import snapshot_download
        except ImportError as exc:
            raise RuntimeError(
                "ModelScope is required to download the local vision model. Install modelscope in the backend environment."
            ) from exc

        return snapshot_download(self._model_name)

    def _extract_summary(self, parsed: object) -> str:
        if isinstance(parsed, dict):
            value = parsed.get(self._prompt, "")
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, list):
                return " ".join(str(item).strip() for item in value if str(item).strip()).strip()
        if isinstance(parsed, str):
            return parsed.strip()
        return ""
