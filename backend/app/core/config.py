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
    cors_allowed_origins: str = "http://127.0.0.1:5200,http://localhost:5200,http://127.0.0.1:3300,http://localhost:3300"
    database_url: str = "postgresql+psycopg://chatchat:chatchat@127.0.0.1:5432/chatchat"
    redis_url: str = "redis://127.0.0.1:6379/0"
    media_root: str = "./storage/media"
    auth_session_cookie_name: str = "chatchat_session"
    auth_session_ttl_hours: int = 168
    auth_cookie_secure: bool = False
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model_allowlist: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_api_key: str = ""
    openai_image_base_url: str = ""
    openai_image_api_key: str = ""
    openai_image_model: str = "gpt-image-2"
    openai_image_size: str = "1024x1024"
    openai_image_quality: str = "auto"
    openai_image_output_format: str = "png"
    openai_image_timeout_seconds: float = 180.0
    trio_base_url: str = "https://pytrio.cn/api/v1"
    trio_api_key: str = ""
    trio_model_path: str = ""
    trio_model_allowlist: str = ""
    claude_base_url: str = "https://api.anthropic.com"
    claude_api_key: str = ""
    claude_model_allowlist: str = ""
    codex_base_url: str = "https://api.openai.com/v1"
    codex_api_key: str = ""
    codex_model_allowlist: str = ""
    codex_use_responses_api: bool = False
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_api_key: str = ""
    gemini_model_allowlist: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: str = ""
    model_catalog_path: str = "./model_catalog.json"
    model_catalog_strict: bool = True
    default_provider: str = "openai"
    default_model: str = "openai:deepseek-v4-flash"
    attachment_max_upload_count: int = 8
    attachment_max_upload_size_bytes: int = 20 * 1024 * 1024
    image_text_max_chars: int = 4800
    file_text_max_chars: int = 6000
    file_table_row_limit: int = 40
    file_table_column_limit: int = 24
    attachment_processing_max_concurrency: int = 2
    audio_transcription_enabled: bool = True
    audio_transcription_base_url: str = ""
    audio_transcription_api_key: str = ""
    audio_transcription_timeout_seconds: float = 60.0
    audio_transcription_api_max_bytes: int = 10 * 1024 * 1024
    audio_transcription_model: str = "qwen3-asr-flash"
    audio_transcription_language: str = "zh"
    audio_transcription_min_duration_ms: int = 300
    audio_transcription_min_rms_dbfs: float = -65.0
    audio_max_upload_size_bytes: int = 25 * 1024 * 1024
    audio_tts_enabled: bool = True
    audio_tts_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
    audio_tts_api_key: str = ""
    audio_tts_timeout_seconds: float = 60.0
    audio_tts_model: str = "cosyvoice-v3-flash"
    audio_tts_voice: str = "longanyang"
    audio_tts_format: str = "mp3"
    audio_tts_sample_rate: int = 24000
    audio_tts_max_chars: int = 3000
    request_timeout_seconds: float = 180.0
    openai_connect_timeout_seconds: float = 30.0
    http_pool_max_connections: int = 100
    http_pool_max_keepalive_connections: int = 20
    claude_http_max_concurrency: int = 8
    openai_http_max_concurrency: int = 8
    web_search_http_max_concurrency: int = 4
    model_max_concurrency_per_model: int = 2
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
    rag_query_rewrite_enabled: bool = True
    rag_query_rewrite_model: str = "codex:gpt-5.2"
    rag_query_rewrite_history_messages: int = 6
    file_retrieval_top_k: int = 3
    file_retrieval_chunk_token_limit: int = 220
    file_retrieval_min_score: float = 0.18
    knowledge_storage_root: str = "./storage/knowledge"
    knowledge_embedding_provider: str = "dashscope"
    knowledge_embedding_base_url: str = ""
    knowledge_embedding_api_key: str = ""
    knowledge_embedding_timeout_seconds: float = 30.0
    knowledge_embedding_model: str = "text-embedding-v4"
    knowledge_embedding_dimensions: int = 1024
    knowledge_embedding_batch_size: int = 8
    knowledge_rerank_provider: str = "dashscope"
    knowledge_rerank_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    knowledge_rerank_api_key: str = ""
    knowledge_rerank_timeout_seconds: float = 30.0
    knowledge_rerank_model: str = "gte-rerank-v2"
    knowledge_rerank_max_chars: int = 480
    knowledge_rerank_max_concurrency: int = 1
    knowledge_max_file_size_bytes: int = 2 * 1024 * 1024
    knowledge_max_documents_per_user: int = 100
    knowledge_max_total_size_bytes: int = 100 * 1024 * 1024
    knowledge_top_k: int = 4
    knowledge_section_max_chars: int = 1400
    knowledge_candidate_limit: int = 4
    knowledge_rerank_window: int = 2
    knowledge_neighbor_window: int = 0
    knowledge_min_score: float = 0.22
    web_search_provider: str = "dashscope"
    web_search_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    web_search_api_key: str = ""
    web_search_timeout_seconds: float = 20.0
    web_search_model: str = "qwen-plus"
    web_search_strategy: str = "turbo"
    web_search_forced: bool = True
    web_search_enable_source: bool = True
    web_search_enable_citation: bool = True
    web_search_citation_format: str = "[ref_<number>]"
    web_search_max_results: int = 5
    web_search_top_k: int = 4
    web_search_min_score: float = 0.35
    web_search_content_max_chars: int = 1600
    web_search_translation_model: str = "codex:gpt-5.2"
    conversation_title_max_length: int = 40

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


settings = Settings(_env_file=_resolve_env_files())
