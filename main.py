"""
Archium Agent — Legacy v0.1 CLI (experimental)

This is NOT the v0.2 product entry point. Use ``archium`` or
``streamlit run app.py`` for the project workspace.

Natural-language router for v0.1 tools: file organization, quick Marp PPT,
Discord watcher. Requires ``pip install -e ".[legacy]"`` for Discord support.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archium.infrastructure.llm import LLMRequest, get_llm_provider
from archium.infrastructure.llm.schemas import RouterPlan, RouterStep
from archium.prompts.identity import ARCHIUM_IDENTITY
from file_manager import classify_files_with_ai, move_files, scan_folder
from ppt_generator import generate_presentation

ROUTER_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Archium 的任务路由器（Router），根据用户的自然语言指令，拆解为有序的工具调用计划。

可用工具（tool 字段必须为下列之一）：

1. file_manager — 扫描并 AI 分类整理本地文件夹
   必填 params：
   - folder_path (str)：要整理的文件夹绝对路径或 ~ 开头路径
     示例：C:/Users/xxx/Downloads 或 ~/Downloads

2. ppt_generator — 根据主题自动生成 Marp 幻灯片并导出
   必填 params：
   - topic (str)：演示文稿主题
   - output_path (str)：输出文件路径，必须以 .pptx 或 .pdf 结尾
     示例：output/weekly_report.pptx

3. discord_watcher — 启动 Discord 消息守卫 Bot（长期运行，阻塞进程）
   params：{} （无需参数，Token 从 .env 读取）

规则：
- 用户可能要求连续执行多个工具，按逻辑顺序排列 steps（例如先整理文件再做 PPT）。
- 从用户指令中推断缺失参数；Windows 用户 Downloads 通常为 ~/Downloads。
- PPT 未指定输出路径时，默认 output/presentation.pptx。
- 若用户只是闲聊或与上述工具无关，返回空 steps 并在 summary 中直接回复。
- 只输出 JSON，不要 Markdown 代码块。

输出格式：
{
  "summary": "一句话说明你对用户意图的理解",
  "steps": [
    {"tool": "file_manager", "params": {"folder_path": "~/Downloads"}},
    {"tool": "ppt_generator", "params": {"topic": "本周项目进度", "output_path": "output/weekly.pptx"}}
  ]
}
"""


def _expand_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


ConfirmFileMoves = Callable[[str, dict[str, str]], bool]


def _default_confirm_file_moves(folder: str, plan: dict[str, str]) -> bool:
    print()
    print("⚠️  文件移动会永久改变本地磁盘上的文件位置（不可通过本工具撤销）。")
    print(f"     源文件夹：`{folder}`")
    print(f"     待移动：**{len(plan)}** 个文件")
    for name, dest in plan.items():
        print(f"     - `{name}` → `{dest}`")
    print()
    if not sys.stdin.isatty():
        print("     当前为非交互环境，已自动取消文件移动。")
        return False
    try:
        answer = input("确认执行以上移动？(输入 yes 确认，其他任意键取消): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes", "是", "确认"}


def _route_instruction(instruction: str) -> RouterPlan:
    provider = get_llm_provider()
    return provider.generate_structured(
        LLMRequest(
            system_prompt=ROUTER_SYSTEM_PROMPT,
            user_prompt=instruction,
            temperature=0.2,
        ),
        RouterPlan,
    )


def _print_banner() -> None:
    print()
    print("=" * 52)
    print("  LEGACY — v0.1 CLI (not the v0.2 product entry)")
    print("  Use `archium` or `streamlit run app.py` for the workspace.")
    print("=" * 52)
    print("  🏛️  Archium Agent — 建筑师 AI 助手")
    print("  📂 文件整理  |  📊 PPT 生成  |  🤖 Discord 守卫")
    print("=" * 52)
    print()


def _print_step(label: str, message: str) -> None:
    print(f"\n{label}  {message}")


def _run_file_manager(
    params: dict[str, Any],
    *,
    confirm_moves: ConfirmFileMoves | None = None,
) -> StepResult:
    label = TOOL_LABELS["file_manager"]
    lines: list[str] = []
    file_paths: list[str] = []

    folder_path = params.get("folder_path")
    if not folder_path:
        raise ValueError("file_manager 缺少参数 folder_path")

    folder = _expand_path(str(folder_path))
    lines.append(f"扫描文件夹：`{folder}`")

    files = scan_folder(folder)
    if not files:
        lines.append("文件夹中没有可整理的文件，已跳过。")
        return StepResult("file_manager", label, True, lines)

    lines.append(f"发现 **{len(files)}** 个文件，正在请求 AI 分类…")
    for item in files:
        lines.append(f"- {item.name}")

    plan = classify_files_with_ai(files)
    lines.append("**分类方案：**")
    for name, dest in plan.items():
        lines.append(f"- `{name}` → `{dest}`")

    confirm = confirm_moves or _default_confirm_file_moves
    if not confirm(folder, plan):
        lines.append("已取消文件移动；本地文件未被修改。")
        return StepResult("file_manager", label, False, lines)

    lines.append("开始安全移动文件…")
    results = move_files(plan, source_folder=folder)

    ok = sum(1 for r in results if r.success)
    fail = len(results) - ok
    for r in results:
        icon = "✅" if r.success else "❌"
        lines.append(f"{icon} `{r.source.name}` — {r.message}")
        if r.success:
            file_paths.append(str(r.destination))

    lines.append(f"整理完成：成功 **{ok}**，失败 **{fail}**")
    return StepResult("file_manager", label, fail == 0, lines, file_paths)


