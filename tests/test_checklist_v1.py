"""Тесты чек-листа v1 (эксперимент 03): выпуск прибора, высоты СП 73, Hтр ф. (14)."""

import pytest

from calc.normcheck import checklist
from calc.sp30 import pressure


def _cluster(z_krana: float = 800.0):
    return {
        "pribory": [
            {"revit_id": 1, "tip_a1": "unitaz_kran", "connectors": {
                "k1": {"x": 0, "y": 0, "z": 180, "dia_mm": 85},
                "v1": {"x": 0, "y": 100, "z": z_krana, "dia_mm": None},
            }},
            {"revit_id": 2, "tip_a1": "trap_du100", "connectors": {
                "k1": {"x": 500, "y": 0, "z": 0, "dia_mm": 100},
            }},
        ],
    }


class TestOtvodVsVypusk:
    def test_suzhenie_lovitsya(self):
        # грабля эксперимента 02: отвод Ду50 при выпуске прибора 100 мм
        segs = [{"system": "K1", "start": (0, 0, 0), "end": (1, 0, 0),
                 "dia_mm": 50, "naznachenie": "отвод trap_du100 к коллектору"}]
        findings = checklist.check_otvod_vs_vypusk(segs, _cluster())
        bad = [f for f in findings if f["status"] == "violation"]
        assert bad and "18.34" in bad[0]["text"] and "trap_du100" in bad[0]["text"]

    def test_dostatochny_otvod_prohodit(self):
        segs = [
            {"system": "K1", "start": (0, 0, 0), "end": (1, 0, 0),
             "dia_mm": 110, "naznachenie": "отвод trap_du100 к коллектору"},
            {"system": "K1", "start": (0, 0, 0), "end": (1, 0, 0),
             "dia_mm": 110, "naznachenie": "выпуск unitaz_kran в коллектор"},
        ]
        findings = checklist.check_otvod_vs_vypusk(segs, _cluster())
        assert not [f for f in findings if f["status"] == "violation"]


class TestVysotyPriborov:
    def test_smyvnoy_kran_800(self):
        findings = checklist.check_fixture_heights(_cluster(800.0), floor_z_mm=0.0)
        oks = [f for f in findings if f["status"] == "ok"]
        assert oks and "6.2.1" in oks[0]["text"]

    def test_otkloneniye_lovitsya(self):
        findings = checklist.check_fixture_heights(_cluster(900.0), floor_z_mm=0.0)
        bad = [f for f in findings if f["status"] == "violation"]
        assert bad and "800" in bad[0]["text"]

    def test_dopusk_20mm(self):
        findings = checklist.check_fixture_heights(_cluster(815.0), floor_z_mm=0.0)
        assert not [f for f in findings if f["status"] == "violation"]


class TestTrebuemyNapor:
    def test_bez_garantirovannogo_info(self):
        (f,) = checklist.check_required_head(2.0, 50, dlina_m=10.0, h_geom_m=6.0)
        assert f["status"] == "info"
        assert "формула (14)" in f["text"] and "задание инженера" in f["text"]

    def test_prevyshenie_lovitsya(self):
        (f,) = checklist.check_required_head(2.0, 50, 10.0, 6.0, garantirovanny_m=10.0)
        assert f["status"] == "violation" and "насосная" in f["text"]

    def test_zapas_prohodit(self):
        (f,) = checklist.check_required_head(2.0, 50, 10.0, 6.0, garantirovanny_m=40.0)
        assert f["status"] == "ok"


class TestDarcy:
    def test_i_gladkoy_truby(self):
        # Ду20, v = 1 м/с (q = 0,3142 л/с): Re = 15267, λ = 0,0285, i = 0,0725 м/м
        i = pressure.unit_loss_darcy(0.31416, 20)
        assert i == pytest.approx(0.0725, rel=0.01)

    def test_laminarny_rezhim(self):
        # малый расход: Re < 2300 — λ = 64/Re
        i = pressure.unit_loss_darcy(0.01, 20)
        assert i > 0
