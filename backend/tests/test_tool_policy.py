from app.tools import build_tool_policy


def test_build_tool_policy_maps_none_to_off():
    policy = build_tool_policy("none")

    assert policy.mode == "off"
    assert policy.source_mode == "none"
    assert policy.is_enabled is False
    assert policy.requested_tools == ()


def test_build_tool_policy_maps_search_to_requested_tool():
    policy = build_tool_policy("search")

    assert policy.mode == "search"
    assert policy.source_mode == "search"
    assert policy.is_enabled is True
    assert policy.requested_tools == ("search",)


def test_tool_policy_serializes_external_and_internal_selection():
    policy = build_tool_policy("knowledge")

    assert policy.to_metadata() == {
        "tool_mode": "knowledge",
        "tool_policy": "knowledge",
    }
    assert policy.to_context_payload() == {
        "tool_mode": "knowledge",
        "tool_policy": "knowledge",
        "tool_plan": ["knowledge"],
        "knowledge_folders": [],
    }
