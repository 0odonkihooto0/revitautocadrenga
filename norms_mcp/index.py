"""BM25-индекс по чанкам norms/ с русским стеммингом (snowball)."""

import re
from functools import lru_cache

import snowballstemmer
from rank_bm25 import BM25Okapi

from norms_mcp.parser import Chunk, parse_all

_stemmer = snowballstemmer.stemmer("russian")
_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Токены: кириллица/латиница/цифры, нижний регистр, русский стемминг."""
    words = _TOKEN_RE.findall(text.lower().replace("ё", "е"))
    return _stemmer.stemWords(words)


class NormsIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._bm25 = BM25Okapi([tokenize(f"{c.clause} {c.section} {c.text}") for c in chunks])

    def search(self, query: str, doc: str | None = None, top_n: int = 8) -> list[tuple[Chunk, float]]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda p: p[1], reverse=True)
        if doc:
            ranked = [(c, s) for c, s in ranked if c.doc == doc]
        return [(c, s) for c, s in ranked[:top_n] if s > 0]

    def get_clause(self, doc: str, clause: str) -> list[Chunk]:
        """Чанки документа с точным clause id (плюс его «(продолжение)»)."""
        want = clause.strip().lower()
        exact = [
            c for c in self.chunks
            if c.doc == doc and (c.clause.lower() == want or c.clause.lower().startswith(want + " ("))
        ]
        return exact


@lru_cache(maxsize=1)
def get_index() -> NormsIndex:
    return NormsIndex(parse_all())
