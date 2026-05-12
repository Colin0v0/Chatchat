from app.core.config import settings
from pathlib import Path

from app.providers import catalog
from app.providers.catalog import build_model_options, resolve_model_profile, resolve_reasoning_profile


def test_catalog_resolves_known_model_profile():
    profile = resolve_model_profile("codex:gpt-5.2")

    assert profile is not None
    assert profile.id == "codex:gpt-5.2"
    assert profile.provider_family == "openai"
    assert profile.upstream_model == "gpt-5.2"


def test_catalog_builds_frontend_model_options():
    options = build_model_options()

    assert options
    codex_option = next(option for option in options if option["id"] == "codex:gpt-5.2")
    assert codex_option["reasoning_control"] == "effort"
    assert codex_option["default_reasoning_profile"] == "medium"
    assert codex_option["capabilities"]["input"]["pdf"] is True
    assert codex_option["capabilities"]["stream"]["reasoning"] is True
    assert codex_option["capabilities"]["reasoning"]["visibility"] == "summary"
    assert codex_option["capabilities"]["reasoning"]["supported_profiles"] == [
        "auto",
        "low",
        "medium",
        "high",
        "max",
    ]


def test_reasoning_profile_force_off_maps_to_off():
    profile = resolve_reasoning_profile("codex:gpt-5.2", False)

    assert profile == "medium"


def test_reasoning_profile_explicit_request_wins_over_boolean_toggle():
    profile = resolve_reasoning_profile(
        "codex:gpt-5.2",
        False,
        requested_profile="high",
    )

    assert profile == "high"


def test_deepseek_models_do_not_expose_reasoning_selection():
    options = build_model_options()
    profile = resolve_model_profile("openai:deepseek-v4-flash")

    deepseek_reasoner = next(option for option in options if option["id"] == "openai:deepseek-v4-pro")
    deepseek_chat = next(option for option in options if option["id"] == "openai:deepseek-v4-flash")

    assert profile is not None
    assert profile.chat_base_url == settings.deepseek_base_url
    assert deepseek_reasoner["reasoning_control"] == "none"
    assert deepseek_reasoner["default_reasoning_profile"] == "off"
    assert deepseek_reasoner["capabilities"]["reasoning"]["visibility"] == "full"
    assert deepseek_reasoner["capabilities"]["input"]["image"] is False
    assert deepseek_chat["reasoning_control"] == "none"
    assert deepseek_chat["capabilities"]["reasoning"]["visibility"] == "summary"
    assert deepseek_chat["capabilities"]["input"]["image"] is False


def test_reasoning_profile_rejects_unsupported_off_profile_by_falling_back_to_default():
    profile = resolve_reasoning_profile(
        "gemini:gemini-3.1-pro-high",
        None,
        requested_profile="off",
    )

    assert profile == "auto"


def test_model_catalog_profiles_are_cached_by_file_fingerprint(tmp_path, monkeypatch):
    catalog_path = tmp_path / "models.json"
    source_catalog_path = Path(__file__).resolve().parents[1] / "model_catalog.json"
    catalog_path.write_text(source_catalog_path.read_text(encoding="utf-8"), encoding="utf-8")
    read_count = 0
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        nonlocal read_count
        if self == catalog_path:
            read_count += 1
        return original_read_text(self, *args, **kwargs)

    catalog.clear_model_catalog_cache()
    monkeypatch.setattr(catalog.settings, "model_catalog_path", str(catalog_path))
    monkeypatch.setattr(Path, "read_text", counting_read_text)

    assert catalog.resolve_model_profile("codex:gpt-5.2") is not None
    assert catalog.resolve_model_profile("codex:gpt-5.2") is not None
    assert read_count == 1

    catalog.clear_model_catalog_cache()
