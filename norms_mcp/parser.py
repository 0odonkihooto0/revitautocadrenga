"""Разбор norms/*.md на чанки-пункты для поискового индекса.

Форматы исходников различаются (конвертация BazaSnipMD и pymupdf-конвертация сессии
2026-07-18), поэтому чанк начинается на любом из маркеров: заголовок «## …», номер
пункта в начале строки (5.3, 6.3.4, «17.» у ПП 87), «Таблица X», «Приложение X».
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

NORMS_DIR = Path(__file__).resolve().parents[1] / "norms"

# id → (файл, полное имя документа)
DOC_META = {
    "sp30": ("sp30-13330-2020.md", "СП 30.13330.2020 «Внутренний водопровод и канализация зданий»"),
    "sp73": ("sp73-13330-2016.md", "СП 73.13330.2016 «Внутренние санитарно-технические системы зданий»"),
    "sp31": ("sp31-13330-2021.md", "СП 31.13330.2021 «Водоснабжение. Наружные сети и сооружения»"),
    "sp32": ("sp32-13330-2018.md", "СП 32.13330.2018 «Канализация. Наружные сети и сооружения» (с изм. 1, 2)"),
    "sp10": ("sp10-13130-2020.md", "СП 10.13130.2020 «Внутренний противопожарный водопровод» (с изм. 1)"),
    "gost21601": ("gost-21-601-2011.md", "ГОСТ 21.601-2011 «СПДС. Рабочая документация внутренних систем водоснабжения и канализации»"),
    "pp87": ("pp-87.md", "ПП РФ от 16.02.2008 № 87 «О составе разделов проектной документации» (ред. 21.10.2025)"),
}

MAX_CHUNK_CHARS = 6000

_RE_TABLE = re.compile(r"^#*\s*Т\s*а\s*б\s*л\s*и\s*ц\s*а\s+([А-ЯёЁA-Z]?\.?\s?\d+(?:\.\d+)*)", re.I)
_RE_APPENDIX = re.compile(r"^#{0,2}\s*(Приложение\s+[А-ЯЁ])\b")
_RE_CLAUSE = re.compile(r"^(?:-\s+)?(\d+(?:\.\d+)+)\s+\S")
_RE_CLAUSE_HEAD = re.compile(r"^##\s+(\d+(?:\.\d+)*)\s+(\S.*)")
_RE_PP_ITEM = re.compile(r"^(\d+)(?:\.|\(\d+\)\.)\s+[А-ЯЁ«\"]")
_RE_SECTION_CAPS = re.compile(r"^(\d+)\s+[А-ЯЁ][А-ЯЁ ,\-]{4,}$")


@dataclass
class Chunk:
    doc: str
    clause: str
    section: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


def _boundary(line: str) -> tuple[str, str] | None:
    """Возвращает (clause_id, заголовок-контекст) если строка открывает новый чанк."""
    m = _RE_TABLE.match(line)
    if m:
        num = re.sub(r"\s+", "", m.group(1))
        return f"табл. {num}", line.lstrip("# ").strip()
    m = _RE_APPENDIX.match(line)
    if m:
        return m.group(1).replace("Приложение", "прил."), line.lstrip("# ").strip()
    m = _RE_CLAUSE_HEAD.match(line)
    if m:
        return m.group(1), m.group(2).strip()
    m = _RE_CLAUSE.match(line)
    if m:
        return m.group(1), ""
    m = _RE_SECTION_CAPS.match(line)
    if m:
        return m.group(1), line.strip()
    m = _RE_PP_ITEM.match(line)
    if m:
        return m.group(1), ""
    return None


def parse_doc(doc_id: str) -> list[Chunk]:
    """Разбирает один документ norms/ на чанки."""
    fname, _title = DOC_META[doc_id]
    text = (NORMS_DIR / fname).read_text(encoding="utf-8")
    chunks: list[Chunk] = []
    current = Chunk(doc=doc_id, clause="preamble", section="")
    section = ""
    for line in text.splitlines():
        b = _boundary(line)
        if b is not None:
            if current.text:
                chunks.append(current)
            clause, head = b
            if head:
                section = head
            current = Chunk(doc=doc_id, clause=clause, section=section)
        elif len("\n".join(current.lines)) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = Chunk(
                doc=doc_id, clause=f"{current.clause} (продолжение)", section=current.section
            )
        current.lines.append(line)
    if current.text:
        chunks.append(current)
    return chunks


def parse_all() -> list[Chunk]:
    """Все документы norms/ (см. DOC_META) одним списком чанков."""
    out: list[Chunk] = []
    for doc_id in DOC_META:
        out.extend(parse_doc(doc_id))
    return out
