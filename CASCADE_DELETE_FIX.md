# 级联删除修复文档

## 问题描述

删除项目时出现以下错误：

```
sqlite3.IntegrityError: NOT NULL constraint failed: presentations.project_id
[SQL: UPDATE presentations SET project_id=?, updated_at=? WHERE presentations.id = ?]
[parameters: (None, '2026-07-19 15:43:40.364823', 'bf4d853815cb485a864e709bbe330a5d')]
```

**根本原因：**
- 虽然数据库外键配置了 `ondelete="CASCADE"`，但 SQLAlchemy 的 relationship 缺少 `cascade="all, delete-orphan"` 配置
- 当删除父记录（Project）时，SQLAlchemy 尝试将子记录的外键设置为 NULL，而不是删除子记录
- 因为 `presentations.project_id` 有 `nullable=False` 约束，所以操作失败

## 修复内容

### 1. ProjectORM 关系配置修复

**文件：** `archium/infrastructure/database/models.py`

**修改前：**
```python
documents: Mapped[list[SourceDocumentORM]] = relationship(back_populates="project")
presentations: Mapped[list[PresentationORM]] = relationship(back_populates="project")
facts: Mapped[list[ProjectFactORM]] = relationship(back_populates="project")
assets: Mapped[list[AssetORM]] = relationship(back_populates="project")
```

**修改后：**
```python
documents: Mapped[list[SourceDocumentORM]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
)
presentations: Mapped[list[PresentationORM]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
)
facts: Mapped[list[ProjectFactORM]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
)
assets: Mapped[list[AssetORM]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan",
)
```

### 2. PresentationORM 关系配置修复

**修改前：**
```python
briefs: Mapped[list[PresentationBriefORM]] = relationship(back_populates="presentation")
storylines: Mapped[list[StorylineORM]] = relationship(back_populates="presentation")
slides: Mapped[list[SlideORM]] = relationship(back_populates="presentation")
review_issues: Mapped[list[ReviewIssueORM]] = relationship(back_populates="presentation")
```

**修改后：**
```python
briefs: Mapped[list[PresentationBriefORM]] = relationship(
    back_populates="presentation",
    cascade="all, delete-orphan",
)
storylines: Mapped[list[StorylineORM]] = relationship(
    back_populates="presentation",
    cascade="all, delete-orphan",
)
slides: Mapped[list[SlideORM]] = relationship(
    back_populates="presentation",
    cascade="all, delete-orphan",
)
review_issues: Mapped[list[ReviewIssueORM]] = relationship(
    back_populates="presentation",
    cascade="all, delete-orphan",
)
```

### 3. SourceDocumentORM 关系配置修复

**修改前：**
```python
chunks: Mapped[list[DocumentChunkORM]] = relationship(back_populates="document")
```

**修改后：**
```python
chunks: Mapped[list[DocumentChunkORM]] = relationship(
    back_populates="document",
    cascade="all, delete-orphan",
)
```

## 级联删除层级

现在删除项目时，会按照以下层级自动删除所有相关数据：

```
Project (项目)
├── Documents (文档)
│   └── Chunks (文档块) ✓
├── Presentations (汇报)
│   ├── Briefs (需求文档) ✓
│   ├── Storylines (故事线) ✓
│   ├── Slides (幻灯片) ✓
│   └── ReviewIssues (审阅问题) ✓
├── Facts (事实) ✓
├── Assets (资产) ✓
└── Missions (任务) ✓ (已有配置)
```

## cascade="all, delete-orphan" 说明

这个配置包含两个部分：

1. **`all`**: 包含以下所有级联操作
   - `save-update`: 保存父对象时同时保存子对象
   - `merge`: 合并父对象时同时合并子对象
   - `refresh-expire`: 刷新父对象时同时刷新子对象
   - `expunge`: 从 session 移除父对象时同时移除子对象
   - `delete`: **删除父对象时同时删除子对象** ← 这是我们需要的

2. **`delete-orphan`**: 当子对象与父对象解除关联时（成为孤儿），自动删除该子对象

## 测试建议

1. **创建测试项目**：包含多个 presentations、documents、facts
2. **删除项目**：在项目管理页面点击删除
3. **验证**：确认所有相关数据都被正确删除，没有孤儿记录

## 注意事项

- 这些修改只影响 SQLAlchemy ORM 层的行为
- 数据库外键约束 `ondelete="CASCADE"` 保持不变，作为额外的安全保障
- 如果已有孤儿数据，需要手动清理
- 修改后需要重启应用以使新配置生效

## 相关文件

- `archium/infrastructure/database/models.py` - 数据库模型定义
- `archium/ui/pages/project_management.py` - 项目删除 UI
- `archium/infrastructure/database/repositories.py` - 仓储层删除逻辑