def _run_ppt_generator(params: dict[str, Any]) -> StepResult:
    label = TOOL_LABELS["ppt_generator"]
    lines: list[str] = []

    topic = params.get("topic")
    output_path = params.get("output_path", "output/presentation.pptx")

    if not topic:
        raise ValueError("ppt_generator 缺少参数 topic")

    output_path = _expand_path(str(output_path))
    lines.append(f"主题：**{topic}**")
    lines.append(f"输出路径：`{output_path}`")

    result = generate_presentation(str(topic), output_path)
    lines.append(f"PPT 已生成：`{result}`")
    return StepResult("ppt_generator", label, True, lines, [str(result)])


def _run_discord_watcher(
    _params: dict[str, Any],
    *,
    discord_runner: DiscordRunner | None = None,
) -> StepResult:
    label = TOOL_LABELS["discord_watcher"]
    lines = ["正在启动 Discord 消息守卫…"]

    runner = discord_runner or _default_discord_runner
    runner()
    lines.append("Discord 守卫已在后台运行。")
    return StepResult("discord_watcher", label, True, lines)


def _default_discord_runner() -> None:
    import discord_watcher

    discord_watcher.run()


def _print_step_result_cli(result: StepResult) -> None:
    for line in result.lines:
        print(f"     {line}")


TOOL_RUNNERS = {
    "file_manager": _run_file_manager,
    "ppt_generator": _run_ppt_generator,
    "discord_watcher": _run_discord_watcher,
}

TOOL_LABELS = {
    "file_manager": "📂 文件管家",
    "ppt_generator": "📊 PPT 生成器",
    "discord_watcher": "🤖 Discord 守卫",
}


@dataclass
class StepResult:
    tool: str
    label: str
    success: bool
    lines: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)


@dataclass
class ExecutionReport:
    summary: str
    plan_labels: list[str]
    step_results: list[StepResult]
    success: bool
    error: str | None = None


DiscordRunner = Callable[[], None]


def execute_plan(
    steps: list[RouterStep],
    *,
    discord_runner: DiscordRunner | None = None,
    confirm_file_moves: ConfirmFileMoves | None = None,
) -> tuple[list[StepResult], bool]:
    if not steps:
        return [], True

    results: list[StepResult] = []
    total = len(steps)

    for index, step in enumerate(steps):
        tool = step.tool
        params = step.params
        label = TOOL_LABELS[tool]

        _print_step("▶️ ", f"步骤 {index + 1}/{total}：{label}")

        try:
            if tool == "file_manager":
                result = _run_file_manager(params, confirm_moves=confirm_file_moves)
            elif tool == "ppt_generator":
                result = _run_ppt_generator(params)
            else:
                result = _run_discord_watcher(params, discord_runner=discord_runner)
        except KeyboardInterrupt:
            _print_step("🛑", "用户中断当前任务。")
            raise
        except Exception as exc:
            _print_step("❌", f"步骤失败：{exc}")
            results.append(StepResult(tool, label, False, [str(exc)]))
            return results, False

        for line in result.lines:
            print(f"     {line}")
        results.append(result)

        if not result.success:
            return results, False

        if tool == "discord_watcher":
            return results, True

    return results, True


def _execute_plan(steps: list[RouterStep]) -> bool:
    _, success = execute_plan(steps)
    return success


def run_instruction(
    instruction: str,
    *,
    discord_runner: DiscordRunner | None = None,
    confirm_file_moves: ConfirmFileMoves | None = None,
) -> ExecutionReport:
    plan = _route_instruction(instruction)

    if not plan.steps:
        return ExecutionReport(plan.summary, [], [], True)

    plan_labels = [TOOL_LABELS.get(step.tool, step.tool) for step in plan.steps]
    step_results, success = execute_plan(
        plan.steps,
        discord_runner=discord_runner,
        confirm_file_moves=confirm_file_moves,
    )
    return ExecutionReport(plan.summary, plan_labels, step_results, success)


def _handle_instruction(instruction: str) -> None:
    _print_step("🧠", "正在理解您的指令…")

    try:
        report = run_instruction(instruction)
    except Exception as exc:
        _print_step("❌", f"路由失败：{exc}")
        return

    _print_step("💡", f"理解：{report.summary}")

    if not report.plan_labels:
        _print_step("💬", "未匹配到可执行工具，请在指令中说明具体任务。")
        return

    _print_step("📋", f"执行计划（共 {len(report.plan_labels)} 步）：")
    for index, label in enumerate(report.plan_labels, start=1):
        print(f"     {index}. {label}")

    print()
    _print_step("🚀", "开始执行…")

    for result in report.step_results:
        print()
        print("-" * 52)
        _print_step("▶️ ", result.label)
        for line in result.lines:
            print(f"     {line}")

    if report.success:
        _print_step("🎉", "全部任务已完成！")
    else:
        _print_step("⚠️ ", "任务链中断，请检查上方错误信息后重试。")


def main() -> None:
    _print_banner()

    while True:
        try:
            instruction = input("请输入您的指令 (输入 q 退出): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not instruction:
            continue

        if instruction.lower() in {"q", "quit", "exit", "退出"}:
            print("👋 再见！")
            break

        print()
        try:
            _handle_instruction(instruction)
        except KeyboardInterrupt:
            print("\n🛑 已取消当前指令。")
        except Exception as exc:
            _print_step("❌", f"发生意外错误：{exc}")

        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 再见！")
        sys.exit(0)
