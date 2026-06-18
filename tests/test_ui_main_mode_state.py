import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.ui_main import SaraApp


class FakeBoolVar:
    def __init__(self, value: bool = False):
        self._value = bool(value)
        self.set_calls = []

    def get(self) -> bool:
        return self._value

    def set(self, value: bool) -> None:
        self._value = bool(value)
        self.set_calls.append(bool(value))


class FakeDialogs:
    def __init__(self):
        self.info_calls = []

    def info(self, *args, **kwargs) -> None:
        self.info_calls.append({"args": args, "kwargs": kwargs})


class ModeSpies:
    def __init__(self):
        self.clear_timer_calls = 0
        self.build_menu_calls = 0
        self.sync_research_context_calls = 0
        self.refresh_all_calls = 0
        self.render_calls = 0
        self.cursor_calls = 0

    def install(self, app) -> None:
        app._clear_hotspot_label_timer = self.clear_timer
        app._build_menu = self.build_menu
        app._sync_research_context = self.sync_research_context
        app._refresh_all = self.refresh_all
        app._render_scene_image = self.render
        app._update_scene_cursor = self.cursor

    def clear_timer(self) -> None:
        self.clear_timer_calls += 1

    def build_menu(self) -> None:
        self.build_menu_calls += 1

    def sync_research_context(self) -> None:
        self.sync_research_context_calls += 1

    def refresh_all(self) -> None:
        self.refresh_all_calls += 1

    def render(self) -> None:
        self.render_calls += 1

    def cursor(self, *args, **kwargs) -> None:
        self.cursor_calls += 1


def _app(mode: str = "design"):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.current_mode = mode
    app.hotspot_edit_enabled_var = FakeBoolVar(True)
    app.hotspot_edit_mode = True
    app.hotspot_drag_start = object()
    app.hotspot_drag_state = {"mode": "move"}
    app.hotspot_preview_rect = {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.2}
    app.selected_hotspot_id = "h1"
    app.hotspot_tool_mode = "select"
    app.dialogs = FakeDialogs()
    app.root = None
    spies = ModeSpies()
    spies.install(app)
    return app, spies


def test_set_mode_user_changes_mode_and_clears_hotspot_state():
    app, spies = _app(mode="design")

    app.set_mode("user")

    assert app.current_mode == "user"
    assert spies.clear_timer_calls == 1
    assert app.hotspot_edit_mode is False
    assert app.hotspot_edit_enabled_var.get() is False
    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert app.selected_hotspot_id == ""
    assert spies.build_menu_calls == 1
    assert spies.sync_research_context_calls == 1
    assert spies.refresh_all_calls == 1


def test_set_mode_design_changes_mode_without_clearing_selected_hotspot():
    app, spies = _app(mode="user")

    app.set_mode("design")

    assert app.current_mode == "design"
    assert spies.clear_timer_calls == 0
    assert app.selected_hotspot_id == "h1"
    assert app.hotspot_drag_start is not None
    assert app.hotspot_preview_rect is not None
    assert app.hotspot_drag_state is None
    assert spies.build_menu_calls == 1
    assert spies.sync_research_context_calls == 1
    assert spies.refresh_all_calls == 1


def test_return_to_user_mode_clears_hotspot_state_and_sets_user_mode():
    app, spies = _app(mode="design")

    app.return_to_user_mode()

    assert app.current_mode == "user"
    assert app.hotspot_edit_mode is False
    assert app.hotspot_edit_enabled_var.get() is False
    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert app.selected_hotspot_id == ""
    assert spies.clear_timer_calls == 1
    assert spies.build_menu_calls == 1
    assert spies.sync_research_context_calls == 1
    assert spies.refresh_all_calls == 1


def test_activate_hotspot_create_tool_enables_create_mode_and_refreshes_cursor():
    app, spies = _app(mode="design")

    app.activate_hotspot_create_tool()

    assert app.current_mode == "design"
    assert app.hotspot_tool_mode == "create"
    assert app.hotspot_edit_mode is True
    assert app.hotspot_edit_enabled_var.get() is True
    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_activate_hotspot_select_tool_enables_select_mode_and_refreshes_cursor():
    app, spies = _app(mode="design")

    app.activate_hotspot_select_tool()

    assert app.current_mode == "design"
    assert app.hotspot_tool_mode == "select"
    assert app.hotspot_edit_mode is True
    assert app.hotspot_edit_enabled_var.get() is True
    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_toggle_hotspot_edit_mode_in_user_disables_editing_and_shows_info_without_rendering():
    app, spies = _app(mode="user")
    app.hotspot_edit_enabled_var = FakeBoolVar(True)
    app.hotspot_edit_mode = True

    app.toggle_hotspot_edit_mode()

    assert app.hotspot_edit_mode is False
    assert app.hotspot_edit_enabled_var.get() is False
    assert len(app.dialogs.info_calls) == 1
    assert spies.render_calls == 0
    assert spies.cursor_calls == 0


def test_toggle_hotspot_edit_mode_in_design_when_disabling_clears_selection_and_refreshes():
    app, spies = _app(mode="design")
    app.hotspot_edit_enabled_var = FakeBoolVar(False)
    app.hotspot_edit_mode = True

    app.toggle_hotspot_edit_mode()

    assert app.hotspot_edit_mode is False
    assert app.selected_hotspot_id == ""
    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1
