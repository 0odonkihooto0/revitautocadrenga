"""Тесты парсера и BM25-поиска norms_mcp (слой 3 базы знаний)."""

import pytest

from norms_mcp.index import get_index
from norms_mcp.parser import DOC_META, parse_doc


@pytest.fixture(scope="module")
def index():
    return get_index()


class TestParser:
    def test_klyuchevye_punkty_sp30(self):
        clauses = {c.clause for c in parse_doc("sp30")}
        for want in ("5.3", "18.2", "19.1", "8.27", "прил. К"):
            assert want in clauses, f"нет чанка {want}"

    def test_klyuchevye_punkty_drugih_dokov(self):
        assert "6.3.4" in {c.clause for c in parse_doc("sp73")}
        assert "7.6" in {c.clause for c in parse_doc("sp10")}
        assert "4.2" in {c.clause for c in parse_doc("gost21601")}
        assert "17" in {c.clause for c in parse_doc("pp87")}

    def test_vse_doky_razobrany(self, index):
        docs = {c.doc for c in index.chunks}
        assert docs == set(DOC_META)

    def test_chanki_ne_pustye_i_ne_ogromnye(self, index):
        for c in index.chunks:
            assert c.text
            assert len(c.text) < 20000


class TestSearch:
    def test_rashod_unitaza(self, index):
        results = index.search("расход стоков от унитаза со смывным бачком", doc="sp30", top_n=5)
        assert any("А.1" in c.clause or "16" in c.text for c, _ in results)

    def test_samoochishchenie(self, index):
        results = index.search("условие самоочищения безнапорного трубопровода", doc="sp30", top_n=5)
        assert any(c.clause.startswith("19.1") for c, _ in results)

    def test_vysota_ustanovki_sp73(self, index):
        results = index.search("высота установки санитарных приборов от пола", doc="sp73", top_n=5)
        assert any(c.clause.startswith("6.3.4") or "табл" in c.clause for c, _ in results)

    def test_filtr_po_dokumentu(self, index):
        results = index.search("пожарный кран расход", doc="sp10", top_n=5)
        assert results and all(c.doc == "sp10" for c, _ in results)

    def test_get_clause(self, index):
        chunks = index.get_clause("sp30", "19.1")
        assert chunks and "самоочища" in chunks[0].text.lower()

    def test_get_clause_tablitsa(self, index):
        chunks = index.get_clause("sp30", "табл. К.5")
        assert chunks and "невентилируемых" in chunks[0].text.lower()
