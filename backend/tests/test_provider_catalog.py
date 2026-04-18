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
    assert codex_option["default_reasoning_profile"] == "off"
    assert codex_option["capabilities"]["input"]["pdf"] is True
    assert codex_option["capabilities"]["stream"]["reasoning"] is True


def test_reasoning_profile_force_off_maps_to_off():
    profile = resolve_reasoning_profile("codex:gpt-5.2", False)

    assert profile == "off"


def test_reasoning_profile_explicit_request_wins_over_boolean_toggle():
    profile = resolve_reasoning_profile(
        "openai:deepseek-reasoner",
        False,
        requested_profile="high",
    )

    assert profile == "high"
