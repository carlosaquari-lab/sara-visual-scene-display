import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import HotspotData
from app.ui_main import SaraApp


class FakeRoot:
    def __init__(self):
        self.after_calls = []
        self.after_cancel_calls = []
        self._next_id = 1

    def after(self, milliseconds: int, callback):
        after_id = f"after-{self._next_id}"
        self._next_id += 1
        self.after_calls.append({"id": after_id, "milliseconds": milliseconds, "callback": callback})
        return after_id

    def after_cancel(self, after_id) -> None:
        self.after_cancel_calls.append(after_id)


class RenderSpy:
    def __init__(self):
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def _hotspot(
    hotspot_id: str = "h1",
    *,
    seconds=5,
    always: bool = False,
) -> HotspotData:
    hotspot = HotspotData(id=hotspot_id, label=hotspot_id)
    hotspot.label_persistence_seconds = seconds
    hotspot.label_persistence_always = always
    return hotspot


def _app():
    app = object.__new__(SaraApp)
    app.root = FakeRoot()
    app._hotspot_label_hide_after_id = None
    app.selected_hotspot_id = ""
    render_spy = RenderSpy()
    app._render_scene_image = render_spy
    return app, render_spy


def test_clear_hotspot_label_timer_cancels_pending_timer_and_clears_id():
    app, _render_spy = _app()
    app._hotspot_label_hide_after_id = "after-previous"

    app._clear_hotspot_label_timer()

    assert app.root.after_cancel_calls == ["after-previous"]
    assert app._hotspot_label_hide_after_id is None


def test_clear_hotspot_label_timer_without_pending_timer_does_not_cancel():
    app, _render_spy = _app()

    app._clear_hotspot_label_timer()

    assert app.root.after_cancel_calls == []
    assert app._hotspot_label_hide_after_id is None


def test_schedule_hotspot_label_hide_cancels_previous_timer_and_schedules_new_one():
    app, _render_spy = _app()
    app._hotspot_label_hide_after_id = "after-previous"

    app._schedule_hotspot_label_hide(_hotspot(seconds=7))

    assert app.root.after_cancel_calls == ["after-previous"]
    assert len(app.root.after_calls) == 1
    assert app.root.after_calls[0]["milliseconds"] == 7000
    assert app._hotspot_label_hide_after_id == "after-1"


def test_schedule_hotspot_label_hide_with_always_persistence_cancels_without_scheduling():
    app, _render_spy = _app()
    app._hotspot_label_hide_after_id = "after-previous"

    app._schedule_hotspot_label_hide(_hotspot(always=True))

    assert app.root.after_cancel_calls == ["after-previous"]
    assert app.root.after_calls == []
    assert app._hotspot_label_hide_after_id is None


def test_schedule_hotspot_label_hide_uses_minimum_for_negative_seconds():
    app, _render_spy = _app()

    app._schedule_hotspot_label_hide(_hotspot(seconds=-3))

    assert app.root.after_calls[0]["milliseconds"] == 1000
    assert app._hotspot_label_hide_after_id == "after-1"


def test_schedule_hotspot_label_hide_uses_default_for_invalid_seconds():
    app, _render_spy = _app()

    app._schedule_hotspot_label_hide(_hotspot(seconds="bad"))

    assert app.root.after_calls[0]["milliseconds"] == 5000
    assert app._hotspot_label_hide_after_id == "after-1"


def test_hotspot_label_timer_callback_hides_current_selected_hotspot_and_renders():
    app, render_spy = _app()
    app.selected_hotspot_id = "h1"
    app._schedule_hotspot_label_hide(_hotspot("h1", seconds=2))

    app.root.after_calls[0]["callback"]()

    assert app.selected_hotspot_id == ""
    assert app._hotspot_label_hide_after_id is None
    assert render_spy.calls == 1


def test_hotspot_label_timer_callback_ignores_when_another_hotspot_is_selected():
    app, render_spy = _app()
    app.selected_hotspot_id = "other"
    app._schedule_hotspot_label_hide(_hotspot("h1", seconds=2))

    app.root.after_calls[0]["callback"]()

    assert app.selected_hotspot_id == "other"
    assert app._hotspot_label_hide_after_id == "after-1"
    assert render_spy.calls == 0
