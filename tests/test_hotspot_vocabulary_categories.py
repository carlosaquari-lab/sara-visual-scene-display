from __future__ import annotations

import csv
import json
from pathlib import Path

from app.controller import AppController
from app.models import HotspotData, Scene, StoryProject
from app.research import ResearchLogger
from app.services.session_service import SessionService
from app.storage import save_project
from app.vocabulary_categories import (
    COMMUNICATION_CATEGORIES,
    COMMUNICATION_CATEGORY_GROUP,
    VOCABULARY_CATEGORIES,
    get_categories_by_group,
    get_vocabulary_category,
    get_vocabulary_category_columns,
)


class FakeAudio:
    def __init__(self):
        self.calls = []

    def play_or_speak(self, audio_path, text, tts_enabled=True):
        self.calls.append({"audio_path": audio_path, "text": text, "tts_enabled": tts_enabled})
        return "none"


class FakeUsers:
    current_user_id = ""
    user_segment_key_presses = 0
    user_segment_words_inserted = 0
    user_segment_characters_inserted = 0

    def get_current_user_name(self):
        return ""


def test_communication_categories_are_centralized_and_single_category_lookup():
    communication = get_categories_by_group(COMMUNICATION_CATEGORY_GROUP)

    assert VOCABULARY_CATEGORIES is COMMUNICATION_CATEGORIES
    assert get_vocabulary_category("person") == {
        "id": "person",
        "label": "Person / proper name",
        "group": COMMUNICATION_CATEGORY_GROUP,
    }
    assert get_vocabulary_category("priority") == {
        "id": "priority",
        "label": "Priority / emergency",
        "group": COMMUNICATION_CATEGORY_GROUP,
    }
    assert len(COMMUNICATION_CATEGORIES) == 11
    assert len([category for category in COMMUNICATION_CATEGORIES if category["id"] != "none"]) == 10
    assert len(communication) == 10
    for category in COMMUNICATION_CATEGORIES:
        assert set(category) == {"id", "label", "group"}
        assert category["id"]
        assert category["label"]


def test_vocabulary_category_ui_columns_are_balanced_and_do_not_duplicate_none():
    columns = get_vocabulary_category_columns()
    ids = [category["id"] for column in columns for category in column]

    assert len(columns) == 3
    assert [len(column) for column in columns] == [4, 4, 3]
    assert ids.count("none") == 1
    assert set(ids) == {category["id"] for category in COMMUNICATION_CATEGORIES}


def test_hotspot_json_uses_vocabulary_category_fields_and_omits_old_research_fields(tmp_path):
    hotspot = HotspotData(
        id="h1",
        text="hello",
        vocabulary_category_id="person",
        vocabulary_category_label="Person / proper name",
        vocabulary_category_group=COMMUNICATION_CATEGORY_GROUP,
    )
    project = StoryProject(project_name="Vocabulary", scenes=[Scene(id="scene_1", title="Scene", hotspots=[hotspot])])
    project_path = tmp_path / "Vocabulary.json"

    save_project(project, str(project_path))

    payload = json.loads(project_path.read_text(encoding="utf-8"))
    saved_hotspot = payload["scenes"][0]["hotspots"][0]
    assert saved_hotspot["vocabulary_category_id"] == "person"
    assert saved_hotspot["vocabulary_category_label"] == "Person / proper name"
    assert saved_hotspot["vocabulary_category_group"] == COMMUNICATION_CATEGORY_GROUP
    assert "key_typology" not in saved_hotspot
    assert "discourse_function" not in saved_hotspot


def test_research_event_logs_vocabulary_category_columns(tmp_path):
    hotspot = HotspotData(
        id="h1",
        text="hello",
        vocabulary_category_id="priority",
        vocabulary_category_label="Priority / emergency",
        vocabulary_category_group=COMMUNICATION_CATEGORY_GROUP,
    )
    scene = Scene(id="scene_1", title="Scene", hotspots=[hotspot])
    project = StoryProject(project_name="Vocabulary", scenes=[scene])
    controller = AppController()
    controller.project = project
    controller.current_scene_index = 0
    controller.set_mode("user")
    research = ResearchLogger(tmp_path, schema_version="test", app_name="Sara", app_version="0.1.26")
    research.set_research_enabled(True)
    service = SessionService(controller, FakeAudio(), research, FakeUsers())

    service.activate_hotspot(project, scene, 0, "user", hotspot, "")

    with Path(research.session_events_path).open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["vocabulary_category_id"] == "priority"
    assert rows[0]["vocabulary_category_label"] == "Priority / emergency"
    assert rows[0]["vocabulary_category_group"] == COMMUNICATION_CATEGORY_GROUP
    assert "key_typology" not in rows[0]
    assert "discourse_function" not in rows[0]
    summary_path = research.write_session_summary(reason="test")
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["category_counts"] == {"priority": 1}
    assert summary["top_vocabulary_categories"] == ["priority"]
