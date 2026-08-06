"""
批量操作服务的单元测试

测试覆盖：
- BatchOperationService 核心逻辑
- PresentationBatchOperations 所有方法
- OutlineBatchOperations 所有方法
- 错误处理和事务回滚
- 边界条件和异常场景
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any
from datetime import datetime

from archium.application.batch_operations import (
    BatchOperationService,
    PresentationBatchOperations,
    OutlineBatchOperations,
    BatchOperationResult,
)
from archium.domain.models import (
    PresentationSlide,
    SlideStatus,
    OutlineSection,
    OutlinePageIntent,
    PageArchetype,
)
from archium.domain.repositories import (
    PresentationRepository,
    OutlineRepository,
)
from archium.application.services import PresentationGenerationService


# ==================== Fixtures ====================

@pytest.fixture
def mock_uow():
    """模拟 UnitOfWork"""
    uow = Mock()
    uow.__enter__ = Mock(return_value=uow)
    uow.__exit__ = Mock(return_value=False)
    uow.commit = Mock()
    uow.rollback = Mock()
    return uow


@pytest.fixture
def mock_presentation_repo():
    """模拟 PresentationRepository"""
    return Mock(spec=PresentationRepository)


@pytest.fixture
def mock_outline_repo():
    """模拟 OutlineRepository"""
    return Mock(spec=OutlineRepository)


@pytest.fixture
def mock_generation_service():
    """模拟 PresentationGenerationService"""
    return Mock(spec=PresentationGenerationService)


@pytest.fixture
def sample_slides() -> List[PresentationSlide]:
    """创建示例幻灯片列表"""
    slides = []
    for i in range(5):
        slide = PresentationSlide(
            id=f"slide_{i}",
            presentation_id="pres_1",
            page_number=i + 1,
            title=f"Slide {i + 1}",
            content=f"Content {i + 1}",
            status=SlideStatus.FAILED if i % 2 == 0 else SlideStatus.COMPLETED,
            error_message="Generation failed" if i % 2 == 0 else None,
        )
        slides.append(slide)
    return slides


@pytest.fixture
def sample_sections() -> List[OutlineSection]:
    """创建示例大纲章节"""
    sections = []
    for i in range(3):
        section = OutlineSection(
            id=f"section_{i}",
            outline_id="outline_1",
            title=f"Section {i + 1}",
            category="background",
            target_page_count=5,
            is_required=True,
            order_index=i,
        )
        sections.append(section)
    return sections


@pytest.fixture
def sample_page_intents() -> List[OutlinePageIntent]:
    """创建示例页面意图"""
    intents = []
    for i in range(5):
        intent = OutlinePageIntent(
            id=f"intent_{i}",
            section_id="section_0",
            outline_id="outline_1",
            page_number=i + 1,
            archetype=PageArchetype.TITLE if i == 0 else PageArchetype.CONTENT,
            layout_preference="title_only" if i == 0 else "content_heavy",
            key_message=f"Message {i + 1}",
        )
        intents.append(intent)
    return intents


# ==================== BatchOperationService Tests ====================

class TestBatchOperationService:
    """测试 BatchOperationService 核心逻辑"""

    def test_execute_all_success(self, mock_uow):
        """测试所有项目成功的场景"""
        # Arrange
        items = [1, 2, 3, 4, 5]

        def mock_operation(item):
            return f"processed_{item}"

        service = BatchOperationService(mock_uow)

        # Act
        result = service.execute(
            items=items,
            operation=mock_operation,
            operation_name="test_op"
        )

        # Assert
        assert result.total == 5
        assert result.success == 5
        assert result.failed == 0
        assert result.skipped == 0
        assert len(result.errors) == 0
        mock_uow.commit.assert_called_once()
        mock_uow.rollback.assert_not_called()

    def test_execute_partial_failure_continue_on_error(self, mock_uow):
        """测试部分失败且继续执行的场景"""
        # Arrange
        items = [1, 2, 3, 4, 5]

        def mock_operation(item):
            if item == 2 or item == 4:
                raise ValueError(f"Failed on item {item}")
            return f"processed_{item}"

        service = BatchOperationService(mock_uow)

        # Act
        result = service.execute(
            items=items,
            operation=mock_operation,
            operation_name="test_op",
            continue_on_error=True
        )

        # Assert
        assert result.total == 5
        assert result.success == 3
        assert result.failed == 2
        assert result.skipped == 0
        assert len(result.errors) == 2
        assert "item 2" in result.errors[0]
        assert "item 4" in result.errors[1]
        mock_uow.commit.assert_called_once()
        mock_uow.rollback.assert_not_called()

    def test_execute_failure_stop_on_error(self, mock_uow):
        """测试遇到错误立即停止的场景"""
        # Arrange
        items = [1, 2, 3, 4, 5]

        def mock_operation(item):
            if item == 3:
                raise ValueError("Critical error")
            return f"processed_{item}"

        service = BatchOperationService(mock_uow)

        # Act
        result = service.execute(
            items=items,
            operation=mock_operation,
            operation_name="test_op",
            continue_on_error=False
        )

        # Assert
        assert result.total == 5
        assert result.success == 2  # 只处理了 1 和 2
        assert result.failed == 1   # 3 失败
        assert result.skipped == 2  # 4 和 5 被跳过
        assert len(result.errors) == 1
        mock_uow.rollback.assert_called_once()
        mock_uow.commit.assert_not_called()

    def test_execute_empty_items(self, mock_uow):
        """测试空列表的场景"""
        # Arrange
        service = BatchOperationService(mock_uow)

        # Act
        result = service.execute(
            items=[],
            operation=lambda x: x,
            operation_name="test_op"
        )

        # Assert
        assert result.total == 0
        assert result.success == 0
        assert result.failed == 0
        assert result.skipped == 0
        mock_uow.commit.assert_called_once()

    def test_execute_with_progress_callback(self, mock_uow):
        """测试带进度回调的场景"""
        # Arrange
        items = [1, 2, 3]
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        service = BatchOperationService(mock_uow)

        # Act
        result = service.execute(
            items=items,
            operation=lambda x: x,
            operation_name="test_op",
            progress_callback=progress_callback
        )

        # Assert
        assert len(progress_calls) == 3
        assert progress_calls == [(1, 3), (2, 3), (3, 3)]


# ==================== PresentationBatchOperations Tests ====================

class TestPresentationBatchOperations:
    """测试 PresentationBatchOperations"""

    def test_batch_retry_failed_slides_success(
        self,
        mock_uow,
        mock_presentation_repo,
        mock_generation_service,
        sample_slides
    ):
        """测试批量重试失败幻灯片 - 成功场景"""
        # Arrange
        presentation_id = "pres_1"
        failed_slides = [s for s in sample_slides if s.status == SlideStatus.FAILED]

        mock_presentation_repo.get_slides_by_status.return_value = failed_slides
        mock_generation_service.generate_slide.return_value = Mock(
            status=SlideStatus.COMPLETED
        )

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            mock_generation_service
        )

        # Act
        result = ops.batch_retry_failed_slides(presentation_id)

        # Assert
        assert result.total == len(failed_slides)
        assert result.success == len(failed_slides)
        assert result.failed == 0

        # 验证 generate_slide 被调用的次数
        assert mock_generation_service.generate_slide.call_count == len(failed_slides)

        # 验证 UOW commit
        mock_uow.commit.assert_called()

    def test_batch_retry_failed_slides_partial_failure(
        self,
        mock_uow,
        mock_presentation_repo,
        mock_generation_service,
        sample_slides
    ):
        """测试批量重试 - 部分失败"""
        # Arrange
        presentation_id = "pres_1"
        failed_slides = [s for s in sample_slides if s.status == SlideStatus.FAILED]

        mock_presentation_repo.get_slides_by_status.return_value = failed_slides

        # 模拟部分成功部分失败
        call_count = 0
        def mock_generate(pres_id, slide_id):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Generation failed")
            return Mock(status=SlideStatus.COMPLETED)

        mock_generation_service.generate_slide.side_effect = mock_generate

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            mock_generation_service
        )

        # Act
        result = ops.batch_retry_failed_slides(
            presentation_id,
            continue_on_error=True
        )

        # Assert
        assert result.total == len(failed_slides)
        assert result.success > 0
        assert result.failed > 0
        assert result.success + result.failed == len(failed_slides)

    def test_batch_update_slide_property_success(
        self,
        mock_uow,
        mock_presentation_repo,
        sample_slides
    ):
        """测试批量更新幻灯片属性 - 成功"""
        # Arrange
        slide_ids = [s.id for s in sample_slides[:3]]
        mock_presentation_repo.get_by_id.side_effect = sample_slides[:3]

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            Mock()
        )

        # Act
        result = ops.batch_update_slide_property(
            slide_ids=slide_ids,
            property_updates={"notes": "Updated notes"}
        )

        # Assert
        assert result.total == 3
        assert result.success == 3
        assert result.failed == 0

        # 验证每个幻灯片的 notes 都被更新
        for slide in sample_slides[:3]:
            assert slide.notes == "Updated notes"

        mock_uow.commit.assert_called()

    def test_batch_update_slide_property_invalid_property(
        self,
        mock_uow,
        mock_presentation_repo,
        sample_slides
    ):
        """测试批量更新 - 无效属性"""
        # Arrange
        slide_ids = [s.id for s in sample_slides[:2]]
        mock_presentation_repo.get_by_id.side_effect = sample_slides[:2]

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            Mock()
        )

        # Act
        result = ops.batch_update_slide_property(
            slide_ids=slide_ids,
            property_updates={"invalid_property": "value"}
        )

        # Assert
        assert result.total == 2
        assert result.failed == 2
        assert "没有属性" in result.errors[0] or "does not have" in result.errors[0]

    def test_batch_delete_slides_success(
        self,
        mock_uow,
        mock_presentation_repo,
        sample_slides
    ):
        """测试批量删除幻灯片 - 成功"""
        # Arrange
        slide_ids = [s.id for s in sample_slides[:3]]

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            Mock()
        )

        # Act
        result = ops.batch_delete_slides(slide_ids)

        # Assert
        assert result.total == 3
        assert result.success == 3
        assert result.failed == 0

        # 验证 delete 被调用
        assert mock_presentation_repo.delete.call_count == 3
        mock_uow.commit.assert_called()

    def test_batch_skip_failed_slides(
        self,
        mock_uow,
        mock_presentation_repo,
        sample_slides
    ):
        """测试批量跳过失败幻灯片"""
        # Arrange
        presentation_id = "pres_1"
        failed_slides = [s for s in sample_slides if s.status == SlideStatus.FAILED]

        mock_presentation_repo.get_slides_by_status.return_value = failed_slides

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            Mock()
        )

        # Act
        result = ops.batch_skip_failed_slides(presentation_id)

        # Assert
        assert result.total == len(failed_slides)
        assert result.success == len(failed_slides)

        # 验证所有失败幻灯片状态改为 SKIPPED
        for slide in failed_slides:
            assert slide.status == SlideStatus.SKIPPED

        mock_uow.commit.assert_called()


# ==================== OutlineBatchOperations Tests ====================

class TestOutlineBatchOperations:
    """测试 OutlineBatchOperations"""

    def test_batch_update_section_property_success(
        self,
        mock_uow,
        mock_outline_repo,
        sample_sections
    ):
        """测试批量更新章节属性 - 成功"""
        # Arrange
        section_ids = [s.id for s in sample_sections]
        mock_outline_repo.get_section_by_id.side_effect = sample_sections

        ops = OutlineBatchOperations(mock_uow, mock_outline_repo)

        # Act
        result = ops.batch_update_section_property(
            section_ids=section_ids,
            property_updates={
                "category": "solution",
                "target_page_count": 10,
                "is_required": False
            }
        )

        # Assert
        assert result.total == 3
        assert result.success == 3
        assert result.failed == 0

        # 验证属性更新
        for section in sample_sections:
            assert section.category == "solution"
            assert section.target_page_count == 10
            assert section.is_required == False

        mock_uow.commit.assert_called()

    def test_batch_update_section_property_partial_update(
        self,
        mock_uow,
        mock_outline_repo,
        sample_sections
    ):
        """测试批量更新 - 只更新部分属性"""
        # Arrange
        section_ids = [s.id for s in sample_sections[:2]]
        mock_outline_repo.get_section_by_id.side_effect = sample_sections[:2]

        ops = OutlineBatchOperations(mock_uow, mock_outline_repo)

        # Act
        result = ops.batch_update_section_property(
            section_ids=section_ids,
            property_updates={"category": "technology"}
        )

        # Assert
        assert result.total == 2
        assert result.success == 2

        # 验证只有 category 被更新
        for section in sample_sections[:2]:
            assert section.category == "technology"
            # 其他属性保持不变
            assert section.target_page_count == 5
            assert section.is_required == True

    def test_batch_update_page_archetype_success(
        self,
        mock_uow,
        mock_outline_repo,
        sample_page_intents
    ):
        """测试批量更新页面原型 - 成功"""
        # Arrange
        intent_ids = [i.id for i in sample_page_intents]
        mock_outline_repo.get_page_intent_by_id.side_effect = sample_page_intents

        ops = OutlineBatchOperations(mock_uow, mock_outline_repo)

        # Act
        result = ops.batch_update_page_archetype(
            intent_ids=intent_ids,
            new_archetype=PageArchetype.DATA_VISUALIZATION,
            new_layout="chart_focused"
        )

        # Assert
        assert result.total == 5
        assert result.success == 5
        assert result.failed == 0

        # 验证更新
        for intent in sample_page_intents:
            assert intent.archetype == PageArchetype.DATA_VISUALIZATION
            assert intent.layout_preference == "chart_focused"

        mock_uow.commit.assert_called()

    def test_batch_update_page_archetype_only_archetype(
        self,
        mock_uow,
        mock_outline_repo,
        sample_page_intents
    ):
        """测试只更新原型不更新布局"""
        # Arrange
        intent_ids = [sample_page_intents[0].id]
        mock_outline_repo.get_page_intent_by_id.return_value = sample_page_intents[0]

        original_layout = sample_page_intents[0].layout_preference

        ops = OutlineBatchOperations(mock_uow, mock_outline_repo)

        # Act
        result = ops.batch_update_page_archetype(
            intent_ids=intent_ids,
            new_archetype=PageArchetype.TIMELINE,
            new_layout=None
        )

        # Assert
        assert result.success == 1
        assert sample_page_intents[0].archetype == PageArchetype.TIMELINE
        assert sample_page_intents[0].layout_preference == original_layout

    def test_batch_delete_page_intents_success(
        self,
        mock_uow,
        mock_outline_repo,
        sample_page_intents
    ):
        """测试批量删除页面意图 - 成功"""
        # Arrange
        intent_ids = [i.id for i in sample_page_intents[:3]]

        ops = OutlineBatchOperations(mock_uow, mock_outline_repo)

        # Act
        result = ops.batch_delete_page_intents(intent_ids)

        # Assert
        assert result.total == 3
        assert result.success == 3
        assert result.failed == 0

        assert mock_outline_repo.delete_page_intent.call_count == 3
        mock_uow.commit.assert_called()


# ==================== Integration Scenarios ====================

class TestBatchOperationIntegrationScenarios:
    """测试真实使用场景"""

    def test_scenario_retry_all_failed_in_large_presentation(
        self,
        mock_uow,
        mock_presentation_repo,
        mock_generation_service
    ):
        """场景：重试一个大型演示文稿中的所有失败页面"""
        # Arrange: 100 个页面，30 个失败
        failed_slides = []
        for i in range(30):
            slide = PresentationSlide(
                id=f"slide_{i}",
                presentation_id="large_pres",
                page_number=i + 1,
                status=SlideStatus.FAILED,
                error_message="Original error"
            )
            failed_slides.append(slide)

        mock_presentation_repo.get_slides_by_status.return_value = failed_slides

        # 模拟 80% 成功率
        success_count = 0
        def mock_generate(pres_id, slide_id):
            nonlocal success_count
            success_count += 1
            if success_count % 5 == 0:  # 每 5 个失败 1 个
                raise Exception("Still failed")
            return Mock(status=SlideStatus.COMPLETED)

        mock_generation_service.generate_slide.side_effect = mock_generate

        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            mock_generation_service
        )

        # Act
        result = ops.batch_retry_failed_slides(
            "large_pres",
            continue_on_error=True
        )

        # Assert
        assert result.total == 30
        assert result.success == 24  # 80% 成功
        assert result.failed == 6    # 20% 失败
        assert result.success_rate == 0.8

    def test_scenario_bulk_edit_outline_sections(
        self,
        mock_uow,
        mock_outline_repo
    ):
        """场景：批量编辑大纲章节属性"""
        # Arrange: 10 个章节需要统一修改
        sections = []
        for i in range(10):
            section = OutlineSection(
                id=f"section_{i}",
                outline_id="outline_1",
                title=f"Section {i}",
                category="background",
                target_page_count=5,
                is_required=True,
                order_index=i
            )
            sections.append(section)

        section_ids = [s.id for s in sections]
        mock_outline_repo.get_section_by_id.side_effect = sections

        ops = OutlineBatchOperations(mock_uow, mock_outline_repo)

        # Act: 将所有章节改为 solution 类别，页数改为 8
        result = ops.batch_update_section_property(
            section_ids=section_ids,
            property_updates={
                "category": "solution",
                "target_page_count": 8
            }
        )

        # Assert
        assert result.total == 10
        assert result.success == 10

        # 验证所有章节都被正确更新
        for section in sections:
            assert section.category == "solution"
            assert section.target_page_count == 8


# ==================== Edge Cases and Error Handling ====================

class TestEdgeCasesAndErrors:
    """测试边界条件和错误处理"""

    def test_empty_batch_operation(self, mock_uow):
        """测试空批次操作"""
        service = BatchOperationService(mock_uow)

        result = service.execute(
            items=[],
            operation=lambda x: x,
            operation_name="empty_op"
        )

        assert result.total == 0
        assert result.success == 0
        assert result.summary() == "empty_op 完成: 0/0 成功, 0 失败"

    def test_all_items_fail(self, mock_uow):
        """测试所有项目都失败"""
        items = [1, 2, 3]

        def failing_operation(item):
            raise ValueError(f"Failed on {item}")

        service = BatchOperationService(mock_uow)

        result = service.execute(
            items=items,
            operation=failing_operation,
            operation_name="all_fail",
            continue_on_error=True
        )

        assert result.total == 3
        assert result.success == 0
        assert result.failed == 3
        assert result.success_rate == 0.0

    def test_transaction_rollback_on_critical_error(self, mock_uow):
        """测试关键错误时的事务回滚"""
        items = [1, 2, 3, 4, 5]

        def operation_with_critical_error(item):
            if item == 3:
                raise Exception("Critical database error")
            return item

        service = BatchOperationService(mock_uow)

        result = service.execute(
            items=items,
            operation=operation_with_critical_error,
            operation_name="critical_error",
            continue_on_error=False
        )

        # 应该回滚事务
        mock_uow.rollback.assert_called_once()
        mock_uow.commit.assert_not_called()

        # 后续项目被跳过
        assert result.skipped == 2

    def test_none_values_in_batch(self, mock_uow, mock_presentation_repo):
        """测试批次中包含 None 值"""
        ops = PresentationBatchOperations(
            mock_uow,
            mock_presentation_repo,
            Mock()
        )

        # 包含 None 的 slide_ids
        slide_ids = ["slide_1", None, "slide_3"]

        mock_presentation_repo.get_by_id.side_effect = [
            Mock(id="slide_1"),
            None,
            Mock(id="slide_3")
        ]

        result = ops.batch_delete_slides(slide_ids)

        # 应该跳过 None 值或优雅处理
        assert result.total == 3
        # 可能 failed 或 skipped，取决于实现


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
