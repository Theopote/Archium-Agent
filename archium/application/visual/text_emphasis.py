"""Deterministic inline emphasis for body / lead / bullet text.

Splits plain layout text into ``TextRun`` spans so PPTX can render mixed
weight and accent color without requiring Studio manual edits.
"""

from __future__ import annotations

import re

from archium.domain.visual.render_scene import TextRun

# Leading markers: "01." "1." "·" "→" "（1）" "(1)"
_LINE_PREFIX = re.compile(
    r"^(\s*(?:·|→|•|-|"
    r"\d{1,2}\s*[.、．]|"
    r"[（(]\d{1,2}[）)]|"
    r"[①②③④⑤⑥⑦⑧⑨⑩])\s*)"
)
# Measurable figures worth accenting in architectural decks.
_METRIC = re.compile(
    r"(?<![\w.])("
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|"
    r"\d+(?:\.\d+)?"
    r")"
    r"(\s*(?:%|％|㎡|m²|km|公顷|万㎡|万人|亿|万吨|万|亿元|年|层)?)?"
)
# Editorial keywords — bold + accent once per line (architectural Chinese).
_KEYWORD = re.compile(
    r"(核心|重点|关键|策略|原则|优先|必须|强制|禁止|韧性|蓝绿|"
    r"客货分离|港产城|示范区|总体城市设计|"
    r"Core|Strategy|Priority|Must|Key)"
)
# Lead statements: emphasize the clause before the first Chinese pause.
_LEAD_CLAUSE = re.compile(r"^(.{4,28}?)([，：、；]|——)")


def build_emphasis_text_runs(
    text: str,
    *,
    base_color: str,
    accent_color: str,
    base_weight: int = 400,
    emphasize_weight: int = 700,
    base_size: float | None = None,
    emphasize_size: float | None = None,
    emphasize_lead_clause: bool = False,
    keywords: bool = True,
) -> list[TextRun]:
    """Return runs with bold/accent on prefixes, metrics, and key phrases.

    Empty input yields an empty list (caller should keep flat TextNode text).
    """
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    runs: list[TextRun] = []
    for line_index, line in enumerate(lines):
        suffix = "\n" if line_index < len(lines) - 1 else ""
        if not line:
            runs.append(TextRun(text=suffix or "\n"))
            continue
        cursor = 0
        match = _LINE_PREFIX.match(line)
        if match:
            prefix = match.group(1)
            runs.append(
                TextRun(
                    text=prefix,
                    font_weight=emphasize_weight,
                    color=accent_color,
                    font_size=emphasize_size,
                )
            )
            cursor = match.end()
        remainder = line[cursor:]
        if emphasize_lead_clause and line_index == 0 and cursor == 0:
            clause = _LEAD_CLAUSE.match(remainder)
            if clause:
                runs.append(
                    TextRun(
                        text=clause.group(1),
                        font_weight=emphasize_weight,
                        color=accent_color,
                        font_size=emphasize_size,
                    )
                )
                runs.append(
                    TextRun(
                        text=clause.group(2),
                        font_weight=base_weight,
                        color=base_color,
                        font_size=base_size,
                    )
                )
                remainder = remainder[clause.end() :]
        runs.extend(
            _phrase_runs(
                remainder,
                base_color=base_color,
                accent_color=accent_color,
                base_weight=base_weight,
                emphasize_weight=emphasize_weight,
                base_size=base_size,
                emphasize_size=emphasize_size,
                keywords=keywords,
            )
        )
        if suffix:
            if runs:
                last = runs[-1]
                runs[-1] = last.model_copy(update={"text": last.text + suffix})
            else:
                runs.append(TextRun(text=suffix))
    return [run for run in runs if run.text]


def _phrase_runs(
    text: str,
    *,
    base_color: str,
    accent_color: str,
    base_weight: int,
    emphasize_weight: int,
    base_size: float | None,
    emphasize_size: float | None,
    keywords: bool,
) -> list[TextRun]:
    if not text:
        return []
    # Interleave keyword and metric matches by position.
    events: list[tuple[int, int, str]] = []
    if keywords:
        for match in _KEYWORD.finditer(text):
            events.append((match.start(), match.end(), "keyword"))
    for match in _METRIC.finditer(text):
        events.append((match.start(), match.end(), "metric"))
    events.sort(key=lambda item: (item[0], item[1]))

    runs: list[TextRun] = []
    cursor = 0
    for start, end, _kind in events:
        if start < cursor:
            continue
        if start > cursor:
            runs.append(
                TextRun(
                    text=text[cursor:start],
                    font_weight=base_weight,
                    color=base_color,
                    font_size=base_size,
                )
            )
        runs.append(
            TextRun(
                text=text[start:end],
                font_weight=emphasize_weight,
                color=accent_color,
                font_size=emphasize_size,
            )
        )
        cursor = end
    if cursor < len(text):
        runs.append(
            TextRun(
                text=text[cursor:],
                font_weight=base_weight,
                color=base_color,
                font_size=base_size,
            )
        )
    if not runs:
        runs.append(
            TextRun(
                text=text,
                font_weight=base_weight,
                color=base_color,
                font_size=base_size,
            )
        )
    return runs
