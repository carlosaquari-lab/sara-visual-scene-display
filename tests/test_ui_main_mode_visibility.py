import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk
from types import SimpleNamespace

from app.controller import AppController
from app.ui_main import SaraApp


class FakeWidget:
    def __init__(self):
        self.grid_calls = []
        self.grid_remove_calls = 0
        self.configure_calls = []
        self.state_calls = []
        self.place_calls = []
        self.place_forget_calls = 0
        self.lift_calls = 0

    def grid(self, *args, **kwargs) -> None:
        self.grid_calls.append({"args": args, "kwargs": kwargs})

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1

    def configure(self, *args, **kwargs) -> None:
        self.configure_calls.append({"args": args, "kwargs": kwargs})

    def state(self, value) -> None:
        self.state_calls.append(value)

    def place(self, *args, **kwargs) -> None:
        self.place_calls.append({"args": args, "kwargs": kwargs})

    def place_forget(self) -> None:
        self.place_forget_calls += 1

    def lift(self) -> None:
        self.lift_calls += 1


class FakeMenu:
    def __init__(self, end_index: int = 2):
        self.end_index = end_index
        self.entryconfig_calls = []

    def index(self, value):
        assert value == "end"
        return self.end_index

    def entryconfig(self, index, **kwargs) -> None:
        self.entryconfig_calls.append({"index": index, "kwargs": kwargs})


class AudioVisibilitySpy:
    def __init__(self):
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def _app(mode: str = "design", research_enabled: bool = False):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.current_mode = mode
    app.research = SimpleNamespace(research_enabled=research_enabled)

    app.thumbnail_toggle = FakeWidget()
    app.support_toggle = FakeWidget()
    app.hotspot_overlay_toggle = FakeWidget()
    app.scene_status_label = FakeWidget()
    app.mode_status_label = FakeWidget()
    app.user_label = FakeWidget()
    app.research_label = FakeWidget()
    app.research_quick_button = FakeWidget()
    app.mode_quick_button = FakeWidget()
    app.hotspot_tools_frame = FakeWidget()
    app.return_user_button = FakeWidget()

    app.research_menu = FakeMenu()
    app.menubar = FakeMenu()
    app.research_menu_label = "Research"

    audio_visibility_spy = AudioVisibilitySpy()
    app._refresh_scene_audio_button_visibility = audio_visibility_spy
    return app, audio_visibility_spy


def _last_config(widget: FakeWidget) -> dict:
    assert widget.configure_calls
    return widget.configure_calls[-1]["kwargs"]


def test_apply_mode_visibility_user_hides_edit_controls_and_disables_research_controls():
    app, _audio_spy = _app(mode="user")

    app._apply_mode_visibility()

    for widget in (
        app.thumbnail_toggle,
        app.support_toggle,
        app.hotspot_overlay_toggle,
        app.scene_status_label,
        app.mode_status_label,
        app.user_label,
    ):
        assert widget.grid_remove_calls == 1

    assert len(app.research_label.grid_calls) == 1
    assert len(app.research_quick_button.grid_calls) == 1
    assert len(app.mode_quick_button.grid_calls) == 1
    assert _last_config(app.research_quick_button)["state"] == tk.DISABLED
    assert _last_config(app.research_quick_button)["cursor"] == "arrow"
    assert [call["kwargs"]["state"] for call in app.research_menu.entryconfig_calls] == [tk.DISABLED, tk.DISABLED, tk.DISABLED]
    assert app.menubar.entryconfig_calls[-1]["kwargs"]["state"] == tk.DISABLED


def test_apply_mode_visibility_design_shows_edit_controls_and_enables_research_controls():
    app, _audio_spy = _app(mode="design")

    app._apply_mode_visibility()

    for widget in (
        app.thumbnail_toggle,
        app.support_toggle,
        app.hotspot_overlay_toggle,
        app.scene_status_label,
        app.mode_status_label,
        app.user_label,
    ):
        assert len(widget.grid_calls) == 1

    assert app.hotspot_overlay_toggle.state_calls == [["!disabled"]]
    assert _last_config(app.research_quick_button)["state"] == tk.NORMAL
    assert _last_config(app.research_quick_button)["cursor"] == "hand2"
    assert [call["kwargs"]["state"] for call in app.research_menu.entryconfig_calls] == [tk.NORMAL, tk.NORMAL, tk.NORMAL]
    assert app.menubar.entryconfig_calls[-1]["kwargs"]["state"] == tk.NORMAL


def test_refresh_hotspot_tools_visibility_design_places_tools_and_hides_return_button():
    app, audio_spy = _app(mode="design")

    app._refresh_hotspot_tools_visibility()

    assert len(app.hotspot_tools_frame.place_calls) == 1
    assert app.hotspot_tools_frame.lift_calls == 1
    assert app.return_user_button.place_forget_calls == 1
    assert audio_spy.calls == 1


def test_refresh_hotspot_tools_visibility_user_hides_tools_and_return_button():
    app, audio_spy = _app(mode="user")

    app._refresh_hotspot_tools_visibility()

    assert app.hotspot_tools_frame.place_forget_calls == 1
    assert app.hotspot_tools_frame.lift_calls == 0
    assert app.return_user_button.place_forget_calls == 1
    assert audio_spy.calls == 1


def test_refresh_research_quick_button_enabled_in_design_shows_on_and_normal_state():
    app, _audio_spy = _app(mode="design", research_enabled=True)

    app._refresh_research_quick_button()

    config = _last_config(app.research_quick_button)
    assert config["text"] == "ON"
    assert config["state"] == tk.NORMAL
    assert config["cursor"] == "hand2"


def test_refresh_research_quick_button_disabled_in_user_shows_off_and_disabled_state():
    app, _audio_spy = _app(mode="user", research_enabled=False)

    app._refresh_research_quick_button()

    config = _last_config(app.research_quick_button)
    assert config["text"] == "OFF"
    assert config["state"] == tk.DISABLED
    assert config["cursor"] == "arrow"
