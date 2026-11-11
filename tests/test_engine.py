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

    assert (
        data["scenes"][0]["visual_query"]
        == "ancient map"
    )

    assert data["word_count"] == 3
