import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import CellData, HotspotData, Scene, StoryProject
from app.storage import load_project, save_project


def _scene_with_content() -> Scene:
    return Scene(
        id="scene_1",
        title="Scene 1",
        background_image="scene.png",
        scene_audio="scene.wav",
        scene_focus_category_id="person",
        scene_focus_category_label="Person / proper name",
        scene_specific_topic="pluto",
        supports=[
            CellData(
                id="support_1",
                position=0,
                text="DOG",
                image_path="dog.png",
                audio_path="dog.wav",
                cell_type="visual_support",
                visible=True,
            )
        ],
        hotspots=[
            HotspotData(
                id="hotspot_1",
                label="PLUTO",
                text="PLUTO",
                audio_path="pluto.wav",
                x=0.2,
                y=0.3,
                width=0.2,
                height=0.2,
            )
        ],
    )


def test_scene_topic_edit_preserves_existing_hotspots_supports_image_and_audio():
    controller = AppController()
    original = _scene_with_content()
    controller.project = StoryProject(project_name="Topic edit", scenes=[original])
    controller.current_scene_index = 0

    edited = Scene(
        id="scene_1",
        title="Scene 1",
        background_image="new_scene.png",
        scene_audio="new_scene.wav",
        scene_focus_category_id="noun",
        scene_focus_category_label="Noun / object",
        scene_specific_topic="planet",
    )

    updated = controller.update_scene(edited)

    assert updated is original
    assert updated.id == "scene_1"
    assert updated.scene_specific_topic == "planet"
    assert updated.scene_focus_category_id == "noun"
    assert updated.background_image == "new_scene.png"
    assert updated.scene_audio == "new_scene.wav"
    assert [hotspot.id for hotspot in updated.hotspots] == ["hotspot_1"]
    assert updated.hotspots[0].label == "PLUTO"
    assert updated.hotspots[0].audio_path == "pluto.wav"
    assert [support.id for support in updated.supports] == ["support_1"]
    assert updated.supports[0].text == "DOG"
    assert updated.supports[0].audio_path == "dog.wav"


def test_scene_topic_edit_preserves_content_after_save_and_load(tmp_path):
    controller = AppController()
    original = _scene_with_content()
    controller.project = StoryProject(project_name="Topic edit", scenes=[original])
    controller.current_scene_index = 0

    edited = Scene(
        id="scene_1",
        title="Scene 1",
        background_image=original.background_image,
        scene_audio=original.scene_audio,
        scene_focus_category_id=original.scene_focus_category_id,
        scene_focus_category_label=original.scene_focus_category_label,
        scene_specific_topic="planet",
    )
    controller.update_scene(edited)

    project_path = tmp_path / "topic_edit.json"
    save_project(controller.project, str(project_path))
    loaded = load_project(str(project_path))
    scene = loaded.scenes[0]

    assert scene.id == "scene_1"
    assert scene.scene_specific_topic == "planet"
    assert len(scene.hotspots) == 1
    assert scene.hotspots[0].label == "PLUTO"
    assert Path(scene.hotspots[0].audio_path).name == "pluto.wav"
    assert len(scene.supports) >= 1
    assert scene.supports[0].text == "DOG"
    assert Path(scene.supports[0].audio_path).name == "dog.wav"
