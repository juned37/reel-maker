"""Tests for documentary scripts, illustrations and transitions."""

import json
from pathlib import Path

import pytest
from PIL import Image

from art import ELEMENTS, make_element, parse_spec
from engine.quality import validate_script, count_words
from engine.illustrations import (
    render_visual_plan,
    validate_visual_plan,
)
from engine.transitions import (
    crossfade,
    transition_name,
    apply_transition,
)
from reel import build_legacy_art_elements


def valid_visual_plan():
    return {
        "elements": [
            {
                "type": "circle",
                "x": 50,
                "y": 45,
                "size": 20,
                "color": "gold",
                "fill": "pale",
                "draw_at": 0,
                "draw_duration": 0.3,
            },
            {
                "type": "line",
                "points": [[20, 50], [80, 50]],
                "color": "ink",
                "draw_at": 0.3,
                "draw_duration": 0.4,
            },
        ]
    }


def valid_script():
    return {
        "title": ["Test Documentary"],
        "claims_to_verify": ["Verify the date."],
        "visual_style": "illustrated",
        "scenes": [
            {
                "narration": "This is a test narration.",
                "onscreen_title": "Test narration",
                "show": [],
                "visual_query": "historical map",
                "visual_plan": valid_visual_plan(),
                "camera": "slow_push",
                "transition": "crossfade",
            }
        ],
    }


def test_validate_preserves_scene_metadata():
    data = valid_script()
    result = validate_script(data)

    assert result["scenes"][0]["show"] == []
    assert result["scenes"][0]["visual_query"] == "historical map"
    assert result["scenes"][0]["camera"] == "slow_push"
    assert result["scenes"][0]["transition"] == "crossfade"
    assert result["scenes"][0]["visual_plan"]["elements"]


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


def test_visual_plan_accepts_different_subjects():
    space_plan = {
        "elements": [
            {"type": "circle", "x": 50, "y": 45, "size": 20},
            {
                "type": "arc",
                "x": 50,
                "y": 45,
                "size": 65,
                "draw_at": 0.2,
            },
        ]
    }

    history_plan = {
        "elements": [
            {
                "type": "polygon",
                "points": [[20, 60], [50, 25], [80, 60]],
                "fill": "pale",
            },
            {
                "type": "rect",
                "x": 50,
                "y": 65,
                "size": 35,
            },
        ]
    }

    validate_visual_plan(space_plan)
    validate_visual_plan(history_plan)


def test_invalid_visual_type_is_rejected():
    plan = {"elements": [{"type": "photograph"}]}

    with pytest.raises(ValueError, match="Unsupported"):
        validate_visual_plan(plan)


def test_invalid_visual_coordinates_are_rejected():
    plan = {
        "elements": [
            {
                "type": "line",
                "points": [[-5, 20], [50, 50]],
            }
        ]
    }

    with pytest.raises(ValueError, match="Points"):
        validate_visual_plan(plan)


def test_visual_plan_rejects_too_many_elements():
    plan = {
        "elements": [
            {"type": "circle", "x": 50, "y": 50, "size": 5}
            for _ in range(36)
        ]
    }

    with pytest.raises(ValueError, match="35"):
        validate_visual_plan(plan)


def test_visual_plan_draws_on_frame():
    frame = Image.new(
        "RGB",
        (1080, 1920),
        (246, 237, 224)
    )

    result = render_visual_plan(
        frame,
        valid_visual_plan(),
        1.0
    )

    assert result.size == (1080, 1920)
    assert result.mode == "RGB"
    assert result.tobytes() != frame.tobytes()


def test_visual_plan_reveals_progressively():
    frame = Image.new(
        "RGB",
        (1080, 1920),
        (246, 237, 224)
    )
    plan = valid_visual_plan()

    early = render_visual_plan(
        frame.copy(),
        plan,
        0.0
    )
    late = render_visual_plan(
        frame.copy(),
        plan,
        1.0
    )

    assert early.tobytes() != late.tobytes()


def test_missing_visual_plan_remains_compatible():
    data = valid_script()
    del data["scenes"][0]["visual_plan"]

    validate_script(data)


def test_underscore_asset_specification_is_parsed():
    name, argument, position = parse_spec("prayer_mat@left")

    assert name == "prayer_mat"
    assert argument is None
    assert position == "left"


def test_all_registered_art_assets_can_be_built():
    for name in sorted(ELEMENTS):
        if name == "text":
            spec = "text:TEST|SUBTITLE@center"
        elif name == "figures":
            spec = "figures:3"
        elif name == "arches":
            spec = "arches:3"
        else:
            spec = f"{name}@center"

        image, position = make_element(spec)

        assert image is not None
        assert image.width > 0
        assert image.height > 0
        assert isinstance(position, tuple)
        assert len(position) == 2


def test_invalid_show_asset_is_rejected():
    data = valid_script()
    data["scenes"][0]["show"] = ["not_a_real_asset"]

    with pytest.raises(ValueError, match="invalid illustration"):
        validate_script(data)


def test_duplicate_show_positions_are_rejected():
    data = valid_script()
    data["scenes"][0]["show"] = [
        "book@left",
        "map@left",
    ]

    with pytest.raises(ValueError, match="position"):
        validate_script(data)


def test_fixed_assets_must_be_used_alone():
    data = valid_script()
    data["scenes"][0]["show"] = [
        "figures:3",
        "book@right",
    ]

    with pytest.raises(ValueError, match="must be used on its own"):
        validate_script(data)


def test_figures_count_must_be_in_range():
    data = valid_script()
    data["scenes"][0]["show"] = ["figures:7"]

    with pytest.raises(ValueError, match="between 1 and 6"):
        validate_script(data)


def test_text_illustration_is_validated():
    data = valid_script()
    data["scenes"][0]["show"] = [
        "text:TEST|SUBTITLE@center"
    ]

    validate_script(data)

    image, position = make_element(
        "text:TEST|SUBTITLE@center"
    )

    assert image.width > 0
    assert image.height > 0
    assert isinstance(position, tuple)


def test_scene_art_is_kept_separate():
    scenes = [
        {"show": ["book@left"]},
        {"show": ["map@right"]},
    ]

    timeline = [
        {"start": 1.2, "end": 5.0},
        {"start": 5.0, "end": 9.0},
    ]

    result = build_legacy_art_elements(
        scenes,
        timeline
    )

    assert len(result) == 2
    assert len(result[0]) == 1
    assert len(result[1]) == 1

    assert result[0][0]["show"] == pytest.approx(1.35)
    assert result[1][0]["show"] == pytest.approx(5.15)

    assert result[0][0]["x"] != result[1][0]["x"]


def test_empty_scene_art_returns_empty_scene_list():
    scenes = [{"show": []}]
    timeline = [{"start": 1.2, "end": 5.0}]

    result = build_legacy_art_elements(
        scenes,
        timeline
    )

    assert result == [[]]


def test_scene_and_timeline_length_must_match():
    with pytest.raises(ValueError, match="must match"):
        build_legacy_art_elements(
            [{"show": []}],
            []
        )


def test_world_before_islam_script_exists():
    path = Path("scripts/world-before-islam.json")

    if not path.exists():
        pytest.skip(
            "Example script is not present in this checkout."
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert data["scenes"]
    assert all(
        scene.get("narration")
        for scene in data["scenes"]
    )
