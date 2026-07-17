"""Add rule_code column to review_issues."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_review_issue_rule_code"
down_revision: Union[str, None] = "004_review_layer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TITLE_TO_RULE_CODE: dict[str, str] = {
    "缺少标题": "CONTENT.MISSING_TITLE",
    "缺少核心信息": "CONTENT.MISSING_MESSAGE",
    "结论表述过于简略": "CONTENT.MESSAGE_TOO_SHORT",
    "标题重复": "CONTENT.DUPLICATE_TITLE",
    "Brief 核心信息未体现": "CONTENT.BRIEF_CORE_NOT_REFLECTED",
    "Brief 语义对齐不足": "CONTENT.BRIEF_ALIGNMENT_GAP",
    "缺少引用来源": "EVIDENCE.MISSING_CITATION",
    "数值结论缺少依据": "EVIDENCE.NUMERIC_CLAIM_UNCITED",
    "视觉证据未确认": "EVIDENCE.VISUAL_EVIDENCE_UNCONFIRMED",
    "结论缺少视觉证据": "EVIDENCE.MISSING_VISUAL_EVIDENCE",
    "视觉素材与结论关联性弱": "EVIDENCE.WEAK_VISUAL_ALIGNMENT",
    "页数偏离目标": "ARCH.SLIDE_COUNT_DEVIATION",
    "必要章节未覆盖": "ARCH.REQUIRED_SECTION_MISSING",
    "章节缺少对应页面": "ARCH.CHAPTER_WITHOUT_SLIDES",
    "面积单位表述不一致": "ARCH.INCONSISTENT_AREA_UNITS",
    "概念汇报包含施工图级细节": "ARCH.CONCEPT_HAS_CONSTRUCTION_DETAIL",
    "总平面图缺少方位标注提示": "ARCH.PLAN_MISSING_NORTH_ARROW",
    "平面图缺少楼层标注提示": "ARCH.PLAN_MISSING_FLOOR_LABEL",
    "交通流线图缺少颜色图例提示": "ARCH.FLOW_DIAGRAM_MISSING_LEGEND",
    "页面信息密度过高": "LAYOUT.HIGH_TEXT_DENSITY",
    "单条要点过长": "LAYOUT.BULLET_TOO_LONG",
    "要点过多": "LAYOUT.TOO_MANY_BULLETS",
    "核心结论过长": "LAYOUT.MESSAGE_TOO_LONG",
    "缺少匹配素材": "LAYOUT.MISSING_ASSET",
    "素材分辨率偏低": "LAYOUT.LOW_RESOLUTION_ASSET",
    "素材宽高比极端": "LAYOUT.EXTREME_ASPECT_RATIO",
    "需人工确认版面调整": "LAYOUT.MANUAL_LAYOUT_CONFIRMATION",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_issues" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("review_issues")}
    if "rule_code" in columns:
        return

    with op.batch_alter_table("review_issues") as batch:
        batch.add_column(
            sa.Column(
                "rule_code",
                sa.String(length=100),
                nullable=True,
            )
        )

    review_issues = sa.table(
        "review_issues",
        sa.column("title", sa.String),
        sa.column("rule_code", sa.String),
    )
    for title, rule_code in _TITLE_TO_RULE_CODE.items():
        op.execute(
            review_issues.update()
            .where(review_issues.c.title == title)
            .values(rule_code=rule_code)
        )
    op.execute(
        review_issues.update()
        .where(review_issues.c.rule_code.is_(None))
        .values(rule_code="LEGACY.UNSPECIFIED")
    )

    with op.batch_alter_table("review_issues") as batch:
        batch.alter_column("rule_code", nullable=False)


def downgrade() -> None:
    pass
