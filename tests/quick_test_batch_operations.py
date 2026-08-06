"""
批量操作测试 - 快速验证版本

直接测试批量操作逻辑，最小化依赖
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_batch_operation_service_basic():
    """测试 BatchOperationService 基本功能"""

    # 创建简单的批量操作服务
    from archium.application.batch_operations import BatchOperationService

    # Mock UnitOfWork
    mock_uow = Mock()
    mock_uow.__enter__ = Mock(return_value=mock_uow)
    mock_uow.__exit__ = Mock(return_value=False)
    mock_uow.commit = Mock()
    mock_uow.rollback = Mock()

    service = BatchOperationService(mock_uow)

    # 测试：全部成功
    items = [1, 2, 3, 4, 5]
    result = service.execute(
        items=items,
        operation=lambda x: f"processed_{x}",
        operation_name="test_op"
    )

    assert result.total == 5
    assert result.success == 5
    assert result.failed == 0
    mock_uow.commit.assert_called_once()

    print("✅ 测试通过: BatchOperationService 基本功能")


def test_batch_operation_partial_failure():
    """测试部分失败场景"""

    from archium.application.batch_operations import BatchOperationService

    mock_uow = Mock()
    mock_uow.__enter__ = Mock(return_value=mock_uow)
    mock_uow.__exit__ = Mock(return_value=False)
    mock_uow.commit = Mock()

    service = BatchOperationService(mock_uow)

    # 操作：第 2 和第 4 项失败
    def operation_with_failures(item):
        if item in [2, 4]:
            raise ValueError(f"Failed on {item}")
        return f"processed_{item}"

    result = service.execute(
        items=[1, 2, 3, 4, 5],
        operation=operation_with_failures,
        operation_name="partial_fail_op",
        continue_on_error=True
    )

    assert result.total == 5
    assert result.success == 3
    assert result.failed == 2
    assert len(result.errors) == 2
    mock_uow.commit.assert_called_once()

    print("✅ 测试通过: 部分失败继续执行")


def test_batch_operation_stop_on_error():
    """测试遇错即停场景"""

    from archium.application.batch_operations import BatchOperationService

    mock_uow = Mock()
    mock_uow.__enter__ = Mock(return_value=mock_uow)
    mock_uow.__exit__ = Mock(return_value=False)
    mock_uow.rollback = Mock()

    service = BatchOperationService(mock_uow)

    def operation_fail_at_3(item):
        if item == 3:
            raise Exception("Critical error")
        return item

    result = service.execute(
        items=[1, 2, 3, 4, 5],
        operation=operation_fail_at_3,
        operation_name="stop_on_error",
        continue_on_error=False
    )

    assert result.total == 5
    assert result.success == 2  # 只处理了 1 和 2
    assert result.failed == 1
    assert result.skipped == 2  # 4 和 5 被跳过
    mock_uow.rollback.assert_called_once()

    print("✅ 测试通过: 遇错即停并回滚")


def test_batch_operation_result():
    """测试 BatchOperationResult 统计"""

    from archium.application.batch_operations import BatchOperationResult

    result = BatchOperationResult(
        total=10,
        success=7,
        failed=2,
        skipped=1,
        errors=["Error 1", "Error 2"]
    )

    assert result.success_rate == 0.7
    assert "7/10 成功" in result.summary()
    assert len(result.errors) == 2

    print("✅ 测试通过: BatchOperationResult 统计")


def test_presentation_batch_operations_mock():
    """测试 PresentationBatchOperations (使用 Mock)"""

    from archium.application.batch_operations import PresentationBatchOperations

    # Mock 依赖
    mock_uow = Mock()
    mock_uow.__enter__ = Mock(return_value=mock_uow)
    mock_uow.__exit__ = Mock(return_value=False)
    mock_uow.commit = Mock()

    mock_repo = Mock()
    mock_gen_service = Mock()

    ops = PresentationBatchOperations(mock_uow, mock_repo, mock_gen_service)

    # Mock slides
    mock_slides = [Mock(id=f"slide_{i}") for i in range(3)]
    mock_repo.get_slides_by_status.return_value = mock_slides

    # Mock 成功的生成
    mock_gen_service.generate_slide.return_value = Mock(status="COMPLETED")

    result = ops.batch_retry_failed_slides("pres_1")

    assert result.total == 3
    assert mock_gen_service.generate_slide.call_count == 3
    mock_uow.commit.assert_called()

    print("✅ 测试通过: PresentationBatchOperations 批量重试")


def test_outline_batch_operations_mock():
    """测试 OutlineBatchOperations (使用 Mock)"""

    from archium.application.batch_operations import OutlineBatchOperations

    mock_uow = Mock()
    mock_uow.__enter__ = Mock(return_value=mock_uow)
    mock_uow.__exit__ = Mock(return_value=False)
    mock_uow.commit = Mock()

    mock_repo = Mock()

    ops = OutlineBatchOperations(mock_uow, mock_repo)

    # Mock sections
    mock_sections = []
    for i in range(3):
        section = Mock()
        section.id = f"section_{i}"
        section.category = "old_category"
        section.target_page_count = 5
        mock_sections.append(section)

    mock_repo.get_section_by_id.side_effect = mock_sections

    result = ops.batch_update_section_property(
        section_ids=["section_0", "section_1", "section_2"],
        property_updates={"category": "new_category", "target_page_count": 10}
    )

    assert result.total == 3
    assert result.success == 3

    # 验证属性被更新
    for section in mock_sections:
        assert section.category == "new_category"
        assert section.target_page_count == 10

    mock_uow.commit.assert_called()

    print("✅ 测试通过: OutlineBatchOperations 批量更新章节")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("批量操作功能 - 快速验证测试")
    print("="*60 + "\n")

    try:
        test_batch_operation_service_basic()
        test_batch_operation_partial_failure()
        test_batch_operation_stop_on_error()
        test_batch_operation_result()
        test_presentation_batch_operations_mock()
        test_outline_batch_operations_mock()

        print("\n" + "="*60)
        print("✅ 所有测试通过！(6/6)")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
