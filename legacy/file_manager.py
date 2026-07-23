import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from archium.infrastructure.llm import LLMRequest, get_llm_provider
from archium.infrastructure.llm.schemas import FileClassificationPlan
from archium.prompts.identity import ARCHIUM_IDENTITY

CLASSIFY_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：以知识管理的严谨标准，根据提供的文件列表，为每个文件指定合适的目标文件夹路径。
你擅长从文件名与后缀推断建筑项目中的文件类型（如图纸、报告、模型、合同等），并给出清晰、可执行的归档方案。

分类原则：
1. 按文件类型与用途归类（如 CAD 图纸、报告文档、图片、表格、PDF、压缩包等）。
2. 目标路径使用绝对路径风格，例如 `D:/Projects/Drawings` 或 `C:/Users/Name/Documents/Reports`。
3. 同一类文件归入同一文件夹；若后缀含义明确，优先按后缀分类。
4. 无法判断时，归入 `Misc` 或 `未分类` 子目录。
5. 只返回目标文件夹路径，不包含文件名本身。

输出格式（必须严格遵守）：
- 仅输出一个 JSON 对象，不要 Markdown 代码块，不要任何解释文字。
- 键：文件名（与输入完全一致，含扩展名）。
- 值：目标文件夹的绝对路径字符串。
- 示例：
{"draft_v2.dwg": "D:/Projects/Drawings", "report.docx": "D:/Projects/Reports", "photo.jpg": "D:/Projects/Images"}
"""


@dataclass(frozen=True)
class FileInfo:
    name: str
    suffix: str
    path: Path


@dataclass(frozen=True)
class MoveResult:
    source: Path
    destination: Path
    success: bool
    message: str


def _is_hidden(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            # st_file_attributes is Windows-only; missing on POSIX stubs (mypy).
            attrs = getattr(path.stat(), "st_file_attributes", None)
            if attrs is None:
                return False
            return bool(attrs & stat.FILE_ATTRIBUTE_HIDDEN)
        except OSError:
            pass
    return False


def classify_files_with_ai(file_list: list[FileInfo]) -> dict[str, str]:
    """将文件名发送给 LLM，返回 {文件名: 目标文件夹} 的分类方案。"""
    if not file_list:
        raise ValueError("file_list 不能为空")

    expected_names = {item.name for item in file_list}
    lines = [f"- {item.name}（后缀：{item.suffix or '无'}）" for item in file_list]
    user_prompt = "请为以下文件制定分类方案：\n" + "\n".join(lines)

    provider = get_llm_provider()
    plan = provider.generate_structured(
        LLMRequest(
            system_prompt=CLASSIFY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
        ),
        FileClassificationPlan,
    )
    return plan.validate_expected_files(expected_names)


def _resolve_source_path(key: str, source_folder: Path | None) -> Path:
    candidate = Path(key)
    if candidate.is_absolute():
        return candidate.resolve()

    if source_folder is None:
        raise ValueError(
            f"键 {key!r} 为相对文件名，请通过 source_folder 指定源目录，"
            "或在键中使用文件的绝对路径"
        )
    return (source_folder / key).resolve()


def _safe_move_file(source: Path, dest_dir: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"源文件不存在或不是普通文件：{source}")

    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    destination = dest_dir / source.name
    if destination.exists():
        raise FileExistsError(f"目标已存在，跳过移动以避免覆盖：{destination}")

    if source.resolve() == destination.resolve():
        raise ValueError(f"源与目标相同，无需移动：{source}")

    if destination.is_dir():
        raise IsADirectoryError(f"目标路径是目录，无法覆盖：{destination}")

    temp_destination = dest_dir / f".{source.name}.moving"
    if temp_destination.exists():
        raise FileExistsError(f"存在未完成的移动临时文件：{temp_destination}")

    try:
        shutil.copy2(source, temp_destination)
        if temp_destination.stat().st_size != source.stat().st_size:
            raise OSError("复制校验失败：文件大小不一致")

        temp_destination.replace(destination)
        source.unlink()
    except Exception:
        temp_destination.unlink(missing_ok=True)
        raise

    return destination


def scan_folder(folder_path: str | Path) -> list[FileInfo]:
    """扫描指定文件夹，返回所有非隐藏文件的名称与后缀。"""
    root = Path(folder_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"文件夹不存在：{root}")
    if not root.is_dir():
        raise NotADirectoryError(f"路径不是文件夹：{root}")

    files: list[FileInfo] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file():
            continue
        if _is_hidden(entry):
            continue
        files.append(
            FileInfo(
                name=entry.name,
                suffix=entry.suffix.lower(),
                path=entry,
            )
        )
    return files


def move_files(
    classification_map: dict[str, str],
    *,
    source_folder: str | Path | None = None,
) -> list[MoveResult]:
    """根据分类方案安全移动文件；目标文件夹不存在时自动创建。"""
    if not classification_map:
        raise ValueError("classification_map 不能为空")

    resolved_source = Path(source_folder).expanduser().resolve() if source_folder else None
    results: list[MoveResult] = []

    for key, dest_folder in classification_map.items():
        try:
            source = _resolve_source_path(key, resolved_source)
            destination = _safe_move_file(source, Path(dest_folder))
            results.append(
                MoveResult(
                    source=source,
                    destination=destination,
                    success=True,
                    message="移动成功",
                )
            )
        except Exception as exc:
            source_path = Path(key)
            if resolved_source and not source_path.is_absolute():
                source_path = resolved_source / key
            results.append(
                MoveResult(
                    source=source_path,
                    destination=Path(dest_folder),
                    success=False,
                    message=str(exc),
                )
            )

    return results
