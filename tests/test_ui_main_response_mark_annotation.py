import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import HotspotData, Scene, StoryProject
from app.research import ResearchLogger
from app.ui_main import SaraApp


class FakeSessionService:
    def __init__(self, result):
        self.result = result

    def activate_hotspot(self, *_args, **_kwargs):
        return self.result


class FakeUsers:
    current_user_id = "u1"

    def get_current_user_name(self):
        return "Therapist"


class FakeRoot:
    def __init__(self, focus=None, grabbed=None):
        self.focus = focus
        self.grabbed = grabbed
        self.binds = []

    def bind(self, sequence, callback, add=None):
        self.binds.append((sequence, callback, add))

    def focus_get(self):
        return self.focus

    def grab_current(self):
        return self.grabbed

    def after_idle(self, callback):
        callback()


class FakeFocusWidget:
    def __init__(self, widget_class):
        self.widget_class = widget_class

    def winfo_class(self):
        return self.widget_class


class FakeStatusVar:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class FakeStatusLabel:
    def __init__(self):
        self.grid_calls = []
        self.grid_remove_calls = 0

    def grid(self, **kwargs):
        self.grid_calls.append(kwargs)

    def grid_remove(self):
        self.grid_remove_calls += 1


class FakeBindableWidget:
    def __init__(self):
        self.binds = {}

    def bind(self, sequence, callback, add=None):
        self.binds[sequence] = (callback, add)


class FakeBoolVar:
    def __init__(self, value):
        self.value = bool(value)
        self.set_calls = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)
        self.set_calls.append(bool(value))


class FakeEvent:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class FakeSceneImageView:
    def __init__(self, hotspot=None):
        self.hotspot = hotspot

    def hotspot_hit_test(self, *_args, **_kwargs):
        return self.hotspot


class HotspotActivationSpies:
    def __init__(self):
        self.render_calls = 0
        self.sync_text_calls = 0

    def install(self, app):
        app._schedule_hotspot_label_hide = lambda _hotspot: None
        app._render_scene_image = self.render
        app._replace_output_text = lambda value: setattr(app, "output_buffer", value)
        app._sync_research_text = self.sync_text

    def render(self):
        self.render_calls += 1

    def sync_text(self):
        self.sync_text_calls += 1


def _rows(path):
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _app(tmp_path, result=None, focus=None):
    scene = Scene(id="scene_1", title="Scene 1")
    project = StoryProject(project_name="Response Mark", scenes=[scene])
    app = object.__new__(SaraApp)
    app.root = FakeRoot(focus=focus)
    app.controller = AppController()
    app.controller.project = project
    app.controller.current_scene_index = 0
    app.current_mode = "user"
    app.output_buffer = ""
    app.selected_hotspot_id = ""
    app.research = ResearchLogger(tmp_path, schema_version="0.1-test", app_name="Sara", app_version="test")
    app.research.research_enabled = True
    app.research.research_ever_enabled = True
    app.users_manager = FakeUsers()
    app.session_service = FakeSessionService(result or SimpleNamespace(action="insert", inserted_text="MOM", target_scene_id=""))
    app._last_hotspot_event = None
    app._last_response_event = None
    app._last_response_mark = "unmarked"
    spies = HotspotActivationSpies()
    spies.install(app)
    return app, spies


def test_activate_hotspot_remembers_last_hotspot_as_unmarked(tmp_path):
    app, _spies = _app(tmp_path)
    hotspot = HotspotData(id="h1", label="MOM", text="MOM")

    app.activate_hotspot(hotspot)

    assert app._last_hotspot_event["hotspot_id"] == "h1"
    assert app._last_hotspot_event["hotspot_label"] == "MOM"
    assert app._last_hotspot_event["response_mark"] == "unmarked"


def test_space_plus_minus_and_z_write_response_mark_annotation_events(tmp_path):
    app, _spies = _app(tmp_path)
    app.activate_hotspot(HotspotData(id="h1", label="MOM", text="MOM"))

    assert app._handle_response_mark_shortcut(None, "turn") == "break"
    assert app._handle_response_mark_shortcut(None, "correct") == "break"
    assert app._handle_response_mark_shortcut(None, "incorrect") == "break"
    assert app._handle_response_mark_shortcut(None, "unmarked") == "break"

    rows = _rows(app.research.session_events_path)
    annotation_rows = [row for row in rows if row["action"] == "response_mark_annotation"]
    assert [row["response_mark"] for row in annotation_rows] == ["turn", "correct", "incorrect", "unmarked"]
    assert {row["annotation_source"] for row in annotation_rows} == {"keyboard"}
    assert all(row["annotated_event_id"] for row in annotation_rows)
    assert {row["hotspot_id"] for row in annotation_rows} == {"h1"}
    assert {row["hotspot_label"] for row in annotation_rows} == {"MOM"}
    assert app._last_hotspot_event["response_mark"] == "unmarked"


def test_response_mark_shortcut_records_manual_session_mark_without_last_response(tmp_path):
    app, _spies = _app(tmp_path)

    assert app._handle_response_mark_shortcut(None, "correct") == "break"

    rows = _rows(app.research.session_events_path)
    annotation_rows = [row for row in rows if row["action"] == "response_mark_annotation"]
    assert len(annotation_rows) == 1
    assert annotation_rows[0]["key_raw"] == "manual_session_mark"
    assert annotation_rows[0]["annotated_event_id"] == ""
    assert annotation_rows[0]["response_mark"] == "correct"
    assert annotation_rows[0]["annotation_source"] == "keyboard"
    assert app._last_response_event is None
    assert app._last_response_mark == "correct"


