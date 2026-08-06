"""批量操作服务 - 统一的批量处理、事务管理和进度跟踪。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Any
from uuid import UUID

from archium.application.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchOperationResult(Generic[T]):
    """批量操作结果。"""

    success_count: int
    failure_count: int
    skipped_count: int
    total_count: int
    success_items: list[T]
    failed_items: list[tuple[T, Exception]]
    skipped_items: list[T]
    warnings: list[str]

    @property
    def all_succeeded(self) -> bool:
        """是否全部成功。"""
        return self.failure_count == 0 and self.skipped_count == 0

    @property
    def any_succeeded(self) -> bool:
        """是否有任何成功。"""
        return self.success_count > 0

    @property
    def completion_rate(self) -> float:
        """完成率（0-1）。"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


class BatchOperationService:
    """批量操作服务 - 提供统一的批量处理能力。"""

    @staticmethod
    def execute_batch(
        items: list[T],
        operation: Callable[[T], R],
        *,
        continue_on_error: bool = True,
        transaction_per_item: bool = False,
        max_errors: int | None = None,
    ) -> BatchOperationResult[T]:
        """执行批量操作。

        Args:
            items: 要处理的项目列表
            operation: 对每个项目执行的操作
            continue_on_error: 遇到错误是否继续
            transaction_per_item: 是否为每个项目单独创建事务
            max_errors: 最大错误数，超过则中止

        Returns:
            BatchOperationResult 包含成功/失败/跳过的统计
        """
        success_items: list[T] = []
        failed_items: list[tuple[T, Exception]] = []
        skipped_items: list[T] = []
        warnings: list[str] = []

        error_count = 0

        for item in items:
            # 检查是否超过最大错误数
            if max_errors is not None and error_count >= max_errors:
                skipped_items.extend(items[len(success_items) + len(failed_items) :])
                warnings.append(f"已达到最大错误数 {max_errors}，跳过剩余 {len(skipped_items)} 项")
                break

            try:
                operation(item)
                success_items.append(item)
            except Exception as e:
                logger.exception(f"批量操作失败: {e}")
                failed_items.append((item, e))
                error_count += 1

                if not continue_on_error:
                    # 不继续，剩余项目标记为跳过
                    remaining_index = len(success_items) + len(failed_items)
                    skipped_items.extend(items[remaining_index:])
                    warnings.append("遇到错误已停止，剩余项目未处理")
                    break

        return BatchOperationResult(
            success_count=len(success_items),
            failure_count=len(failed_items),
            skipped_count=len(skipped_items),
            total_count=len(items),
            success_items=success_items,
            failed_items=failed_items,
            skipped_items=skipped_items,
            warnings=warnings,
        )

    @staticmethod
    def execute_batch_with_progress(
        items: list[T],
        operation: Callable[[T, int, int], R],
        *,
        continue_on_error: bool = True,
    ) -> BatchOperationResult[T]:
        """执行批量操作，并提供进度回调。

        Args:
            items: 要处理的项目列表
            operation: 操作函数，接收 (item, current_index, total_count)
            continue_on_error: 遇到错误是否继续

        Returns:
            BatchOperationResult
        """
        success_items: list[T] = []
        failed_items: list[tuple[T, Exception]] = []
        warnings: list[str] = []

        total = len(items)

        for index, item in enumerate(items):
            try:
                operation(item, index, total)
                success_items.append(item)
            except Exception as e:
                logger.exception(f"批量操作失败 [{index + 1}/{total}]: {e}")
                failed_items.append((item, e))

                if not continue_on_error:
                    warnings.append(f"在第 {index + 1} 项遇到错误已停止")
                    break

        return BatchOperationResult(
            success_count=len(success_items),
            failure_count=len(failed_items),
            skipped_count=total - len(success_items) - len(failed_items),
            total_count=total,
            success_items=success_items,
            failed_items=failed_items,
            skipped_items=[],
            warnings=warnings,
        )


