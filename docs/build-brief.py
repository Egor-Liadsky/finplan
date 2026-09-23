#!/usr/bin/env python3
"""Сборка `docs/architecture-brief.md` из `docs/architecture.md`.

Выжимка нужна исполнителям-субагентам: полный документ — несколько тысяч
строк, и каждый загруженный в контекст кусок оплачивается заново при каждом
следующем обращении к модели. Выжимка даёт карту документа с номерами строк и дословные
тексты тех правил, которые нужны в любой задаче.

Принцип: **ничего не пересказывается**. Карта строится по заголовкам
автоматически, правила копируются из документа посимвольно. Поэтому выжимка
не может разойтись с источником по смыслу — она может только устареть, и это
ловит `make lint`, который пересобирает файл и сравнивает с лежащим в
репозитории.

Запуск:
    python3 docs/build-brief.py            # пересобрать файл
    python3 docs/build-brief.py --check    # проверить, что файл совпадает
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOC = Path("docs/architecture.md")
BRIEF = Path("docs/architecture-brief.md")

# Разделы, копируемые в выжимку целиком и дословно. Список меняется здесь, а
# не правкой готового файла: правка готового файла затирается пересборкой.
VERBATIM = ["2.2", "3.1", "4.1", "11.1", "11.4", "12.1"]

# Дерево каталогов раздела 2.1 в выжимку попадает обрезанным по глубине:
# нужен слой, а не каждый файл внутри слоя.
TREE_SECTION = "2.1"
TREE_DEPTH = 2

HEAD_RE = re.compile(r"^(#{2,3}) (.+)$")
NUM_RE = re.compile(r"^(\d+(?:\.\d+)?)[.]? (.+)$")


def headings(lines: list[str]) -> list[tuple[int, int, str, str]]:
    """Заголовки документа: (номер строки, уровень, номер раздела, название)."""
    out = []
    for i, line in enumerate(lines, 1):
        m = HEAD_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        text = m.group(2).strip()
        num = NUM_RE.match(text)
        out.append((i, level, num.group(1) if num else "", num.group(2) if num else text))
    return out


def section_span(heads, lines, number: str) -> tuple[int, int]:
    """Границы раздела по его номеру: строки [начало, конец)."""
    for k, (line_no, _level, num, _title) in enumerate(heads):
        if num == number:
            end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
            return line_no, end
    raise SystemExit(f"раздел {number} в {DOC} не найден")


def section_text(heads, lines, number: str) -> str:
    start, end = section_span(heads, lines, number)
    return "\n".join(lines[start - 1:end]).rstrip()


def tree_excerpt(heads, lines) -> str:
    """Дерево каталогов, обрезанное по глубине вложенности."""
    text = section_text(heads, lines, TREE_SECTION)
    body = text.split("```text", 1)[1].split("```", 1)[0].strip("\n")
    kept = []
    for row in body.split("\n"):
        prefix = row.split("├")[0].split("└")[0]
        depth = prefix.count("│") + (1 if ("├" in row or "└" in row) else 0)
        if depth <= TREE_DEPTH:
            kept.append(row)
    return "\n".join(kept)


def build() -> str:
    lines = DOC.read_text().split("\n")
    heads = headings(lines)
    tops = [h for h in heads if h[1] == 2 and h[2]]

    parts: list[str] = []
    parts.append("# Выжимка архитектуры finplan")
    parts.append("")
    parts.append(
        "Файл собирается командой `make brief` из `docs/architecture.md` и руками\n"
        "не правится: правка затирается пересборкой, а `make lint` падает, если\n"
        "файл разошёлся с документом. Источник истины — сам документ; здесь лежат\n"
        "его карта и дословные копии правил, нужных в любой задаче. Всё, чего тут\n"
        "нет, читается из `docs/architecture.md` по номерам строк из карты."
    )
    parts.append("")
    parts.append("## Карта документа")
    parts.append("")
    parts.append("Номера строк указаны для текущей версии документа и обновляются пересборкой.")
    parts.append("")
    for k, (line_no, _level, num, title) in enumerate(tops):
        nxt = tops[k + 1][0] - 1 if k + 1 < len(tops) else len(lines)
        subs = [h for h in heads if h[1] == 3 and h[2].startswith(num + ".")
                and line_no < h[0] <= nxt]
        head = f"- **{num}. {title}** — строки {line_no}–{nxt}"
        if subs:
            inner = "; ".join(
                f"{s[2]} {s[3]} {s[0]}–"
                f"{(subs[i + 1][0] - 1) if i + 1 < len(subs) else nxt}"
                for i, s in enumerate(subs)
            )
            head += f"\n  - {inner}"
        parts.append(head)
    parts.append("")
    parts.append("## Дерево каталогов, два уровня")
    parts.append("")
    start, end = section_span(heads, lines, TREE_SECTION)
    parts.append(f"Полное дерево — раздел {TREE_SECTION}, строки {start}–{end}.")
    parts.append("")
    parts.append("```text")
    parts.append(tree_excerpt(heads, lines))
    parts.append("```")
    parts.append("")
    parts.append("## Правила, скопированные дословно")
    parts.append("")
    parts.append(
        "Ниже — текст разделов "
        + ", ".join(VERBATIM)
        + " без изменений. Расхождение с документом невозможно: блоки копируются "
        "при сборке."
    )
    for number in VERBATIM:
        start, end = section_span(heads, lines, number)
        parts.append("")
        parts.append(f"<!-- {DOC}, раздел {number}, строки {start}–{end} -->")
        parts.append("")
        parts.append(section_text(heads, lines, number))
    parts.append("")
    return "\n".join(parts) + "\n"


def main() -> int:
    text = build()
    if "--check" in sys.argv:
        if not BRIEF.exists():
            print(f"{BRIEF} отсутствует: запустите make brief")
            return 1
        if BRIEF.read_text() != text:
            print(f"{BRIEF} разошёлся с {DOC}: запустите make brief")
            return 1
        print(f"{BRIEF} соответствует {DOC}")
        return 0
    BRIEF.write_text(text)
    print(f"{BRIEF}: {len(text)} символов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
