import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research import ResearchLogger
from app.services.research_workflow_service import ResearchWorkflowService


class FakeUsers:
    current_user_id = "1"

    def get_current_user_name(self):
        return "carlos"


class FakeDialogs:
    def __init__(self):
        self.errors = []

    def error(self, title, message, *, parent=None):
        self.errors.append((title, message))


def _rows(path):
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_fast_on_off_on_uses_unique_session_ids(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    research.set_session_context(
        mode="User",
        layout_file="lavar_manos.json",
        project_title="LAVAR_MANOS",
        scene_id="scene_2",
        scene_title="ESCENA 2",
        scene_index=1,
    )
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    assert workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None) is True
    first_session = research.session_id
    first_events = research.session_events_path

    research.log_event(
        action="key_press",
        key_raw="GRIFO",
        key_type="story_cell",
        text_inserted="GRIFO",
        user_id="1",
        user_name="carlos",
    )

    assert workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None) is False
    assert workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None) is True
    second_session = research.session_id
    second_events = research.session_events_path

    assert first_session != second_session
    assert first_events.name == f"events_{first_session}.csv"
    assert second_events.name == f"events_{second_session}.csv"


def test_disable_summary_records_final_off_state(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    research.set_session_context(mode="User", layout_file="lavar_manos.json", project_title="LAVAR_MANOS")
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)
    session_id = research.session_id
    research.log_event(action="key_press", key_raw="A", key_type="story_cell", text_inserted="A", user_id="1", user_name="carlos")
    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)

    payload = json.loads((tmp_path / f"session_summary_{session_id}.json").read_text(encoding="utf-8"))
    assert payload["reason"] == "disable_research"
    assert payload["research_enabled"] is False


def test_toggle_events_are_written_only_when_session_has_participant_activity(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    research.set_session_context(mode="User", layout_file="lavar_manos.json", project_title="LAVAR_MANOS")
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)
    session_id = research.session_id
    research.log_event(action="key_press", key_raw="A", key_type="story_cell", text_inserted="A", user_id="1", user_name="carlos")
    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)

    event_rows = _rows(tmp_path / f"events_{session_id}.csv")
    global_rows = _rows(tmp_path / "global_log.csv")

    assert event_rows[0]["action"] == "toggle_research_on"
    assert any(row["action"] == "toggle_research_off" for row in event_rows)
    assert all(row["session_id"] == session_id for row in event_rows)
    assert any(row["action"] == "toggle_research_on" for row in global_rows)
    assert any(row["action"] == "toggle_research_off" for row in global_rows)


def test_empty_on_off_does_not_create_events_file_or_summary(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    research.set_session_context(mode="User", layout_file="lavar_manos.json", project_title="LAVAR_MANOS")
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)
    session_id = research.session_id
    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)

    assert not (tmp_path / f"events_{session_id}.csv").exists()
    assert not (tmp_path / f"session_summary_{session_id}.json").exists()


def test_no_empty_events_file_before_research_is_enabled(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    assert not research.session_events_path.exists()
    assert (tmp_path / "global_log.csv").exists()
    assert (tmp_path / "session_summary.csv").exists()


def test_events_file_is_created_lazily_on_first_participant_event(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)
    assert not research.session_events_path.exists()
    assert research.get_status_snapshot()["session_event_count"] == 0
    assert research.get_status_snapshot()["pending_toggle_on"] is True

    research.log_event(action="key_press", key_raw="A", key_type="story_cell", text_inserted="A", user_id="1", user_name="carlos")

    assert research.session_events_path.exists()
    assert research.get_status_snapshot()["session_event_count"] == 2
    assert research.get_status_snapshot()["participant_event_count"] == 1
    rows = _rows(research.session_events_path)
    assert rows[0]["action"] == "toggle_research_on"
    assert rows[1]["action"] == "key_press"


def test_layout_load_after_on_does_not_create_empty_research_session(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    workflow.toggle_research(None, research.research_enabled, "1", "carlos", lambda: None)
    research.log_event(
        action="layout_load",
        layout_file="comer.json",
        mode="Therapist",
        project_title="COMER",
        scene_id="scene_1",
        scene_title="ESCENA 1",
        scene_index=0,
    )

    assert not research.session_events_path.exists()
    assert research.get_status_snapshot()["session_event_count"] == 0
    assert research.has_activity() is False

    research.log_event(
        action="key_press",
        key_raw="QUIERO COMER",
        key_type="scene_hotspot",
        text_inserted="QUIERO COMER",
        user_id="1",
        user_name="carlos",
    )

    rows = _rows(research.session_events_path)
    assert [row["action"] for row in rows] == ["toggle_research_on", "key_press"]
