"""MCP-сервер базы знаний норм ВК: слой 1 (YAML-правила) + слой 3 (поиск по norms/).

Инструменты: search_norms (BM25), get_clause (полный текст пункта), list_norm_docs,
list_rules / get_rule (проверенные машиночитаемые правила из rules/).
Запуск: `uv run python -m norms_mcp` (stdio), регистрация — .mcp.json в корне репо.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from norms_mcp.index import get_index
from norms_mcp.parser import DOC_META

mcp = FastMCP("norms")

SNIPPET_CHARS = 500
RULES_DIR = Path(__file__).resolve().parents[1] / "rules"


@mcp.tool()
def search_norms(query: str, doc: str = "", top_n: int = 8) -> str:
    """Полнотекстовый поиск по нормам ВК (СП 30, 73, 31, 32, СП 10, ГОСТ 21.601, ПП 87).

    query — запрос на русском (термины и числа из нормы);
    doc — необязательный фильтр по документу (sp30, sp73, sp31, sp32, sp10, gost21601, pp87);
    top_n — сколько результатов вернуть.
    Возвращает список фрагментов с идентификатором пункта; полный текст пункта
    бери инструментом get_clause. В ответах пользователю всегда цитируй документ и пункт.
    """
    if doc and doc not in DOC_META:
        return f"Неизвестный документ «{doc}». Доступны: {', '.join(DOC_META)}"
    results = get_index().search(query, doc=doc or None, top_n=top_n)
    if not results:
        return "Ничего не найдено — переформулируй запрос (синонимы, номер пункта, число)."
    out = []
    for i, (chunk, score) in enumerate(results, 1):
        snippet = chunk.text[:SNIPPET_CHARS].replace("\n", " ")
        section = f" | раздел: {chunk.section}" if chunk.section else ""
        out.append(
            f"{i}. [{chunk.doc} :: {chunk.clause}]{section} (score {score:.1f})\n   {snippet}"
        )
    return "\n\n".join(out)


@mcp.tool()
def get_clause(doc: str, clause: str) -> str:
    """Полный текст пункта/таблицы/приложения документа.

    doc — id документа (см. list_norm_docs); clause — id пункта как в результатах
    search_norms: «5.3», «18.36», «табл. К.5», «прил. И», для ПП 87 — «17».
    """
    if doc not in DOC_META:
        return f"Неизвестный документ «{doc}». Доступны: {', '.join(DOC_META)}"
    chunks = get_index().get_clause(doc, clause)
    if not chunks:
        near = [c.clause for c in get_index().chunks
                if c.doc == doc and clause.strip().lower() in c.clause.lower()][:10]
        hint = f" Похожие: {', '.join(near)}" if near else ""
        return f"Пункт «{clause}» не найден в {doc}.{hint}"
    title = DOC_META[doc][1]
    body = "\n\n".join(c.text for c in chunks)
    return f"{title} — {clause}\n\n{body}"


@mcp.tool()
def list_rules() -> str:
    """Перечень машиночитаемых правил слоя 1 — оцифрованные таблицы и формулы СП.

    Значения в них перенесены из PDF со сверкой (в отличие от полнотекстового слоя,
    где конвертация могла испортить формулы и знаки сравнения). Для вопросов о числах
    и формулах сначала смотри сюда, потом в полнотекстовый поиск.
    """
    lines = []
    for path in sorted(RULES_DIR.glob("*/*.yaml")):
        head = path.read_text(encoding="utf-8").splitlines()
        source = next((ln.split(":", 1)[1].strip().strip('"') for ln in head
                       if ln.startswith("source:")), "")
        lines.append(f"{path.parent.name}/{path.stem} — {source}")
    return "\n".join(lines)


@mcp.tool()
def get_rule(doc: str, name: str) -> str:
    """Полный YAML правила слоя 1 (точные формулы и значения, сверенные с PDF).

    doc — каталог правила (sp30, sp73), name — имя файла без .yaml,
    как в выдаче list_rules (например: sp30, formuly_raskhodov).
    """
    path = RULES_DIR / doc / f"{name}.yaml"
    if not path.is_file():
        known = [f"{p.parent.name}/{p.stem}" for p in sorted(RULES_DIR.glob("*/*.yaml"))]
        return f"Правила {doc}/{name} нет. Есть: {', '.join(known)}"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def list_norm_docs() -> str:
    """Перечень документов базы норм: id, название, число чанков-пунктов."""
    idx = get_index()
    counts: dict[str, int] = {}
    for c in idx.chunks:
        counts[c.doc] = counts.get(c.doc, 0) + 1
    lines = [f"{doc_id}: {meta[1]} — {counts.get(doc_id, 0)} чанков"
             for doc_id, meta in DOC_META.items()]
    return "\n".join(lines)
