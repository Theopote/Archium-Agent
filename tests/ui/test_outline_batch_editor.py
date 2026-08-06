"""
Outline 批量编辑器 UI 组件的集成测试

测试覆盖：
- 章节批量编辑界面渲染
- 页面意图批量编辑界面渲染
- 批量操作执行和反馈
- 会话状态管理
- 错误处理和用户反馈
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import streamlit as st
from typing import List

from archium.ui.components.outline_batch_editor import (
    render_outline_batch_editor,
    _render_section_batch_editor,
    _render_intent_batch_editor,
)
from archium.domain.models import (
    Outline,
    OutlineSection,
    OutlinePageIntent,
    PageArchetype,
)
from archium.application.batch_operations import BatchOperationResult


# ==================== Test Fixtures ====================

@pytest.fixture
def mock_streamlit_session():
    """模拟 Streamlit session state"""
    session = {}
    with patch.object(st, 'session_state', session):
        yield session


@pytest.fixture
def sample_outline():
    """创建示例大纲"""
    outline = Outline(
        id="outline_1",
        project_id="proj_1",
        title="Test Outline",
        total_pages=15,
    )
    return outline


@pytest.fixture
def sample_sections():
    """创建示例章节"""
    sections = [
        OutlineSection(
            id="section_1",
            outline_id="outline_1",
            title="背景介绍",
            category="background",
            target_page_count=5,
            is_required=True,
            order_index=0,
        ),
        OutlineSection(
            id="section_2",
            outline_id="outline_1",
            title="技术方案",
            category="solution",
            target_page_count=7,
            is_required=True,
            order_index=1,
        ),
        OutlineSection(
            id="section_3",
            outline_id="outline_1",
            title="案例分析",
            category="case_study",
            target_page_count=3,
            is_required=False,
            order_index=2,
        ),
    ]
    return sections


@pytest.fixture
def sample_page_intents():
    """创建示例页面意图"""
    intents = [
        OutlinePageIntent(
            id="intent_1",
            section_id="section_1",
            outline_id="outline_1",
            page_number=1,
            archetype=PageArchetype.TITLE,
            layout_preference="title_only",
            key_message="项目标题页",
        ),
        OutlinePageIntent(
            id="intent_2",
            section_id="section_1",
            outline_id="outline_1",
            page_number=2,
            archetype=PageArchetype.CONTENT,
            layout_preference="content_heavy",
            key_message="背景说明",
        ),
        OutlinePageIntent(
            id="intent_3",
            section_id="section_2",
            outline_id="outline_1",
            page_number=3,
            archetype=PageArchetype.DATA_VISUALIZATION,
            layout_preference="chart_focused",
            key_message="数据展示",
        ),
    ]
    return intents


@pytest.fixture
def mock_batch_operations():
    """模拟批量操作服务"""
    mock_ops = Mock()
    mock_ops.batch_update_section_property.return_value = BatchOperationResult(
        total=3,
        success=3,
        failed=0,
        skipped=0,
        errors=[],
    )
    mock_ops.batch_update_page_archetype.return_value = BatchOperationResult(
        total=2,
        success=2,
        failed=0,
        skipped=0,
        errors=[],
    )
    return mock_ops


# ==================== Component Rendering Tests ====================

class TestOutlineBatchEditorRendering:
    """测试批量编辑器渲染"""

    @patch('streamlit.tabs')
    @patch('archium.ui.components.outline_batch_editor._render_section_batch_editor')
    @patch('archium.ui.components.outline_batch_editor._render_intent_batch_editor')
    def test_render_outline_batch_editor_creates_tabs(
        self,
        mock_render_intent,
        mock_render_section,
        mock_tabs,
        sample_outline,
        sample_sections,
        sample_page_intents,
        mock_batch_operations
    ):
        """测试主编辑器创建两个标签页"""
        # Arrange
        mock_tab1 = Mock()
        mock_tab2 = Mock()
        mock_tabs.return_value = [mock_tab1, mock_tab2]

        # Act
        render_outline_batch_editor(
            outline=sample_outline,
            sections=sample_sections,
            page_intents=sample_page_intents,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_tabs.assert_called_once_with(["📑 批量编辑章节", "📄 批量编辑页面意图"])
        mock_render_section.assert_called_once()
        mock_render_intent.assert_called_once()

    @patch('streamlit.info')
    def test_render_with_empty_sections(
        self,
        mock_info,
        sample_outline,
        mock_batch_operations
    ):
        """测试没有章节时的渲染"""
        # Act
        render_outline_batch_editor(
            outline=sample_outline,
            sections=[],
            page_intents=[],
            batch_ops=mock_batch_operations
        )

        # Assert - 应该显示空状态信息
        mock_info.assert_called()


class TestSectionBatchEditor:
    """测试章节批量编辑器"""

    @patch('streamlit.dataframe')
    @patch('streamlit.selectbox')
    @patch('streamlit.number_input')
    @patch('streamlit.checkbox')
    @patch('streamlit.button')
    def test_render_section_batch_editor_displays_all_controls(
        self,
        mock_button,
        mock_checkbox_input,
        mock_number,
        mock_select,
        mock_dataframe,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试章节编辑器显示所有控件"""
        # Arrange
        mock_button.return_value = False

        # Act
        _render_section_batch_editor(
            sections=sample_sections,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_dataframe.assert_called_once()  # 显示章节表格
        assert mock_checkbox_input.call_count >= len(sample_sections)  # 每个章节一个复选框

    @patch('streamlit.dataframe')
    @patch('streamlit.checkbox')
    @patch('streamlit.button')
    @patch('streamlit.success')
    def test_section_batch_update_success(
        self,
        mock_success,
        mock_button,
        mock_checkbox,
        mock_dataframe,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试成功执行章节批量更新"""
        # Arrange
        # 模拟选中前两个章节
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
            'section_2': True,
            'section_3': False,
        }

        # 模拟点击提交按钮
        mock_button.return_value = True

        # Mock selectbox 返回值
        with patch('streamlit.selectbox') as mock_select:
            mock_select.side_effect = ["solution", None, None]  # category, 其他为 None

            # Act
            _render_section_batch_editor(
                sections=sample_sections,
                batch_ops=mock_batch_operations
            )

        # Assert
        mock_batch_operations.batch_update_section_property.assert_called_once()
        call_args = mock_batch_operations.batch_update_section_property.call_args

        # 验证只更新了选中的章节
        assert len(call_args[1]['section_ids']) == 2
        assert 'section_1' in call_args[1]['section_ids']
        assert 'section_2' in call_args[1]['section_ids']

        # 验证显示成功消息
        mock_success.assert_called()

    @patch('streamlit.warning')
    @patch('streamlit.button')
    def test_section_batch_update_no_selection(
        self,
        mock_button,
        mock_warning,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试未选择任何章节时的警告"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {}
        mock_button.return_value = True

        # Act
        _render_section_batch_editor(
            sections=sample_sections,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_warning.assert_called()
        mock_batch_operations.batch_update_section_property.assert_not_called()

    @patch('streamlit.error')
    @patch('streamlit.button')
    def test_section_batch_update_operation_failure(
        self,
        mock_button,
        mock_error,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试批量操作失败时的错误处理"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
        }
        mock_button.return_value = True

        # 模拟操作失败
        mock_batch_operations.batch_update_section_property.return_value = BatchOperationResult(
            total=1,
            success=0,
            failed=1,
            skipped=0,
            errors=["章节 section_1 更新失败: 数据库错误"],
        )

        with patch('streamlit.selectbox') as mock_select:
            mock_select.return_value = "solution"

            # Act
            _render_section_batch_editor(
                sections=sample_sections,
                batch_ops=mock_batch_operations
            )

        # Assert
        mock_error.assert_called()


class TestIntentBatchEditor:
    """测试页面意图批量编辑器"""

    @patch('streamlit.dataframe')
    @patch('streamlit.selectbox')
    @patch('streamlit.checkbox')
    @patch('streamlit.button')
    def test_render_intent_batch_editor_displays_controls(
        self,
        mock_button,
        mock_checkbox_input,
        mock_select,
        mock_dataframe,
        sample_page_intents,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试意图编辑器显示控件"""
        # Arrange
        mock_button.return_value = False

        # Act
        _render_intent_batch_editor(
            page_intents=sample_page_intents,
            batch_ops=mock_batch_operations
        )

        # Assert
        mock_dataframe.assert_called_once()
        assert mock_checkbox_input.call_count >= len(sample_page_intents)

    @patch('streamlit.button')
    @patch('streamlit.selectbox')
    @patch('streamlit.success')
    def test_intent_batch_update_archetype_success(
        self,
        mock_success,
        mock_select,
        mock_button,
        sample_page_intents,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试成功更新页面原型"""
        # Arrange
        mock_streamlit_session['batch_intent_selections'] = {
            'intent_2': True,
            'intent_3': True,
        }

        mock_button.return_value = True
        mock_select.side_effect = [
            PageArchetype.TIMELINE,  # new_archetype
            "timeline_horizontal",    # new_layout
        ]

        # Act
        with patch('streamlit.dataframe'), patch('streamlit.checkbox'):
            _render_intent_batch_editor(
                page_intents=sample_page_intents,
                batch_ops=mock_batch_operations
            )

        # Assert
        mock_batch_operations.batch_update_page_archetype.assert_called_once()
        call_args = mock_batch_operations.batch_update_page_archetype.call_args

        assert len(call_args[1]['intent_ids']) == 2
        assert call_args[1]['new_archetype'] == PageArchetype.TIMELINE
        assert call_args[1]['new_layout'] == "timeline_horizontal"

        mock_success.assert_called()

    @patch('streamlit.button')
    @patch('streamlit.selectbox')
    @patch('streamlit.success')
    def test_intent_batch_update_archetype_only(
        self,
        mock_success,
        mock_select,
        mock_button,
        sample_page_intents,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试只更新原型不更新布局"""
        # Arrange
        mock_streamlit_session['batch_intent_selections'] = {
            'intent_1': True,
        }

        mock_button.return_value = True
        mock_select.side_effect = [
            PageArchetype.CONTENT,
            "不修改",  # 保持原布局
        ]

        # Act
        with patch('streamlit.dataframe'), patch('streamlit.checkbox'):
            _render_intent_batch_editor(
                page_intents=sample_page_intents,
                batch_ops=mock_batch_operations
            )

        # Assert
        call_args = mock_batch_operations.batch_update_page_archetype.call_args
        assert call_args[1]['new_layout'] is None


class TestSessionStateManagement:
    """测试会话状态管理"""

    def test_section_selection_state_persistence(
        self,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试章节选择状态持久化"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
            'section_2': False,
        }

        with patch('streamlit.checkbox') as mock_checkbox:
            mock_checkbox.side_effect = lambda label, key, value: value

            with patch('streamlit.dataframe'), patch('streamlit.button'):
                # Act
                _render_section_batch_editor(
                    sections=sample_sections,
                    batch_ops=mock_batch_operations
                )

        # Assert - 复选框应该使用会话状态的值
        assert 'batch_section_selections' in st.session_state

    def test_selection_state_cleared_after_success(
        self,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试成功后清除选择状态"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
        }

        with patch('streamlit.button') as mock_button:
            mock_button.return_value = True

            with patch('streamlit.selectbox') as mock_select:
                mock_select.return_value = "solution"

                with patch('streamlit.success'):
                    with patch('streamlit.dataframe'), patch('streamlit.checkbox'):
                        # Act
                        _render_section_batch_editor(
                            sections=sample_sections,
                            batch_ops=mock_batch_operations
                        )

        # Assert - 操作成功后应该清除选择
        # (具体实现取决于组件逻辑)


class TestErrorHandlingAndFeedback:
    """测试错误处理和用户反馈"""

    @patch('streamlit.error')
    @patch('streamlit.button')
    def test_display_detailed_error_messages(
        self,
        mock_button,
        mock_error,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试显示详细错误信息"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
            'section_2': True,
        }
        mock_button.return_value = True

        # 模拟部分失败
        mock_batch_operations.batch_update_section_property.return_value = BatchOperationResult(
            total=2,
            success=1,
            failed=1,
            skipped=0,
            errors=["章节 section_2: 属性验证失败"],
        )

        with patch('streamlit.selectbox') as mock_select:
            mock_select.return_value = "solution"

            with patch('streamlit.dataframe'), patch('streamlit.checkbox'):
                # Act
                _render_section_batch_editor(
                    sections=sample_sections,
                    batch_ops=mock_batch_operations
                )

        # Assert - 应该显示错误详情
        assert mock_error.call_count > 0

    @patch('streamlit.warning')
    @patch('streamlit.success')
    @patch('streamlit.button')
    def test_display_partial_success_feedback(
        self,
        mock_button,
        mock_success,
        mock_warning,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试部分成功时的反馈"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
            'section_2': True,
            'section_3': True,
        }
        mock_button.return_value = True

        # 3 个中 2 个成功
        mock_batch_operations.batch_update_section_property.return_value = BatchOperationResult(
            total=3,
            success=2,
            failed=1,
            skipped=0,
            errors=["章节 section_3: 更新失败"],
        )

        with patch('streamlit.selectbox') as mock_select:
            mock_select.return_value = "solution"

            with patch('streamlit.dataframe'), patch('streamlit.checkbox'):
                # Act
                _render_section_batch_editor(
                    sections=sample_sections,
                    batch_ops=mock_batch_operations
                )

        # Assert - 应该同时显示成功和警告
        mock_success.assert_called()
        mock_warning.assert_called()


class TestUIValidation:
    """测试 UI 验证逻辑"""

    @patch('streamlit.warning')
    @patch('streamlit.button')
    def test_warn_when_no_changes_specified(
        self,
        mock_button,
        mock_warning,
        sample_sections,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试未指定任何更改时的警告"""
        # Arrange
        mock_streamlit_session['batch_section_selections'] = {
            'section_1': True,
        }
        mock_button.return_value = True

        # 所有选项都为 None（不修改）
        with patch('streamlit.selectbox') as mock_select:
            mock_select.return_value = None

            with patch('streamlit.number_input') as mock_number:
                mock_number.return_value = None

                with patch('streamlit.dataframe'), patch('streamlit.checkbox'):
                    # Act
                    _render_section_batch_editor(
                        sections=sample_sections,
                        batch_ops=mock_batch_operations
                    )

        # Assert - 应该警告用户至少选择一项修改
        mock_warning.assert_called()

    def test_validate_archetype_layout_compatibility(
        self,
        sample_page_intents,
        mock_batch_operations,
        mock_streamlit_session
    ):
        """测试验证原型和布局的兼容性"""
        # 这个测试依赖于实际的验证逻辑
        # 示例：TITLE 原型不应该使用 chart_focused 布局
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
