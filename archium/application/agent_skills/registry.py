"""Load ArchiumSkillDefinition rows from archium-agent-skills/."""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from archium.application.agent_skills.catalog import SKILL_CATALOG
from archium.domain.agent_skill import ArchiumSkillDefinition

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def default_skills_root() -> Path:
    """Repo-root ``archium-agent-skills`` (shared by Cursor and runtime)."""
    return Path(__file__).resolve().parents[3] / "archium-agent-skills"


class SkillRegistry:
    """Filesystem-backed skill registry with checksummed prompt bodies."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or default_skills_root()
        self._by_id: dict[str, ArchiumSkillDefinition] = {}
        self.reload()

    @property
    def root(self) -> Path:
        return self._root

    def reload(self) -> None:
        self._by_id = {}
        if not self._root.is_dir():
            return
        for skill_dir in sorted(path for path in self._root.iterdir() if path.is_dir()):
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.is_file():
                continue
            definition = self._load_skill(skill_path)
            if definition is not None:
                self._by_id[definition.id] = definition

    def get(self, skill_id: str) -> ArchiumSkillDefinition | None:
        return self._by_id.get(skill_id)

    def list_all(self) -> list[ArchiumSkillDefinition]:
        return [self._by_id[key] for key in sorted(self._by_id)]

    def require(self, skill_id: str) -> ArchiumSkillDefinition:
        skill = self.get(skill_id)
        if skill is None:
            raise KeyError(f"unknown Archium skill: {skill_id}")
        return skill

    def _load_skill(self, skill_path: Path) -> ArchiumSkillDefinition | None:
        raw = skill_path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        meta, body = _split_frontmatter(raw)
        skill_id = str(meta.get("name") or skill_path.parent.name).strip()
        if not skill_id:
            return None
        catalog = SKILL_CATALOG.get(skill_id, {})
        version = str(meta.get("version") or catalog.get("version") or "1.0.0")
        title = str(
            meta.get("title")
            or catalog.get("title")
            or skill_id.replace("-", " ").title()
        )
        description = str(meta.get("description") or "").strip()
        prompt_uri = f"archium-agent-skills/{skill_path.parent.name}/SKILL.md"
        return ArchiumSkillDefinition(
            id=skill_id,
            version=version,
            title=title,
            description=description,
            applicable_stages=_string_list(meta.get("applicable_stages"))
            or _string_list(catalog.get("applicable_stages")),
            applicable_slide_types=_string_list(meta.get("applicable_slide_types"))
            or _string_list(catalog.get("applicable_slide_types"))
            or ["*"],
            applicable_project_types=_string_list(meta.get("applicable_project_types"))
            or _string_list(catalog.get("applicable_project_types"))
            or ["*"],
            applicable_audiences=_string_list(meta.get("applicable_audiences"))
            or _string_list(catalog.get("applicable_audiences"))
            or ["*"],
            required_rules=_string_list(meta.get("required_rules"))
            or _string_list(catalog.get("required_rules")),
            prompt_uri=prompt_uri,
            checksum=checksum,
            body=body.strip(),
        )


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    return _parse_simple_yaml(match.group(1)), match.group(2)


def _parse_simple_yaml(block: str) -> dict[str, object]:
    """Minimal frontmatter reader (scalars + inline/block string lists)."""
    result: dict[str, object] = {}
    lines = block.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if ":" not in line:
            index += 1
            continue
        key, _, raw_value = line.partition(":")
        key = key.strip()
        value = raw_value.strip()
        if value in {">", ">-", "|", "|-"}:
            folded: list[str] = []
            index += 1
            while index < len(lines) and (
                lines[index].startswith("  ") or lines[index].startswith("\t")
            ):
                folded.append(lines[index].strip())
                index += 1
            result[key] = " ".join(folded).strip()
            continue
        if value == "":
            items: list[str] = []
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith("- "):
                items.append(lines[index].lstrip()[2:].strip().strip("\"'"))
                index += 1
            result[key] = items
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            result[key] = [
                part.strip().strip("\"'")
                for part in inner.split(",")
                if part.strip()
            ]
        else:
            result[key] = value.strip("\"'")
        index += 1
    return result


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
