from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "Chatchat API"
    database_url: str = "sqlite:///./storage/app.db"
    media_root: str = "./storage/media"
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model_allowlist: str = ""
    openai_vision_model_allowlist: str = ""
    default_provider: str = "ollama"
    default_model: str = "qwen2.5:7b"
    image_max_upload_count: int = 4
    image_max_upload_size_bytes: int = 8 * 1024 * 1024
    image_ocr_min_confidence: float = 0.55
    image_text_max_chars: int = 4800
    image_vision_model: str = "AI-ModelScope/Florence-2-base-ft"
    image_vision_prompt: str = "<MORE_DETAILED_CAPTION>"
    image_vision_max_new_tokens: int = 320
    image_vision_num_beams: int = 4
    image_vision_summary_max_chars: int = 1200
    image_vision_device: str = "auto"
    request_timeout_seconds: float = 180.0
    retrieval_context_top_k: int = 6
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
    web_search_translation_model: str = "ollama:translategemma"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

