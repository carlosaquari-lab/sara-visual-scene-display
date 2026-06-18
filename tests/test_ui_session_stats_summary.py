import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research import ResearchLogger
from app.services.research_workflow_service import ResearchWorkflowService
from app.ui.ui_session_stats import _build_clipboard_summary, _format_stats
from app.i18n import set_language, tr


class FakeUsers:
    current_user_id = "u1"

    def get_current_user_name(self):
        return "Therapist"


class FakeDialogs:
    pass


def test_session_stats_show_clear_message_without_session_data(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())
    payload = workflow.build_session_stats_payload("Project", 0, 1, 0, 0, "User")

    text = _format_stats(**payload)

    assert text == "No session data available yet."


def test_session_stats_payload_and_text_include_response_marks(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    research.research_enabled = True
    research.research_ever_enabled = True
    research.set_session_context(project_title="Park", scene_id="s1", scene_title="Scene 1", scene_index=0, mode="User")
    research.log_event(action="key_press", key_raw="MOM", key_type="scene_hotspot", text_inserted="MOM")
    research.log_event(
        action="response_mark_annotation",
        key_raw="MOM",
        key_type="response_mark",
        hotspot_id="h1",
        hotspot_label="MOM",
        annotated_event_id="event_1",
        response_mark="correct",
        annotation_source="keyboard",
    )
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())
    payload = workflow.build_session_stats_payload(
        "Park",
        0,
        3,
        0,
        0,
        "User",
        scene_order=[
            {"id": "s1", "title": "Scene 1"},
            {"id": "s2", "title": "Scene 2"},
            {"id": "s3", "title": "Scene 3"},
        ],
    )
    payload["last_hotspot_label"] = "MOM"
    payload["last_response_mark"] = "correct"

    text = _format_stats(**payload)

    assert payload["session_id"] == research.session_id
    assert payload["hotspot_activation_count"] == 1
    assert payload["response_mark_counts"]["correct"] == 1
    assert "Events recorded in this session: 2" in text
    assert "Hotspots activated: 1" in text
    assert "SESSION DATA" in text
    assert "AUTOMATICALLY RECORDED ACTIVITY" in text
    assert "PROFESSIONAL ANNOTATION" in text
    assert "SCENE-BY-SCENE SUMMARY" in text
    assert "TEXT OUTPUTS USED" in text
    assert "HOTSPOT ACTIVITY" in text
    assert text.index("SCENE 1") < text.index("SCENE 2") < text.index("SCENE 3")
    assert "SCENE 2\n- Events: 0" in text
    assert "Response mark distribution" not in text
    assert "Last response: MOM" in text
    assert "Last mark: correct" in text
    assert "Correct responses: 1" in text
    assert "Unmarked:" not in text
    assert "response_mark_counts" not in text


def test_session_stats_treat_manual_response_marks_as_session_data(tmp_path):
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    research.research_enabled = True
    research.research_ever_enabled = True
    research.set_session_context(project_title="Park", scene_id="s1", scene_title="Scene 1", scene_index=0, mode="User")
    research.log_event(
        action="response_mark_annotation",
        key_raw="manual_session_mark",
        key_type="response_mark",
        annotated_event_id="",
        response_mark="incorrect",
        annotation_source="keyboard",
    )
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())
    payload = workflow.build_session_stats_payload("Park", 0, 3, 0, 0, "User")
    payload["last_response_mark"] = "incorrect"

    text = _format_stats(**payload)

    assert text != "No session data available yet."
    assert "PROFESSIONAL ANNOTATION" in text
    assert "Last response: -" in text
    assert "Incorrect responses: 1" in text


def test_session_stats_remain_consistent_after_changing_language_en_to_es(tmp_path):
    set_language("en")
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    research.research_enabled = True
    research.research_ever_enabled = True
    research.set_session_context(project_title="Park", scene_id="s1", scene_title="Scene 1", scene_index=0, mode="User")
    research.log_event(action="key_press", key_raw="MOM", key_type="scene_hotspot", text_inserted="MOM")
    research.log_event(
        action="key_press",
        key_raw="BALL",
        key_type="visual_support",
        text_inserted="BALL",
        representation_type="text_image",
    )
    research.log_event(
        action="response_mark_annotation",
        key_raw="manual_session_mark",
        key_type="response_mark",
        response_mark="correct",
        annotation_source="keyboard",
    )
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    set_language("es")
    payload = workflow.build_session_stats_payload(
        "Park",
        0,
        1,
        0,
        0,
        "User",
        scene_order=[{"id": "s1", "title": "Scene 1"}],
    )
    text = _format_stats(**payload)

    assert payload["hotspot_activation_count"] == 1
    assert payload["response_mark_counts"]["correct"] == 1
    assert payload["session_counters"]["total_support_activations"] == 1
    assert "ACTIVIDAD REGISTRADA AUTOMÁTICAMENTE" in text
    assert "Respuestas correctas: 1" in text
    assert "MOM" in text
    assert "BALL" in text
    set_language("en")