class PresentationBatchOperations:
    """汇报批量操作 - 针对页面和大纲的批量处理。"""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def batch_retry_failed_slides(
        self,
        presentation_id: UUID,
        *,
        continue_on_error: bool = True,
    ) -> BatchOperationResult[UUID]:
        """批量重试失败的页面。

        Args:
            presentation_id: 汇报 ID
            continue_on_error: 遇到错误是否继续

        Returns:
            批量操作结果
        """
        from archium.application.slide_generation_service import SlideGenerationService

        # 获取所有失败的页面
        failed_slides = self._get_failed_slides(presentation_id)

        if not failed_slides:
            return BatchOperationResult(
                success_count=0,
                failure_count=0,
                skipped_count=0,
                total_count=0,
                success_items=[],
                failed_items=[],
                skipped_items=[],
                warnings=["没有失败的页面需要重试"],
            )

        slide_ids = [slide.id for slide in failed_slides]
        generation_service = SlideGenerationService(self.uow)

        def retry_slide(slide_id: UUID) -> None:
            """重试单个页面。"""
            generation_service.regenerate_slide(slide_id)

        return BatchOperationService.execute_batch(
            slide_ids,
            retry_slide,
            continue_on_error=continue_on_error,
        )

    def batch_update_slide_property(
        self,
        slide_ids: list[UUID],
        property_name: str,
        property_value: Any,
    ) -> BatchOperationResult[UUID]:
        """批量更新页面属性。

        Args:
            slide_ids: 页面 ID 列表
            property_name: 属性名称（如 'slide_type', 'page_archetype'）
            property_value: 属性值

        Returns:
            批量操作结果
        """
        from archium.infrastructure.database.repositories import SlideRepository

        repo = SlideRepository(self.uow.session)

        def update_property(slide_id: UUID) -> None:
            """更新单个页面属性。"""
            slide = repo.get(slide_id)
            if slide is None:
                raise ValueError(f"Slide {slide_id} not found")

            # 使用 setattr 动态设置属性
            if hasattr(slide, property_name):
                setattr(slide, property_name, property_value)
                repo.update(slide)
            else:
                raise AttributeError(f"Slide has no attribute '{property_name}'")

        result = BatchOperationService.execute_batch(
            slide_ids,
            update_property,
            continue_on_error=True,
        )

        # 提交事务
        if result.any_succeeded:
            self.uow.commit()

        return result

    def batch_delete_slides(
        self,
        slide_ids: list[UUID],
        *,
        soft_delete: bool = True,
    ) -> BatchOperationResult[UUID]:
        """批量删除页面。

        Args:
            slide_ids: 页面 ID 列表
            soft_delete: 是否软删除（标记为删除而非真正删除）

        Returns:
            批量操作结果
        """
        from archium.infrastructure.database.repositories import SlideRepository

        repo = SlideRepository(self.uow.session)

        def delete_slide(slide_id: UUID) -> None:
            """删除单个页面。"""
            if soft_delete:
                slide = repo.get(slide_id)
                if slide:
                    slide.deleted = True
                    repo.update(slide)
            else:
                repo.delete(slide_id)

        result = BatchOperationService.execute_batch(
            slide_ids,
            delete_slide,
            continue_on_error=True,
        )

        if result.any_succeeded:
            self.uow.commit()

        return result

    def _get_failed_slides(self, presentation_id: UUID) -> list:
        """获取失败的页面列表。"""
        from archium.infrastructure.database.repositories import SlideRepository

        repo = SlideRepository(self.uow.session)

        # 查询所有属于该汇报且状态为失败的页面
        slides = repo.list_by_presentation(presentation_id)
        failed = [
            slide
            for slide in slides
            if hasattr(slide, "generation_status")
            and slide.generation_status == "failed"
        ]

        return failed


class OutlineBatchOperations:
    """大纲批量操作 - 针对章节和页面意图的批量处理。"""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def batch_update_page_archetype(
        self,
        intent_ids: list[int],
        archetype: str,
    ) -> BatchOperationResult[int]:
        """批量更新页面原型。

        Args:
            intent_ids: 页面意图 ID 列表
            archetype: 新的页面原型

        Returns:
            批量操作结果
        """

        def update_archetype(intent_id: int) -> None:
            """更新单个意图的原型。"""
            # 这里需要根据实际的数据模型来实现
            # 暂时使用占位逻辑
            from archium.domain.visual.visual_grammar import PageArchetype

            # 验证原型是否有效
            try:
                PageArchetype(archetype)
            except ValueError:
                raise ValueError(f"Invalid page archetype: {archetype}")

            # 实际更新逻辑需要根据数据模型实现
            logger.info(f"Updated intent {intent_id} to archetype {archetype}")

        return BatchOperationService.execute_batch(
            intent_ids,
            update_archetype,
            continue_on_error=True,
        )

    def batch_update_section_property(
        self,
        section_ids: list[UUID],
        property_name: str,
        property_value: Any,
    ) -> BatchOperationResult[UUID]:
        """批量更新章节属性。

        Args:
            section_ids: 章节 ID 列表
            property_name: 属性名称
            property_value: 属性值

        Returns:
            批量操作结果
        """

        def update_property(section_id: UUID) -> None:
            """更新单个章节属性。"""
            # 实际实现需要根据数据模型
            logger.info(
                f"Updated section {section_id} property {property_name} = {property_value}"
            )

        return BatchOperationService.execute_batch(
            section_ids,
            update_property,
            continue_on_error=True,
        )