def test_response_mark_shortcut_is_ignored_when_focus_is_text_input(tmp_path):
    app, _spies = _app(tmp_path, focus=FakeFocusWidget("Entry"))
    app.activate_hotspot(HotspotData(id="h1", label="MOM", text="MOM"))

    assert app._handle_response_mark_shortcut(None, "correct") is None

    assert not app.research.session_events_path.exists()
    assert app._last_hotspot_event["response_mark"] == "unmarked"


def test_response_mark_summary_counts_annotations(tmp_path):
    app, _spies = _app(tmp_path)
    app.activate_hotspot(HotspotData(id="h1", label="MOM", text="MOM"))

    app._apply_response_mark("turn")
    app._apply_response_mark("correct")
    app._apply_response_mark("incorrect")

    summary_path = app.research.write_session_summary(reason="test")
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))

    assert payload["response_mark_counts"] == {
        "unmarked": 0,
        "turn": 1,
        "correct": 1,
        "incorrect": 1,
    }


def test_response_mark_status_reserves_toolbar_space_when_research_is_off(tmp_path):
    app, _spies = _app(tmp_path)
    app.research.research_enabled = False
    app.response_mark_status_var = FakeStatusVar()
    app.response_mark_status_label = FakeStatusLabel()

    app._refresh_response_mark_status()

    assert app.response_mark_status_var.value == " "
    assert app.response_mark_status_label.grid_calls
    assert app.response_mark_status_label.grid_remove_calls == 0


def test_response_mark_status_shows_fixed_shortcut_help_without_dynamic_mark(tmp_path):
    app, _spies = _app(tmp_path)
    app.response_mark_status_var = FakeStatusVar()
    app.response_mark_status_label = FakeStatusLabel()

    app._apply_response_mark("incorrect")

    assert app.response_mark_status_var.value == "Space = communicative turn     + = correct response     - = incorrect response     Z = Undo"
    assert "Professional mark" not in app.response_mark_status_var.value
    assert "Mark: incorrect" not in app.response_mark_status_var.value


def test_response_mark_shortcut_does_not_rerender_visible_support_strip(tmp_path):
    app, _spies = _app(tmp_path)
    app.support_strip_visible = FakeBoolVar(True)
    app.reserve_calls = 0
    app.render_support_calls = 0
    app._reserve_or_hide_support_bar = lambda: setattr(app, "reserve_calls", app.reserve_calls + 1)
    app._render_support_strip = lambda: setattr(app, "render_support_calls", app.render_support_calls + 1)

    assert app._handle_response_mark_shortcut(None, "turn") == "break"

    assert app.support_strip_visible.get() is True
    assert app.reserve_calls == 0
    assert app.render_support_calls == 0


def test_support_toggle_space_is_consumed_as_response_mark_before_default_toggle(tmp_path):
    app, _spies = _app(tmp_path)
    app.support_strip_visible = FakeBoolVar(True)
    widget = FakeBindableWidget()

    app._bind_response_mark_shortcuts_to_widget(widget)
    callback, add = widget.binds["<space>"]

    assert add == "+"
    assert callback(None) == "break"

    rows = _rows(app.research.session_events_path)
    annotation_rows = [row for row in rows if row["action"] == "response_mark_annotation"]
    assert annotation_rows[-1]["response_mark"] == "turn"
    assert app.support_strip_visible.get() is True
    assert app.support_strip_visible.set_calls == []


def test_image_response_click_becomes_annotable_and_can_be_marked_incorrect(tmp_path):
    app, _spies = _app(tmp_path)
    app.scene_image_view = FakeSceneImageView(hotspot=None)
    app.scene_render_info = {"image_x": 20, "image_y": 30, "display_width": 200, "display_height": 100}
    app.response_mark_status_var = FakeStatusVar()
    app.response_mark_status_label = FakeStatusLabel()

    app._on_scene_click(FakeEvent(80, 70))

    assert app._last_response_event["response_type"] == "image_click"
    assert app._last_response_event["response_label"] == "image click"
    assert app._last_response_event["click_x"] == 60
    assert app._last_response_event["click_y"] == 40

    assert app._handle_response_mark_shortcut(None, "incorrect") == "break"

    rows = _rows(app.research.session_events_path)
    image_rows = [row for row in rows if row["action"] == "image_response_click"]
    annotation_rows = [row for row in rows if row["action"] == "response_mark_annotation"]
    assert len(image_rows) == 1
    assert image_rows[0]["event_id"] == app._last_response_event["event_id"]
    assert image_rows[0]["click_x"] == "60"
    assert image_rows[0]["click_y"] == "40"
    assert image_rows[0]["response_mark"] == "unmarked"
    assert annotation_rows[-1]["annotated_event_id"] == image_rows[0]["event_id"]
    assert annotation_rows[-1]["response_mark"] == "incorrect"
    assert app.research.session_counters["incorrect_count"] == 1


def test_image_response_click_is_not_recorded_when_research_is_off_or_outside_image(tmp_path):
    app, _spies = _app(tmp_path)
    app.scene_image_view = FakeSceneImageView(hotspot=None)
    app.scene_render_info = {"image_x": 20, "image_y": 30, "display_width": 200, "display_height": 100}
    app.research.research_enabled = False

    app._on_scene_click(FakeEvent(80, 70))

    assert app._last_response_event is None
    assert not app.research.session_events_path.exists()

    app.research.research_enabled = True
    app._on_scene_click(FakeEvent(999, 999))

    assert app._last_response_event is None
    assert not app.research.session_events_path.exists()
