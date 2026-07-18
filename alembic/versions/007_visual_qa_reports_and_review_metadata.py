"""Visual QA report cache, review issue metadata, legacy rule_code backfill."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_visual_qa_reports_and_review_metadata"
down_revision: Union[str, None] = "006_review_issue_rule_code_index"
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
    "图像分辨率不足": "VISUAL.DIMENSIONS_TOO_SMALL",
    "图像空白边距过大": "VISUAL.EXCESSIVE_MARGINS",
    "图像对比度偏低": "VISUAL.LOW_COLOR_CONTRAST",
    "图像可能被裁切": "VISUAL.CONTENT_CLIPPED",
    "图纸文字密度过高": "VISUAL.HIGH_TEXT_DENSITY",
    "图像未检测到指北针": "VISUAL.MISSING_NORTH_ARROW",
    "图像未检测到图例区域": "VISUAL.MISSING_LEGEND",
    "图像类型与页面需求不一致": "VISUAL.DRAWING_TYPE_MISMATCH",
    "素材文件无法读取": "VISUAL.ASSET_UNREADABLE",
    "素材文件不存在": "VISUAL.ASSET_FILE_NOT_FOUND",
    "素材格式不支持": "VISUAL.ASSET_FORMAT_UNSUPPORTED",
    "素材解码失败": "VISUAL.ASSET_DECODE_FAILED",
    "素材权限不足": "VISUAL.ASSET_PERMISSION_DENIED",
    "素材记录缺失": "VISUAL.ASSET_RECORD_MISSING",
}

_LAYER_CATEGORY_RULE_CODE: tuple[tuple[str, str], ...] = (
    ("layout", "visual"),
    ("architectural", "visual"),
)


def _backfill_legacy_rule_codes() -> None:
    review_issues = sa.table(
        "review_issues",
        sa.column("title", sa.String),
        sa.column("reviewer_layer", sa.String),
        sa.column("category", sa.String),
        sa.column("rule_code", sa.String),
    )
    for title, rule_code in _TITLE_TO_RULE_CODE.items():
        op.execute(
            review_issues.update()
            .where(
                review_issues.c.rule_code == "LEGACY.UNSPECIFIED",
                review_issues.c.title == title,
            )
            .values(rule_code=rule_code)
        )
        op.execute(
            review_issues.update()
            .where(
                review_issues.c.rule_code == "LEGACY.UNSPECIFIED",
                review_issues.c.title == f"【疑似】{title}",
            )
            .values(rule_code=rule_code)
        )

    for layer, category in _LAYER_CATEGORY_RULE_CODE:
        op.execute(
            review_issues.update()
            .where(
                review_issues.c.rule_code == "LEGACY.UNSPECIFIED",
                review_issues.c.reviewer_layer == layer,
                review_issues.c.category == category,
                review_issues.c.title.like("%指北针%"),
            )
            .values(rule_code="VISUAL.MISSING_NORTH_ARROW")
        )
        op.execute(
            review_issues.update()
            .where(
                review_issues.c.rule_code == "LEGACY.UNSPECIFIED",
                review_issues.c.reviewer_layer == layer,
                review_issues.c.category == category,
                review_issues.c.title.like("%图例%"),
            )
            .values(rule_code="VISUAL.MISSING_LEGEND")
        )
        op.execute(
            review_issues.update()
            .where(
                review_issues.c.rule_code == "LEGACY.UNSPECIFIED",
                review_issues.c.reviewer_layer == layer,
                review_issues.c.category == category,
                review_issues.c.title.like("%分辨率%"),
            )
            .values(rule_code="VISUAL.DIMENSIONS_TOO_SMALL")
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "review_issues" in tables:
        columns = {column["name"] for column in inspector.get_columns("review_issues")}
        with op.batch_alter_table("review_issues") as batch:
            if "confidence" not in columns:
                batch.add_column(sa.Column("confidence", sa.Float(), nullable=True))
            if "detection_method" not in columns:
                batch.add_column(sa.Column("detection_method", sa.String(length=100), nullable=True))
            if "requires_confirmation" not in columns:
                batch.add_column(
                    sa.Column(
                        "requires_confirmation",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )

        if "rule_code" in columns:
            _backfill_legacy_rule_codes()

    if "visual_qa_reports" not in tables:
        op.create_table(
            "visual_qa_reports",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("asset_id", sa.Uuid(), nullable=False),
            sa.Column("file_hash", sa.String(length=64), nullable=False),
            sa.Column("analyzer_version", sa.String(length=32), nullable=False),
            sa.Column("report_json", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "asset_id",
                "file_hash",
                "analyzer_version",
                name="uq_visual_qa_asset_hash_version",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "visual_qa_reports" in tables:
        op.drop_table("visual_qa_reports")

    if "review_issues" in tables:
        columns = {column["name"] for column in inspector.get_columns("review_issues")}
        with op.batch_alter_table("review_issues") as batch:
            if "requires_confirmation" in columns:
                batch.drop_column("requires_confirmation")
            if "detection_method" in columns:
                batch.drop_column("detection_method")
            if "confidence" in columns:
                batch.drop_column("confidence")
