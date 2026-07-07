import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Scene, StoryProject
from app.research import ResearchLogger
from app.services.session_service import SessionService
from app.ui.ui_session_stats import _format_stats
from app.vocabulary_categories import get_vocabulary_category, get_vocabulary_category_columns


class FakeController:
    pass


class FakeAudio:
    pass


class FakeUsers:
    current_user_id = ""

    def get_current_user_name(self):
        return ""


def _rows(path):
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_scene_focus_metadata_serializes_and_loads_from_json():
    scene = Scene(
        id="scene_1",
        title="Scene 1",
        scene_focus_category_id="person",
        scene_focus_category_label="Person / proper name",
        scene_specific_topic="mom",
    )
    project = StoryProject(project_name="Scene Focus", scenes=[scene])

    payload = project.to_dict()
    scene_payload = payload["scenes"][0]

    assert scene_payload["scene_focus_category_id"] == "person"
    assert scene_payload["scene_focus_category_label"] == "Person / proper name"
    assert "content_type" not in scene_payload
    assert "content_type_label" not in scene_payload
    assert "communicative_function" not in scene_payload
    assert "communicative_function_label" not in scene_payload
    assert scene_payload["scene_specific_topic"] == "mom"

    loaded = StoryProject.from_dict(json.loads(json.dumps(payload)))

    assert loaded.scenes[0].scene_focus_category_id == "person"
    assert loaded.scenes[0].scene_focus_category_label == "Person / proper name"
    assert loaded.scenes[0].scene_specific_topic == "mom"


def test_scene_focus_empty_category_serializes_as_null_and_empty_topic():
    scene = Scene(id="scene_1", title="Scene 1")

    payload = scene.to_dict()

    assert payload["scene_focus_category_id"] is None
    assert payload["scene_focus_category_label"] is None
    assert "content_type" not in payload
    assert "communicative_function" not in payload
    assert payload["scene_specific_topic"] == ""


def test_scene_category_catalog_reuses_hotspot_vocabulary_categories():
    columns = get_vocabulary_category_columns()
    flattened = [category["id"] for column in columns for category in column]

    assert flattened[0] == "none"
    assert "person" in flattened
    assert "verb" in flattened
    assert get_vocabulary_category("person")["label"] == "Person / proper name"


def test_scene_legacy_category_and_intermediate_content_type_map_to_scene_category():
    payload = {
        "id": "scene_1",
        "title": "Legacy scene",
        "category": "person",
        "scene_specific_topic": "mom",
    }

    loaded = Scene.from_dict(payload)

    assert loaded.scene_focus_category_id == "person"
    assert loaded.scene_focus_category_label == "Person / proper name"

    intermediate = Scene.from_dict({
        "id": "scene_2",
        "title": "Intermediate scene",
        "content_type": "object",
        "communicative_function": "response",
    })

    assert intermediate.scene_focus_category_id == "noun"
    assert intermediate.scene_focus_category_label == "Noun / object"


def test_scene_properties_dialog_uses_title_category_and_specific_topic_labels():
    source = Path("app/ui_dialogs.py").read_text(encoding="utf-8")

    assert 'tr("title")' in source
    assert 'tr("category")' in source
    assert 'tr("specific_topic")' in source
    assert 'tr("communicative_function")' not in source
    assert 'tr("content_type")' not in source
    assert '"scene_section"' in source
    assert '"image_section"' in source
    assert '"audio_section"' in source
    assert '"preview_section"' in source
    assert 'tr("clinician_quick_annotations")' in source
    assert "get_vocabulary_category_columns" in source


def test_scene_properties_dialog_includes_audio_recording_controls():
    source = Path("app/ui_dialogs.py").read_text(encoding="utf-8")

    assert "record_scene_audio" in source
    assert 'tr("record_audio_button")' in source
    assert 'tr("play_preview_button")' in source
    assert 'title_key="record_scene_audio"' in source


def test_research_logs_include_scene_focus_context(tmp_path):
    scene = Scene(
        id="scene_1",
        title="Scene 1",
        scene_focus_category_id="person",
        scene_focus_category_label="Person / proper name",
        scene_specific_topic="mom",
    )
    project = StoryProject(project_name="Scene Focus", scenes=[scene])
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    research.research_enabled = True
    research.research_ever_enabled = True
    service = SessionService(FakeController(), FakeAudio(), research, FakeUsers())

    service.sync_research_context(project, scene, 0, "user")
    research.log_event(action="key_press", key_raw="MOM", key_type="scene_hotspot", text_inserted="MOM")

    row = _rows(research.session_events_path)[0]

    assert row["scene_focus_category_id"] == "person"
    assert row["scene_focus_category_label"] == "Person / proper name"
    assert "content_type" not in row
    assert "communicative_function" not in row
    assert row["scene_specific_topic"] == "mom"

    summary_path = research.write_session_summary(reason="test")
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["current_scene_focus_category_id"] == "person"
    assert summary["current_scene_focus_category_label"] == "Person / proper name"
    assert "current_scene_communicative_function" not in summary
    assert summary["current_scene_specific_topic"] == "mom"
    assert summary["current_scene"]["scene_focus_category_id"] == "person"
    assert summary["scene_metadata"][0]["scene_focus_category_id"] == "person"
    assert summary["scene_metadata"][0]["scene_focus_category_label"] == "Person / proper name"
    assert summary["scene_metadata"][0]["scene_specific_topic"] == "mom"


def test_session_stats_show_scene_focus_metadata():
    text = _format_stats(
        project_name="Scene Focus",
        current_scene_index=0,
        total_scenes=1,
        rows=0,
        cols=0,
        mode="User",
        research_enabled=True,
        user_name="Therapist",
        session_type="test",
        is_anonymous=True,
        session_counters={"turn_count": 1, "session_elapsed_s": 0},
        session_event_count=1,
        session_id="session_1",
        scene_title="Scene 1",
        scene_focus_category_label="Person / proper name",
        scene_specific_topic="mom",
    )

    assert "Scene title: Scene 1" in text
    assert "Scene category: Person / proper name" in text
    assert "Specific topic: mom" in text