def test_session_stats_remain_consistent_after_changing_language_es_to_en(tmp_path):
    set_language("es")
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    research.research_enabled = True
    research.research_ever_enabled = True
    research.set_session_context(project_title="Casa", scene_id="s1", scene_title="Escena 1", scene_index=0, mode="User")
    research.log_event(action="key_press", key_raw="MAMÁ", key_type="scene_hotspot", text_inserted="MAMÁ")
    research.log_event(
        action="response_mark_annotation",
        key_raw="manual_session_mark",
        key_type="response_mark",
        response_mark="incorrect",
        annotation_source="keyboard",
    )
    workflow = ResearchWorkflowService(research, FakeUsers(), FakeDialogs())

    set_language("en")
    payload = workflow.build_session_stats_payload("Casa", 0, 1, 0, 0, "User", scene_order=[{"id": "s1", "title": "Escena 1"}])
    text = _format_stats(**payload)

    assert payload["hotspot_activation_count"] == 1
    assert payload["response_mark_counts"]["incorrect"] == 1
    assert "AUTOMATICALLY RECORDED ACTIVITY" in text
    assert "Incorrect responses: 1" in text
    assert "MAMÁ" in text


def test_research_csv_keeps_internal_keys_when_ui_language_changes(tmp_path):
    set_language("es")
    research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    research.research_enabled = True
    research.research_ever_enabled = True
    research.set_session_context(project_title="Casa", scene_id="s1", scene_title="Escena 1", scene_index=0, mode="User")
    research.log_event(
        action="response_mark_annotation",
        key_raw="manual_session_mark",
        key_type="response_mark",
        response_mark="turn",
        annotation_source="keyboard",
    )
    set_language("en")

    row = research.session_events_path.read_text(encoding="utf-8").splitlines()[-1].split(",")
    header = research.session_events_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    payload = dict(zip(header, row))

    assert payload["action"] == "response_mark_annotation"
    assert payload["key_type"] == "response_mark"
    assert payload["response_mark"] == "turn"
    assert payload["annotation_source"] == "keyboard"


def test_session_stats_hide_unmarked_as_non_informative_visual_category():
    text = _format_stats(
        project_name="Project",
        current_scene_index=0,
        total_scenes=1,
        rows=0,
        cols=0,
        mode="User",
        research_enabled=True,
        user_name="Therapist",
        session_type="test",
        is_anonymous=True,
        session_counters={"unmarked_count": 4, "session_elapsed_s": 0},
        session_event_count=1,
        session_id="session_1",
        response_mark_counts={"unmarked": 4, "turn": 0, "correct": 0, "incorrect": 0},
    )

    assert "Unmarked:" not in text
    assert "Sin marcar:" not in text
    assert "Communicative turns: 0" in text
    assert "Correct responses: 0" in text
    assert "Incorrect responses: 0" in text


def test_clipboard_summary_contains_sara_version_and_visible_professional_marks():
    set_language("en")
    stats_text = _format_stats(
        project_name="Park",
        current_scene_index=0,
        total_scenes=1,
        rows=0,
        cols=0,
        mode="User",
        research_enabled=True,
        user_name="Therapist",
        session_type="test",
        is_anonymous=True,
        session_counters={"turn_count": 2, "correct_count": 1, "incorrect_count": 1, "unmarked_count": 3, "session_elapsed_s": 12.5},
        session_event_count=4,
        session_id="session_1",
        hotspot_activation_count=1,
        response_mark_counts={"turn": 2, "correct": 1, "incorrect": 1, "unmarked": 3},
        event_summaries={
            "scene_rows": [{"title": "SCENE 1", "events": 4, "hotspots": 1, "supports": 1, "texts": [("MOM", 1)], "turn": 2, "correct": 1, "incorrect": 1}],
            "text_outputs": [("MOM", 1)],
            "hotspot_activity": [("MOM", 1)],
            "support_activity": [("DOG", 1)],
        },
    )

    summary = _build_clipboard_summary(stats_text, app_name="Sara", app_version="0.1.26")

    assert summary.startswith("Sara 0.1.26")
    assert "Session summary" in summary
    assert "User: Therapist" in summary
    assert "Project: Park" in summary
    assert "Communicative turns: 2" in summary
    assert "Correct responses: 1" in summary
    assert "Incorrect responses: 1" in summary
    assert "Unmarked:" not in summary
    assert "MOM" in summary
    assert "DOG" in summary


def test_copy_summary_i18n_labels_exist_in_english_and_spanish():
    set_language("en")
    assert tr("copy_summary") == "Copy summary"
    assert tr("stats_summary_copied") == "Summary copied to clipboard."

    set_language("es")
    assert tr("copy_summary") == "Copiar resumen"
    assert tr("stats_summary_copied") == "Resumen copiado al portapapeles."
    set_language("en")
