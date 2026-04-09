import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


def _read_env_name_from_file(path: Path) -> str:
    if not path.exists():
        return ""

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key not in {"CHATCHAT_ENV", "APP_ENV"}:
            continue
        return value.strip().strip("\"'")
    return ""


def _resolve_env_files() -> tuple[str, ...]:
    env_files: list[str] = []
    explicit_file = os.getenv("CHATCHAT_ENV_FILE", "").strip()
    env_name = (
        os.getenv("CHATCHAT_ENV", "").strip()
        or os.getenv("APP_ENV", "").strip()
        or _read_env_name_from_file(ENV_FILE)
    )

    if ENV_FILE.exists():
        env_files.append(str(ENV_FILE))

    if env_name:
        named_env_file = BASE_DIR / f".env.{env_name}"
        if not named_env_file.exists():
            raise RuntimeError(f"CHATCHAT_ENV points to a missing env file: {named_env_file}")
        env_files.append(str(named_env_file))

    if explicit_file:
        for raw_path in explicit_file.split(os.pathsep):
            trimmed_path = raw_path.strip()
            if not trimmed_path:
                continue
            candidate = Path(trimmed_path)
            resolved = candidate if candidate.is_absolute() else BASE_DIR / candidate
            if not resolved.exists():
                raise RuntimeError(f"CHATCHAT_ENV_FILE points to a missing env file: {resolved}")
            env_files.append(str(resolved))

    return tuple(dict.fromkeys(env_files))


class Settings(BaseSettings):
    app_env: str = "default"
    app_name: str = "Chatchat API"
    cors_allowed_origins: str = "http://127.0.0.1:5200,http://localhost:5200"
    database_url: str = "sqlite:///./storage/app.db"
    media_root: str = "./storage/media"
    auth_session_cookie_name: str = "chatchat_session"
    auth_session_ttl_hours: int = 168
    auth_cookie_secure: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model_denylist: str = ""
    ollama_keep_alive_seconds: int = 0
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model_allowlist: str = ""
    openai_local_base_url: str = "http://127.0.0.1:18000/v1"
    openai_local_upstream_service_base_url: str = ""
    openai_local_api_key: str = ""
    openai_local_model_allowlist: str = ""
    openai_local_stream: bool = True
    model_catalog_path: str = "./model_catalog.json"
    model_catalog_strict: bool = True
    default_provider: str = "ollama"
    default_model: str = "qwen2.5:7b"
    attachment_max_upload_count: int = 8
    attachment_max_upload_size_bytes: int = 20 * 1024 * 1024
    image_ocr_min_confidence: float = 0.45
    image_text_max_chars: int = 4800
    image_vision_model: str = "AI-ModelScope/Florence-2-base-ft"
    image_vision_prompt: str = "<MORE_DETAILED_CAPTION>"
    image_vision_max_new_tokens: int = 320
    image_vision_num_beams: int = 4
    image_vision_summary_max_chars: int = 1200
    image_vision_device: str = "auto"
    file_text_max_chars: int = 6000
    file_table_row_limit: int = 40
    file_table_column_limit: int = 24
    attachment_processing_max_concurrency: int = 2
    audio_transcription_enabled: bool = True
    audio_transcription_eager_load: bool = False
    audio_transcription_model: str = "iic/SenseVoiceSmall"
    audio_transcription_device: str = "cpu"
    audio_max_upload_size_bytes: int = 25 * 1024 * 1024
    local_model_idle_timeout_seconds: float = 60.0
    request_timeout_seconds: float = 180.0
    openai_connect_timeout_seconds: float = 30.0
    http_pool_max_connections: int = 100
    http_pool_max_keepalive_connections: int = 20
    openai_http_max_concurrency: int = 8
    openai_local_http_max_concurrency: int = 4
    ollama_http_max_concurrency: int = 4
    web_search_http_max_concurrency: int = 4
    model_max_concurrency_per_model: int = 3
    chat_history_message_limit: int = 14
    chat_history_token_budget: int = 3600
    chat_summary_token_budget: int = 1200
    conversation_view_message_limit: int = 10
    memory_model: str = ""
    memory_recall_top_k: int = 4
    memory_pinned_top_k: int = 3
    memory_extract_max_items: int = 6
    memory_refresh_max_concurrency: int = 1
    retrieval_context_top_k: int = 6
    file_retrieval_top_k: int = 3
    file_retrieval_chunk_token_limit: int = 220
    file_retrieval_min_score: float = 0.18
    rag_vault_path: str = "/data/obsidian"
    rag_index_path: str = "./storage/rag/index.json"
    rag_embedding_model: str = "nomic-embed-text"
    rag_top_k: int = 4
    rag_section_max_chars: int = 1400
    rag_candidate_limit: int = 12
    rag_rerank_window: int = 12
    rag_neighbor_window: int = 1
    rag_min_score: float = 0.22
    web_search_base_url: str = "https://api.tavily.com"
    web_search_api_key: str = ""
    web_search_timeout_seconds: float = 20.0
    web_search_max_results: int = 5
    web_search_top_k: int = 4
    web_search_min_score: float = 0.35
    web_search_content_max_chars: int = 1600
    web_search_translation_model: str = "openai_local:claude-haiku-4-5"
    conversation_title_max_length: int = 40

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


settings = Settings(_env_file=_resolve_env_files())
