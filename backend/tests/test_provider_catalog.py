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

    deepseek_reasoner = next(option for option in options if option["id"] == "openai:deepseek-reasoner")
    deepseek_chat = next(option for option in options if option["id"] == "openai:deepseek-chat")

    assert deepseek_reasoner["reasoning_control"] == "none"
    assert deepseek_reasoner["default_reasoning_profile"] == "off"
    assert deepseek_reasoner["capabilities"]["reasoning"]["visibility"] == "full"
    assert deepseek_chat["reasoning_control"] == "none"
    assert deepseek_chat["capabilities"]["reasoning"]["visibility"] == "summary"


def test_reasoning_profile_rejects_unsupported_off_profile_by_falling_back_to_default():
    profile = resolve_reasoning_profile(
        "gemini:gemini-3.1-pro-high",
        None,
        requested_profile="off",
    )

    assert profile == "auto"
