import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import Scene, StoryProject
from app.ui_main import SaraApp


class FakeResearchWorkflow:
    def __init__(self, result):
        self.result = result
        self.toggle_calls = []

    def toggle_research(self, root, current_enabled, current_user_id, current_user_name, select_user_callback):
        self.toggle_calls.append(
            {
                "root": root,
                "current_enabled": current_enabled,
                "current_user_id": current_user_id,
                "current_user_name": current_user_name,
                "select_user_callback": select_user_callback,
            }
        )
        return self.result


class FakeUsersManager:
    def __init__(self, user_id: str = "u1", user_name: str = "User One"):
        self.current_user_id = user_id
        self._user_name = user_name

    def get_current_user_name(self) -> str:
        return self._user_name


class FakeSessionService:
    def __init__(self):
        self.sync_context_calls = []
        self.sync_text_calls = []

    def sync_research_context(self, project, current_scene, current_scene_index, current_mode) -> None:
        self.sync_context_calls.append(
            {
                "project": project,
                "current_scene": current_scene,
                "current_scene_index": current_scene_index,
                "current_mode": current_mode,
            }
        )

    def sync_research_text(self, text: str, mode: str = "Therapist") -> None:
        self.sync_text_calls.append({"text": text, "mode": mode})


class ResearchUISpies:
    def __init__(self):
        self.sync_context_calls = 0
        self.refresh_all_calls = 0

    def install(self, app) -> None:
        app._sync_research_context = self.sync_context
        app._refresh_all = self.refresh_all

    def sync_context(self) -> None:
        self.sync_context_calls += 1

    def refresh_all(self) -> None:
        self.refresh_all_calls += 1


def _project() -> StoryProject:
    return StoryProject(
        project_name="Research UI",
        scenes=[Scene(id="scene_1", title="Scene 1"), Scene(id="scene_2", title="Scene 2")],
    )


def _app(mode: str = "design", research_enabled: bool = False, workflow_result=True):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = _project()
    app.controller.current_scene_index = 1
    app.current_mode = mode
    app.root = object()
    app.research = SimpleNamespace(research_enabled=research_enabled)
    app.research_workflow = FakeResearchWorkflow(workflow_result)
    app.users_manager = FakeUsersManager()
    app.session_service = FakeSessionService()
    app.output_buffer = "current text"
    app.select_user = lambda: None
    return app


def test_toggle_research_user_mode_does_not_call_workflow_sync_or_refresh():
    app = _app(mode="user", research_enabled=False, workflow_result=True)
    spies = ResearchUISpies()
    spies.install(app)

    app.toggle_research()

    assert app.research_workflow.toggle_calls == []
    assert spies.sync_context_calls == 0
    assert spies.refresh_all_calls == 0
    assert app.research.research_enabled is False


def test_toggle_research_design_mode_with_true_result_syncs_and_refreshes():
    app = _app(mode="design", research_enabled=False, workflow_result=True)
    spies = ResearchUISpies()
    spies.install(app)

    app.toggle_research()

    assert app.research_workflow.toggle_calls == [
        {
            "root": app.root,
            "current_enabled": False,
            "current_user_id": "u1",
            "current_user_name": "User One",
            "select_user_callback": app.select_user,
        }
    ]
    assert spies.sync_context_calls == 1
    assert spies.refresh_all_calls == 1


def test_toggle_research_design_mode_with_false_result_syncs_and_refreshes():
    app = _app(mode="design", research_enabled=True, workflow_result=False)
    spies = ResearchUISpies()
    spies.install(app)

    app.toggle_research()

    assert len(app.research_workflow.toggle_calls) == 1
    assert app.research_workflow.toggle_calls[0]["current_enabled"] is True
    assert spies.sync_context_calls == 1
    assert spies.refresh_all_calls == 1


def test_toggle_research_design_mode_with_none_result_does_not_sync_or_refresh():
    app = _app(mode="design", research_enabled=False, workflow_result=None)
    spies = ResearchUISpies()
    spies.install(app)

    app.toggle_research()

    assert len(app.research_workflow.toggle_calls) == 1
    assert spies.sync_context_calls == 0
    assert spies.refresh_all_calls == 0


def test_sync_research_context_delegates_to_session_service_with_project_scene_index_and_mode():
    app = _app(mode="user", research_enabled=True)

    app._sync_research_context()

    assert app.session_service.sync_context_calls == [
        {
            "project": app.project,
            "current_scene": app.current_scene,
            "current_scene_index": 1,
            "current_mode": "user",
        }
    ]


def test_sync_research_text_uses_output_text_and_therapist_mode():
    app = _app(mode="user", research_enabled=True)
    app.output_buffer = "hello"

    app._sync_research_text()

    assert app.session_service.sync_text_calls == [{"text": "hello", "mode": "Therapist"}]
