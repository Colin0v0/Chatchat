from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..core.idle_runtime import IdleRuntime


@dataclass(frozen=True)
class VisionDescription:
    summary: str


@dataclass(frozen=True)
class VisionRuntime:
    processor: object
    model: object
    device: str
    torch_dtype: object


class ImageVision:
    def __init__(
        self,
        *,
        model_name: str,
        prompt: str,
        max_new_tokens: int,
        num_beams: int,
        device: str,
        idle_timeout_seconds: float,
    ):
        self._model_name = model_name.strip()
        self._prompt = prompt.strip()
        self._max_new_tokens = max_new_tokens
        self._num_beams = num_beams
        self._device_preference = device.strip() or "auto"
        self._runtime = IdleRuntime(
            runtime_name="image.vision",
            loader=self._load_runtime,
            unloader=self._unload_runtime,
            idle_timeout_seconds=idle_timeout_seconds,
        )

    def describe(self, image_path: Path) -> VisionDescription:
        if not self._model_name:
            raise RuntimeError("Local image vision is disabled in the current environment.")
        with self._runtime.lease() as runtime:
            with Image.open(image_path) as image_file:
                image = image_file.convert("RGB")

            inputs = runtime.processor(text=self._prompt, images=image, return_tensors="pt")
            inputs = inputs.to(runtime.device, runtime.torch_dtype)

            import torch

            with torch.inference_mode():
                generated_ids = runtime.model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=self._max_new_tokens,
                    num_beams=self._num_beams,
                    do_sample=False,
                )

            generated_text = runtime.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed = runtime.processor.post_process_generation(
                generated_text,
                task=self._prompt,
                image_size=(image.width, image.height),
            )
        summary = self._extract_summary(parsed)
        if not summary:
            raise RuntimeError("The local vision model returned an empty image description.")
        return VisionDescription(summary=summary)

    def _load_runtime(self) -> VisionRuntime:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Local vision dependencies are unavailable or incompatible. "
                f"Install compatible torch/transformers dependencies in the backend environment. Original error: {exc}"
            ) from exc

        device = self._resolve_device(torch)
        torch_dtype = torch.float16 if device.startswith("cuda") else torch.float32
        model_path = self._resolve_model_path()

        processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
        ).to(device)
        model.eval()
        return VisionRuntime(
            processor=processor,
            model=model,
            device=device,
            torch_dtype=torch_dtype,
        )

    def _unload_runtime(self, runtime: VisionRuntime) -> None:
        if runtime.device.startswith("cuda"):
            try:
                import torch
            except ImportError:
                pass
            else:
                del runtime
                gc.collect()
                torch.cuda.empty_cache()
                return

        del runtime
        gc.collect()

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
