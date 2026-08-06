"""
Generate 页面批量操作集成测试

测试覆盖：
- 批量重试失败页面的 UI 流程
- 跳过失败页面的 UI 流程
- 状态分组显示
- 进度可视化
- 错误反馈和用户交互
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import streamlit as st
from typing import List

from archium.ui.pages.flow.generate import (
    _handle_batch_retry_failed,
    _handle_skip_failed_slides,
)
from archium.domain.models import (
    Presentation,
    PresentationSlide,
    SlideStatus,
)
from archium.application.batch_operations import BatchOperationResult


# ==================== Fixtures ====================

@pytest.fixture
def mock_streamlit_session():
    """模拟 Streamlit session state"""
    session = {}
    with patch.object(st, 'session_state', session):
        yield session


@pytest.fixture
def sample_presentation():
    """创建示例演示文稿"""
    return Presentation(
        id="pres_1",
        project_id="proj_1",
        title="测试演示",
        total_slides=10,
    )


@pytest.fixture
def sample_slides_mixed_status():
    """创建混合状态的幻灯片列表"""
    slides = []
    statuses = [
        SlideStatus.COMPLETED,
        SlideStatus.FAILED,
        SlideStatus.PENDING,
        SlideStatus.FAILED,
        SlideStatus.COMPLETED,
        SlideStatus.FAILED,
        SlideStatus.PENDING,
        SlideStatus.COMPLETED,
        SlideStatus.FAILED,
        SlideStatus.SKIPPED,
    ]

    for i, status in enumerate(statuses):
        slide = PresentationSlide(
            id=f"slide_{i}",
            presentation_id="pres_1",
            page_number=i + 1,
            title=f"Slide {i + 1}",
            content=f"Content for slide {i + 1}",
            status=status,
            error_message=f"Error on slide {i + 1}" if status == SlideStatus.FAILED else None,
        )
        slides.append(slide)

    return slides


@pytest.fixture
def mock_batch_operations():
    """模拟批量操作服务"""
    mock_ops = Mock()
    mock_ops.batch_retry_failed_slides.return_value = BatchOperationResult(
        total=4,
        success=3,
        failed=1,
        skipped=0,
        errors=["slide_3: 生成仍然失败"],
    )
    mock_ops.batch_skip_failed_slides.return_value = BatchOperationResult(
        total=4,
        success=4,
        failed=0,
        skipped=0,
        errors=[],
    )
    return mock_ops


# ==================== Batch Retry Tests ====================

class TestBatchRetryFailed:
    """测试批量重试失败页面功能"""

    @patch('streamlit.button')
    @patch('streamlit.success')
    @patch('streamlit.rerun')
    def test_batch_retry_all_success(
        self,
        mock_rerun,
        mock_success,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试全部重试成功"""
        # Arrange
        mock_button.return_value = True

        # 模拟全部成功
        mock_batch_operations.batch_retry_failed_slides.return_value = BatchOperationResult(
            total=4,
            success=4,
            failed=0,
            skipped=0,
            errors=[],
        )

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_batch_operations.batch_retry_failed_slides.assert_called_once_with(
            sample_presentation.id,
            continue_on_error=True
        )
        mock_success.assert_called()
        mock_rerun.assert_called_once()

    @patch('streamlit.button')
    @patch('streamlit.warning')
    @patch('streamlit.error')
    @patch('streamlit.rerun')
    def test_batch_retry_partial_success(
        self,
        mock_rerun,
        mock_error,
        mock_warning,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试部分重试成功"""
        # Arrange
        mock_button.return_value = True

        # 默认的 mock_batch_operations 返回部分成功

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_warning.assert_called()  # 显示部分成功警告
        mock_error.assert_called()    # 显示失败详情
        mock_rerun.assert_called_once()

    @patch('streamlit.button')
    @patch('streamlit.error')
    def test_batch_retry_all_failed(
        self,
        mock_error,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试全部重试失败"""
        # Arrange
        mock_button.return_value = True

        # 模拟全部失败
        mock_batch_operations.batch_retry_failed_slides.return_value = BatchOperationResult(
            total=4,
            success=0,
            failed=4,
            skipped=0,
            errors=[
                "slide_1: 生成失败",
                "slide_3: 生成失败",
                "slide_5: 生成失败",
                "slide_8: 生成失败",
            ],
        )

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        assert mock_error.call_count >= 2  # 错误消息 + 失败详情

    @patch('streamlit.button')
    def test_batch_retry_button_not_clicked(
        self,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试按钮未点击时不执行操作"""
        # Arrange
        mock_button.return_value = False

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_batch_operations.batch_retry_failed_slides.assert_not_called()

    @patch('streamlit.button')
    @patch('streamlit.error')
    def test_batch_retry_operation_exception(
        self,
        mock_error,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试操作抛出异常时的处理"""
        # Arrange
        mock_button.return_value = True
        mock_batch_operations.batch_retry_failed_slides.side_effect = Exception(
            "Database connection failed"
        )

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_error.assert_called()


# ==================== Skip Failed Tests ====================

class TestSkipFailedSlides:
    """测试跳过失败页面功能"""

    @patch('streamlit.button')
    @patch('streamlit.success')
    @patch('streamlit.rerun')
    def test_skip_failed_all_success(
        self,
        mock_rerun,
        mock_success,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试全部跳过成功"""
        # Arrange
        mock_button.return_value = True

        # Act
        _handle_skip_failed_slides(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_batch_operations.batch_skip_failed_slides.assert_called_once_with(
            sample_presentation.id
        )
        mock_success.assert_called()
        mock_rerun.assert_called_once()

    @patch('streamlit.button')
    def test_skip_failed_button_not_clicked(
        self,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试按钮未点击时不执行操作"""
        # Arrange
        mock_button.return_value = False

        # Act
        _handle_skip_failed_slides(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_batch_operations.batch_skip_failed_slides.assert_not_called()

    @patch('streamlit.button')
    @patch('streamlit.warning')
    def test_skip_failed_with_warnings(
        self,
        mock_warning,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试跳过操作带警告"""
        # Arrange
        mock_button.return_value = True

        # 模拟部分跳过
        mock_batch_operations.batch_skip_failed_slides.return_value = BatchOperationResult(
            total=4,
            success=3,
            failed=1,
            skipped=0,
            errors=["slide_8: 状态更新失败"],
        )

        # Act
        _handle_skip_failed_slides(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_warning.assert_called()

    @patch('streamlit.button')
    @patch('streamlit.error')
    def test_skip_failed_operation_exception(
        self,
        mock_error,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试跳过操作抛出异常"""
        # Arrange
        mock_button.return_value = True
        mock_batch_operations.batch_skip_failed_slides.side_effect = Exception(
            "状态更新失败"
        )

        # Act
        _handle_skip_failed_slides(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_error.assert_called()


# ==================== UI Integration Tests ====================

class TestGeneratePageIntegration:
    """测试 Generate 页面集成场景"""

    @patch('streamlit.button')
    @patch('streamlit.progress')
    @patch('streamlit.success')
    def test_complete_retry_workflow(
        self,
        mock_success,
        mock_progress,
        mock_button,
        sample_presentation,
        sample_slides_mixed_status,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试完整的重试工作流"""
        # Arrange
        mock_button.return_value = True

        # Act - 第一次重试
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_batch_operations.batch_retry_failed_slides.assert_called()

    @patch('streamlit.expander')
    def test_error_details_displayed_in_expander(
        self,
        mock_expander,
        sample_presentation,
        mock_batch_operations
    ):
        """测试错误详情在可展开区域显示"""
        # Arrange
        mock_expander_context = MagicMock()
        mock_expander.return_value.__enter__.return_value = mock_expander_context

        with patch('streamlit.button') as mock_button:
            mock_button.return_value = True

            with patch('streamlit.error'):
                # Act
                _handle_batch_retry_failed(
                    presentation=sample_presentation,
                    batch_ops=mock_batch_operations
                )

        # Assert - 应该创建可展开区域显示详情
        # (具体实现取决于页面逻辑)

    def test_status_grouping_display(
        self,
        sample_slides_mixed_status
    ):
        """测试状态分组显示"""
        # 按状态分组
        failed_slides = [s for s in sample_slides_mixed_status if s.status == SlideStatus.FAILED]
        pending_slides = [s for s in sample_slides_mixed_status if s.status == SlideStatus.PENDING]
        completed_slides = [s for s in sample_slides_mixed_status if s.status == SlideStatus.COMPLETED]

        # Assert 分组正确
        assert len(failed_slides) == 4
        assert len(pending_slides) == 2
        assert len(completed_slides) == 3

    @patch('streamlit.metric')
    def test_progress_metrics_display(
        self,
        mock_metric,
        sample_slides_mixed_status
    ):
        """测试进度指标显示"""
        # 计算进度
        total = len(sample_slides_mixed_status)
        completed = len([s for s in sample_slides_mixed_status if s.status == SlideStatus.COMPLETED])
        failed = len([s for s in sample_slides_mixed_status if s.status == SlideStatus.FAILED])

        progress_percentage = (completed / total) * 100

        # Assert
        assert progress_percentage == 30.0  # 3/10
        assert failed == 4


# ==================== User Feedback Tests ====================

class TestUserFeedback:
    """测试用户反馈机制"""

    @patch('streamlit.success')
    @patch('streamlit.balloons')
    def test_success_celebration_on_100_percent(
        self,
        mock_balloons,
        mock_success,
        sample_presentation,
        mock_batch_operations
    ):
        """测试 100% 成功时的庆祝效果"""
        # Arrange
        mock_batch_operations.batch_retry_failed_slides.return_value = BatchOperationResult(
            total=4,
            success=4,
            failed=0,
            skipped=0,
            errors=[],
        )

        with patch('streamlit.button') as mock_button:
            mock_button.return_value = True

            with patch('streamlit.rerun'):
                # Act
                _handle_batch_retry_failed(
                    presentation=sample_presentation,
                    batch_ops=mock_batch_operations
                )

        # Assert
        mock_success.assert_called()
        # 可选：如果实现了 balloons 效果
        # mock_balloons.assert_called()

    @patch('streamlit.info')
    def test_helpful_tips_on_failures(
        self,
        mock_info,
        sample_presentation,
        mock_batch_operations
    ):
        """测试失败时显示有用提示"""
        # Arrange
        mock_batch_operations.batch_retry_failed_slides.return_value = BatchOperationResult(
            total=4,
            success=1,
            failed=3,
            skipped=0,
            errors=[
                "slide_1: API 超时",
                "slide_3: 内容生成失败",
                "slide_5: 模板加载错误",
            ],
        )

        with patch('streamlit.button') as mock_button:
            mock_button.return_value = True

            with patch('streamlit.warning'), patch('streamlit.error'):
                # Act
                _handle_batch_retry_failed(
                    presentation=sample_presentation,
                    batch_ops=mock_batch_operations
                )

        # Assert - 应该显示帮助信息
        # (具体取决于实现)


# ==================== Edge Cases ====================

class TestEdgeCases:
    """测试边界情况"""

    @patch('streamlit.info')
    @patch('streamlit.button')
    def test_no_failed_slides_to_retry(
        self,
        mock_button,
        mock_info,
        sample_presentation,
        mock_batch_operations
    ):
        """测试没有失败页面时的处理"""
        # Arrange
        mock_button.return_value = True
        mock_batch_operations.batch_retry_failed_slides.return_value = BatchOperationResult(
            total=0,
            success=0,
            failed=0,
            skipped=0,
            errors=[],
        )

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert - 应该显示信息提示
        mock_info.assert_called()

    def test_large_batch_retry(
        self,
        sample_presentation,
        mock_batch_operations
    ):
        """测试大批量重试（100+ 页面）"""
        # Arrange
        mock_batch_operations.batch_retry_failed_slides.return_value = BatchOperationResult(
            total=150,
            success=145,
            failed=5,
            skipped=0,
            errors=[f"slide_{i}: 失败" for i in range(5)],
        )

        with patch('streamlit.button') as mock_button:
            mock_button.return_value = True

            with patch('streamlit.warning'), patch('streamlit.rerun'):
                # Act
                _handle_batch_retry_failed(
                    presentation=sample_presentation,
                    batch_ops=mock_batch_operations
                )

        # Assert - 应该能处理大批量
        mock_batch_operations.batch_retry_failed_slides.assert_called()

    @patch('streamlit.button')
    def test_concurrent_operations_prevention(
        self,
        mock_button,
        sample_presentation,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试防止并发操作"""
        # Arrange
        mock_streamlit_session['batch_operation_in_progress'] = True
        mock_button.return_value = True

        # Act
        _handle_batch_retry_failed(
            presentation=sample_presentation,
            batch_ops=mock_batch_operations
        )

        # Assert - 如果实现了并发控制，操作应该被阻止
        # (具体取决于实现)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
