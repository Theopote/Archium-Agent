import json
import re
from uuid import UUID

from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import get_settings
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.session import get_session

deck_id = UUID("e48d0481-f625-48a7-b4b1-e1ee4163e76d")
with get_session() as s:
    slides = PresentationRepository(s).list_slides(deck_id)
    slide = sorted(slides, key=lambda x: x.order)[0]
    result = StudioSceneService(s, settings=get_settings()).ensure_scene_for_slide(slide.id)
    scene = result.scene
    blob = json.dumps(scene.model_dump(mode="json"), ensure_ascii=False)
    print("has_marker", "剧本E" in blob)
    for m in re.findall(r".{0,8}清凉寺.{0,24}", blob)[:20]:
        print("hit", m.replace("\n", " ")[:100])
