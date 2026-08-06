"""PptxGen CLI failure messaging — file-lock guidance."""

from __future__ import annotations

from pathlib import Path

from archium.infrastructure.renderers.pptxgen_cli import _format_pptxgen_failure


def test_ebusy_asks_user_to_close_open_pptx() -> None:
    path = Path(r"C:\tmp\presentation.pptx")
    message = _format_pptxgen_failure(
        "EBUSY: resource busy or locked, open 'C:\\tmp\\presentation.pptx'",
        path,
    )
    assert "正被占用" in message
    assert "请先关闭" in message
    assert str(path) in message
    assert "导出 PPTX" in message


def test_generic_pptxgen_failure_keeps_detail() -> None:
    message = _format_pptxgen_failure("SyntaxError: unexpected token", Path("out.pptx"))
    assert message.startswith("PptxGenJS 导出失败：")
    assert "SyntaxError" in message
