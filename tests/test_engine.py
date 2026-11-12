
"""Tests for documentary script validation and video transitions."""

import pytest
from PIL import Image

from engine.quality import validate_script, count_words
from engine.transitions import (
    crossfade,
    transition_name,
    apply_transition,
)


def valid_script():
    return {
        "title": ["Test Documentary"],
        "claims_to_verify": ["Verify the date."],
        "scenes": [
            {
                "narration": "This is a test narration.",
                "onscreen_title": "Test narration",
                "show": ["globe"],
                "visual_query": "historical map",
                "camera": "slow_push",
                "transition": "crossfade",
            }
        ],
    }


def test_validate_preserves_scene_metadata():
    data = valid_script()
    result = validate_script(data)

    assert result["scenes"][0]["show"] == ["globe"]
    assert result["scenes"][0]["visual_query"] == "historical map"
    assert result["scenes"][0]["camera"] == "slow_push"
    assert result["scenes"][0]["transition"] == "crossfade"


def test_string_title_is_normalised():
    data = valid_script()
    data["title"] = "A Documentary"

    validate_script(data)

    assert data["title"] == ["A Documentary"]


def test_list_title_is_preserved():
    data = valid_script()

    validate_script(data)

    assert data["title"] == ["Test Documentary"]


def test_empty_title_is_rejected():
    data = valid_script()
    data["title"] = []

    with pytest.raises(ValueError, match="title"):
        validate_script(data)


def test_empty_scenes_are_rejected():
    data = valid_script()
    data["scenes"] = []

    with pytest.raises(ValueError, match="scenes"):
        validate_script(data)


def test_empty_narration_is_rejected():
    data = valid_script()
    data["scenes"][0]["narration"] = " "

    with pytest.raises(ValueError, match="narration"):
        validate_script(data)


def test_invalid_camera_is_rejected():
    data = valid_script()
    data["scenes"][0]["camera"] = "rotate"

    with pytest.raises(ValueError, match="camera"):
        validate_script(data)


def test_vertical_camera_movements_are_supported():
    data = valid_script()
    data["scenes"][0]["camera"] = "pan_up"

    validate_script(data)

    assert data["scenes"][0]["camera"] == "pan_up"


def test_invalid_transition_is_rejected():
    data = valid_script()
    data["scenes"][0]["transition"] = "wipe"

    with pytest.raises(ValueError, match="transition"):
        validate_script(data)


def test_missing_onscreen_title_gets_safe_fallback():
    data = valid_script()
    del data["scenes"][0]["onscreen_title"]

    validate_script(data)

    assert (
        data["scenes"][0]["onscreen_title"]
        == "This is a test narration"
    )


def test_count_words():
    assert count_words("The world before Islam.") == 4


def test_transition_name_defaults_to_crossfade():
    assert transition_name({}) == "crossfade"


def test_transition_name_accepts_cut():
    assert transition_name({"transition": "cut"}) == "cut"


def test_crossfade_midpoint():
    first = Image.new("RGB", (10, 10), (0, 0, 0))
    second = Image.new("RGB", (10, 10), (100, 100, 100))

    result = crossfade(first, second, 0.5)

    assert result.getpixel((0, 0)) == (50, 50, 50)


def test_cut_returns_current_frame():
    first = Image.new("RGB", (10, 10), (0, 0, 0))
    second = Image.new("RGB", (10, 10), (100, 100, 100))

    result = apply_transition(first, second, "cut", 0.5)

    assert result.getpixel((0, 0)) == (100, 100, 100)


def test_target_duration_rejects_too_short_script():
    data = valid_script()

    with pytest.raises(ValueError, match="words"):
        validate_script(data, target_minutes=3)


def test_claims_to_verify_must_be_a_list():
    data = valid_script()
    data["claims_to_verify"] = "not a list"

    with pytest.raises(ValueError, match="claims_to_verify"):
        validate_script(data)


def test_world_before_islam_script_defaults_to_editorial():
    import json
    from pathlib import Path

    data = json.loads(
        Path("scripts/world-before-islam.json").read_text(
            encoding="utf-8"
        )
    )

    assert data["visual_style"] == "editorial"
    assert all(
        scene.get("onscreen_title")
        for scene in data["scenes"]
    )
