import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import CellData, Scene, StoryProject, default_supports, normalize_supports


def _support(
    index: int,
    text: str,
    image_path: str = "",
    audio_path: str = "",
    visible: bool = True,
) -> CellData:
    return CellData(
        id=f"support_{index + 1}",
        position=index,
        text=text,
        image_path=image_path,
        audio_path=audio_path,
        tts_enabled=False,
        fitzgerald_enabled=True,
        fitzgerald_category="noun",
        cell_type="visual_support",
        visible=visible,
        discourse_function="request",
        key_typology="noun",
        visual_source="local_image" if image_path else "none",
    )


def _controller_with_scenes(*scenes: Scene) -> AppController:
    controller = AppController()
    controller.project = StoryProject(project_name="Supports", scenes=list(scenes))
    controller.current_scene_index = 0
    for scene in controller.project.scenes:
        normalize_supports(scene)
    return controller


def _empty_scene(scene_id: str = "empty") -> Scene:
    scene = Scene(id=scene_id, title=scene_id, supports=default_supports())
    normalize_supports(scene)
    for support in scene.supports:
        support.text = ""
        support.image_path = ""
        support.audio_path = ""
        support.visible = False
        support.visual_source = "none"
    return scene


def test_update_support_updates_only_current_scene():
    scene_1 = _empty_scene("scene_1")
    scene_2 = _empty_scene("scene_2")
    controller = _controller_with_scenes(scene_1, scene_2)

    controller.update_support(0, _support(0, "scene one", image_path="one.png", audio_path="one.wav"))
    controller.go_to_scene(1)
    controller.update_support(0, _support(0, "scene two", image_path="two.png", audio_path="two.wav"))

    controller.go_to_scene(0)
    assert controller.get_support(0).text == "scene one"
    assert controller.get_support(0).image_path == "one.png"
    assert controller.get_support(0).audio_path == "one.wav"

    controller.go_to_scene(1)
    assert controller.get_support(0).text == "scene two"
    assert controller.get_support(0).image_path == "two.png"
    assert controller.get_support(0).audio_path == "two.wav"


def test_get_support_uses_current_scene_not_global_state():
    scene_1 = Scene(id="scene_1", title="scene 1", supports=[_support(0, "alpha")])
    scene_2 = Scene(id="scene_2", title="scene 2", supports=[_support(0, "beta")])
    controller = _controller_with_scenes(scene_1, scene_2)

    assert controller.get_support(0).text == "alpha"
    controller.go_to_scene(1)
    assert controller.get_support(0).text == "beta"
    controller.go_to_scene(0)
    assert controller.get_support(0).text == "alpha"


def test_empty_scene_does_not_inherit_supports_from_previous_scene():
    scene_with_supports = Scene(
        id="scene_with_supports",
        title="with supports",
        supports=[_support(0, "do not inherit", image_path="support.png", audio_path="support.wav")],
    )
    empty_scene = _empty_scene("empty_scene")
    controller = _controller_with_scenes(scene_with_supports, empty_scene)

    assert controller.get_support(0).text == "do not inherit"

    controller.go_to_scene(1)
    support = controller.get_support(0)
    assert support.text == ""
    assert support.image_path == ""
    assert support.audio_path == ""
    assert support.visible is False


def test_update_support_preserves_support_fields_and_metadata():
    controller = _controller_with_scenes(_empty_scene("scene_1"))
    support = _support(1, "preserve me", image_path="image.png", audio_path="audio.wav", visible=True)

    controller.update_support(1, support)
    saved = controller.get_support(1)

    assert saved.text == "preserve me"
    assert saved.image_path == "image.png"
    assert saved.audio_path == "audio.wav"
    assert saved.visible is True
    assert saved.position == 1
    assert saved.id == "support_2"
    assert saved.cell_type == "visual_support"
    assert saved.tts_enabled is False
    assert saved.fitzgerald_enabled is True
    assert saved.fitzgerald_category == "noun"
    assert saved.discourse_function == "request"
    assert saved.key_typology == "noun"
    assert saved.visual_source == "local_image"


def test_activate_support_returns_edit_in_design_mode():
    controller = _controller_with_scenes(Scene(id="scene_1", title="scene 1", supports=[_support(0, "edit me")]))
    controller.set_mode("design")

    result = controller.activate_support(0, "")

    assert result.action == "edit"


def test_activate_support_returns_insert_payload_in_user_mode():
    controller = _controller_with_scenes(
        Scene(
            id="scene_1",
            title="scene 1",
            supports=[_support(0, "drink water", image_path="drink.png", audio_path="drink.wav")],
        )
    )
    controller.set_mode("user")

    result = controller.activate_support(0, "hello")

    assert result.action == "insert"
    assert result.inserted_text == "DRINK WATER"
    assert result.new_text == "hello DRINK WATER"
    assert result.audio_path == "drink.wav"
    assert result.speak_text == "DRINK WATER"
    assert result.tts_enabled is False
    assert result.discourse_function == "request"
    assert result.key_typology == "noun"
    assert result.fitzgerald_category == "noun"
    assert result.visual_source == "local_image"
    assert result.representation_type == "text_image"


def test_activate_support_ignores_out_of_range_indexes():
    controller = _controller_with_scenes(_empty_scene("scene_1"))
    controller.set_mode("user")

    assert controller.activate_support(-1, "").action == "ignored"
    assert controller.activate_support(999, "").action == "ignored"