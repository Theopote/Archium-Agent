"""API session context — holds SQLAlchemy Session; caller owns commit (APP-003)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from archium.application.api.context import ContextApi
    from archium.application.api.delivery import DeliveryApi
    from archium.application.api.documents import DocumentsApi
    from archium.application.api.jobs import JobsApi
    from archium.application.api.mission import MissionApi
    from archium.application.api.planning import PlanningApi
    from archium.application.api.project import ProjectApi
    from archium.application.api.render import RenderApi
    from archium.application.api.revisions import RevisionsApi
    from archium.application.api.scenes import ScenesApi
    from archium.application.api.slides import SlidesApi
    from archium.application.api.storyline import StorylineApi
    from archium.application.api.visual import VisualApi


@dataclass
class ApiContext:
    """Bundle of resource APIs for one unit-of-work session.

    Callers own commit via ``get_session()`` (APP-003). This context is the
    stable UI/worker entry; it is not an HTTP router. Resource facades are
    cached per context instance (same ``session`` shared).
    """

    session: Session

    @cached_property
    def jobs(self) -> JobsApi:
        from archium.application.api.jobs import JobsApi

        return JobsApi(self.session)

    @cached_property
    def project(self) -> ProjectApi:
        from archium.application.api.project import ProjectApi

        return ProjectApi(self.session)

    @cached_property
    def documents(self) -> DocumentsApi:
        from archium.application.api.documents import DocumentsApi

        return DocumentsApi(self.session)

    @cached_property
    def context(self) -> ContextApi:
        from archium.application.api.context import ContextApi

        return ContextApi(self.session)

    @cached_property
    def mission(self) -> MissionApi:
        from archium.application.api.mission import MissionApi

        return MissionApi(self.session)

    @cached_property
    def storyline(self) -> StorylineApi:
        from archium.application.api.storyline import StorylineApi

        return StorylineApi(self.session)

    @cached_property
    def slides(self) -> SlidesApi:
        from archium.application.api.slides import SlidesApi

        return SlidesApi(self.session)

    @cached_property
    def scenes(self) -> ScenesApi:
        from archium.application.api.scenes import ScenesApi

        return ScenesApi(self.session)

    @cached_property
    def revisions(self) -> RevisionsApi:
        from archium.application.api.revisions import RevisionsApi

        return RevisionsApi(self.session)

    @cached_property
    def render(self) -> RenderApi:
        from archium.application.api.render import RenderApi

        return RenderApi(self.session)

    @cached_property
    def delivery(self) -> DeliveryApi:
        from archium.application.api.delivery import DeliveryApi

        return DeliveryApi(self.session)

    @cached_property
    def visual(self) -> VisualApi:
        from archium.application.api.visual import VisualApi

        return VisualApi(self.session)

    @cached_property
    def planning(self) -> PlanningApi:
        from archium.application.api.planning import PlanningApi

        return PlanningApi(self.session)


def api_from_session(session: Session) -> ApiContext:
    """Compatibility entry: UI/tests already hold a Session (APP-003).

    Future public entry should prefer a Unit-of-Work factory that hides the
    Session; keep this helper until that migration lands.
    """
    return ApiContext(session=session)
