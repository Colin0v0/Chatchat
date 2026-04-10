from __future__ import annotations

import os
from pathlib import Path


def configure_model_cache_environment(raw_root: str) -> None:
    root = raw_root.strip()
    if not root:
        return

    cache_root = Path(root)
    if not cache_root.is_absolute():
        cache_root = Path(__file__).resolve().parents[2] / cache_root
    cache_root.mkdir(parents=True, exist_ok=True)

    modelscope_root = cache_root / "modelscope"
    huggingface_root = cache_root / "huggingface"
    torch_root = cache_root / "torch"

    modelscope_root.mkdir(parents=True, exist_ok=True)
    huggingface_root.mkdir(parents=True, exist_ok=True)
    torch_root.mkdir(parents=True, exist_ok=True)

    os.environ["MODELSCOPE_CACHE"] = str(modelscope_root)
    os.environ["HF_HOME"] = str(huggingface_root)
    os.environ["TORCH_HOME"] = str(torch_root)
