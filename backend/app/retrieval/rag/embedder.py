from __future__ import annotations

import asyncio
import gc
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...core.config import Settings
from ...core.idle_runtime import IdleRuntime
from .types import RagChunk, RagChunkSpec

logger = logging.getLogger("chatchat.embedding")
BACKEND_DIR = Path(__file__).resolve().parents[3]
MODELS_DIR = BACKEND_DIR / "models"
WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


class KnowledgeEmbedder(Protocol):
    async def embed_query(self, query: str) -> list[float]:
        ...

    async def embed_chunk_specs(
        self, chunk_specs: list[RagChunkSpec]
    ) -> tuple[list[RagChunk], int]:
        ...


def build_knowledge_embedder(settings: Settings, embedding_model: str) -> KnowledgeEmbedder:
    normalized = embedding_model.strip()
    if not normalized:
        raise RuntimeError(
            "KNOWLEDGE_EMBEDDING_MODEL is required for local knowledge embedding."
        )
    return LocalModelEmbedder(settings, normalized)


@dataclass(frozen=True)
class LocalEmbeddingRuntime:
    tokenizer: object
    model: object
    device: str


class LocalModelEmbedder:
    def __init__(self, settings: Settings, embedding_model: str):
        self._embedding_model = embedding_model
        self._batch_size = max(1, int(getattr(settings, "knowledge_embedding_batch_size", 8)))
        self._max_length = max(64, int(getattr(settings, "knowledge_embedding_max_length", 2048)))
        self._device_preference = str(getattr(settings, "knowledge_embedding_device", "auto")).strip() or "auto"
        self._runtime = IdleRuntime(
            runtime_name="knowledge.embedding",
            loader=self._load_runtime,
            unloader=self._unload_runtime,
            idle_timeout_seconds=float(getattr(settings, "local_model_idle_timeout_seconds", 60.0)),
        )

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await asyncio.to_thread(self._embed_texts_sync, [query])
        return embeddings[0] if embeddings else []

    async def embed_chunk_specs(
        self, chunk_specs: list[RagChunkSpec]
    ) -> tuple[list[RagChunk], int]:
        if not chunk_specs:
            return [], 0

        texts = [f"{chunk.path}\n## {chunk.heading}\n{chunk.content}" for chunk in chunk_specs]
        embeddings = await asyncio.to_thread(self._embed_texts_sync, texts)
        embedded_chunks = [
            RagChunk(
                id=chunk.id,
                path=chunk.path,
                directory=chunk.directory,
                heading=chunk.heading,
                content=chunk.content,
                order=chunk.order,
                embedding=embedding,
                tags=list(chunk.tags),
            )
            for chunk, embedding in zip(chunk_specs, embeddings, strict=False)
        ]
        failed_chunks = max(0, len(chunk_specs) - len(embedded_chunks))
        return embedded_chunks, failed_chunks

    def _embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        normalized_texts = [text.strip() for text in texts if text.strip()]
        if not normalized_texts:
            return []

        with self._runtime.lease() as runtime:
            import torch

            vectors: list[list[float]] = []
            for start in range(0, len(normalized_texts), self._batch_size):
                batch = normalized_texts[start : start + self._batch_size]
                encoded = runtime.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self._max_length,
                    return_tensors="pt",
                )
                encoded = {key: value.to(runtime.device) for key, value in encoded.items()}

                with torch.inference_mode():
                    outputs = runtime.model(**encoded)
                embeddings = self._extract_embeddings(
                    outputs=outputs,
                    attention_mask=encoded.get("attention_mask"),
                    torch_module=torch,
                )
                normalized = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                vectors.extend(normalized.detach().cpu().tolist())

            return [[float(value) for value in vector] for vector in vectors]

    def _load_runtime(self) -> LocalEmbeddingRuntime:
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Local embedding dependencies are unavailable. Install compatible torch/transformers packages."
            ) from exc

        model_path = self._resolve_model_path()
        device = self._resolve_device(torch)
        load_kwargs: dict[str, object] = {"trust_remote_code": True}
        if device.startswith("cuda"):
            load_kwargs["torch_dtype"] = torch.float16

        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
        )
        model = AutoModel.from_pretrained(
            model_path,
            **load_kwargs,
        ).to(device)
        model.eval()
        logger.info(
            "local embedding runtime ready | requested=%s | resolved=%s | device=%s",
            self._embedding_model,
            model_path,
            device,
        )
        return LocalEmbeddingRuntime(
            tokenizer=tokenizer,
            model=model,
            device=device,
        )

    def _unload_runtime(self, runtime: LocalEmbeddingRuntime) -> None:
        device = runtime.device
        del runtime
        gc.collect()
        if device.startswith("cuda"):
            try:
                import torch
            except ImportError:
                return
            torch.cuda.empty_cache()

    def _resolve_model_path(self) -> str:
        normalized = self._embedding_model
        if normalized.startswith("local:"):
            normalized = normalized.split(":", 1)[1].strip()

        candidate = Path(normalized)

        if candidate.is_absolute() or WINDOWS_DRIVE_PATH_PATTERN.match(normalized):
            if not candidate.exists():
                raise RuntimeError(f"Local embedding model path does not exist: {candidate}")
            return str(candidate)

        if normalized.startswith(("./", "../", ".\\", "..\\")):
            resolved = (BACKEND_DIR / candidate).resolve()
            if not resolved.exists():
                raise RuntimeError(f"Local embedding model path does not exist: {resolved}")
            return str(resolved)

        mapped = self._resolve_by_models_dir_alias(normalized)
        if mapped is not None:
            return str(mapped)

        named_relative = (BACKEND_DIR / normalized).resolve()
        if named_relative.exists():
            return str(named_relative)

        raise RuntimeError(
            "Local embedding model path was not found. "
            f"Set KNOWLEDGE_EMBEDDING_MODEL to an existing local directory. Requested: {self._embedding_model}"
        )

    def _resolve_by_models_dir_alias(self, model_name: str) -> Path | None:
        if not MODELS_DIR.exists():
            return None

        direct = MODELS_DIR / model_name
        if direct.exists():
            return direct

        normalized_target = _normalize_alias(model_name)
        if not normalized_target:
            return None

        candidates = [item for item in MODELS_DIR.iterdir() if item.is_dir()]
        scored: list[tuple[int, Path]] = []
        for item in candidates:
            normalized_candidate = _normalize_alias(item.name)
            if not normalized_candidate:
                continue
            if normalized_candidate == normalized_target:
                scored.append((0, item))
                continue
            if normalized_candidate.startswith(normalized_target) or normalized_target.startswith(normalized_candidate):
                score = abs(len(normalized_candidate) - len(normalized_target))
                scored.append((score + 10, item))

        if not scored:
            return None
        scored.sort(key=lambda pair: pair[0])
        return scored[0][1]

    def _resolve_device(self, torch_module) -> str:
        if self._device_preference == "auto":
            return "cuda" if torch_module.cuda.is_available() else "cpu"
        return self._device_preference

    def _extract_embeddings(self, *, outputs: object, attention_mask, torch_module):
        direct_embeddings = getattr(outputs, "embeddings", None)
        if isinstance(direct_embeddings, torch_module.Tensor):
            return direct_embeddings

        sentence_embeddings = getattr(outputs, "sentence_embeddings", None)
        if isinstance(sentence_embeddings, torch_module.Tensor):
            return sentence_embeddings

        token_embeddings = getattr(outputs, "last_hidden_state", None)
        if token_embeddings is None and isinstance(outputs, (tuple, list)) and outputs:
            token_embeddings = outputs[0]
        if not isinstance(token_embeddings, torch_module.Tensor):
            raise RuntimeError("Local embedding model did not return usable hidden states.")
        if attention_mask is None:
            raise RuntimeError("Local embedding tokenizer did not provide an attention mask.")

        expanded_mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        masked_embeddings = token_embeddings * expanded_mask
        summed_embeddings = masked_embeddings.sum(dim=1)
        mask_sums = expanded_mask.sum(dim=1).clamp(min=1e-9)
        return summed_embeddings / mask_sums


def _normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())
