
from engine.quality import validate_script


def test_validate_preserves_scene_metadata():

    data = {
        "title": ["Demo"],
        "scenes": [
            {
                "narration": "A factual sentence.",
                "visual_query": "ancient map"
            }
        ]
    }

    validate_script(data)

    assert data["scenes"][0]["visual_query"] == "ancient map"
    assert data["word_count"] == 3


def test_validate_accepts_string_title():

    data = {
        "title": "A Documentary About History",
        "scenes": [
            {
                "narration": "History is important."
            }
        ]
    }

    validate_script(data)

    assert data["title"] == ["A Documentary About History"]


def test_validate_accepts_list_title():

    data = {
        "title": ["The Ancient World", "Before Islam"],
        "scenes": [
            {
                "narration": "History is important."
            }
        ]
    }

    validate_script(data)

    assert data["title"] == ["The Ancient World", "Before Islam"]
