"""API session context — holds SQLAlchemy Session; caller owns commit (APP-003)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class ApiContext:
    """Bundle of resource APIs for one unit-of-work session.

    Callers own commit via ``get_session()`` (APP-003). This context is the
    stable UI/worker entry; it is not an HTTP router.
    """

    session: Session

    @property
    def jobs(self):
        from archium.application.api.jobs import JobsApi

        return JobsApi(self.session)

    @property
    def project(self):
        from archium.application.api.project import ProjectApi

        return ProjectApi(self.session)

    @property
    def documents(self):
        from archium.application.api.documents import DocumentsApi

        return DocumentsApi(self.session)

    @property
    def context(self):
        from archium.application.api.context import ContextApi

        return ContextApi(self.session)

    @property
    def mission(self):
        from archium.application.api.mission import MissionApi

        return MissionApi(self.session)

    @property
    def storyline(self):
        from archium.application.api.storyline import StorylineApi

        return StorylineApi(self.session)

    @property
    def slides(self):
        from archium.application.api.slides import SlidesApi

        return SlidesApi(self.session)

    @property
    def scenes(self):
        from archium.application.api.scenes import ScenesApi

        return ScenesApi(self.session)

    @property
    def revisions(self):
        from archium.application.api.revisions import RevisionsApi

        return RevisionsApi(self.session)

    @property
    def render(self):
        from archium.application.api.render import RenderApi

        return RenderApi(self.session)

    @property
    def delivery(self):
        from archium.application.api.delivery import DeliveryApi

        return DeliveryApi(self.session)

    @property
    def visual(self):
        from archium.application.api.visual import VisualApi

        return VisualApi(self.session)

    @property
    def planning(self):
        from archium.application.api.planning import PlanningApi

        return PlanningApi(self.session)


def api_from_session(session: Session) -> ApiContext:
    return ApiContext(session=session)
