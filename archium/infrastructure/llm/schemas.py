"""Pydantic schemas for legacy LLM structured outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel, field_validator


class RouterStep(BaseModel):
    tool: Literal["file_manager", "ppt_generator", "discord_watcher"]
    params: dict[str, Any] = Field(default_factory=dict)


class RouterPlan(BaseModel):
    summary: str
    steps: list[RouterStep] = Field(default_factory=list)


class FileClassificationPlan(RootModel[dict[str, str]]):
    """Maps filenames to destination folder paths."""

    root: dict[str, str]

    def validate_expected_files(self, expected_names: set[str]) -> dict[str, str]:
        result = {name.strip(): dest.strip() for name, dest in self.root.items()}
        missing = expected_names - set(result)
        if missing:
            raise ValueError(f"分类结果缺少以下文件：{', '.join(sorted(missing))}")
        extra = set(result) - expected_names
        if extra:
            raise ValueError(f"分类结果包含未知文件：{', '.join(sorted(extra))}")
        for name, dest in result.items():
            if not name or not dest:
                raise ValueError(f"分类项不能为空：{name!r} -> {dest!r}")
        return result


class DiscordClassification(BaseModel):
    important: bool
    summary: str = Field(max_length=200)

    @field_validator("summary")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        return value.strip()
