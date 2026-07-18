"""Тесты трассировщика v0, гидравлики v0 и нормоконтроля v0 (этап 2 MVP)."""

import json
from pathlib import Path

import pytest

from calc.normcheck import checklist
from calc.trace import router, sizing

PASSPORT = json.loads(
    (Path(__file__).resolve().parents[1] / "experiments" / "02-mvp-sanuzel" / "passport.json")
    .read_text(encoding="utf-8")
)
FIXTURE_KEYS = [f["tip_a1"] for f in PASSPORT["pribory"]]


class TestRouterK1:
    def test_segmenty_postroeny(self):
        segs = router.route_k1(PASSPORT)
        # коллектор + отводы: у прибора на оси стояка 1 сегмент, у прочих 2
        assert any(s["naznachenie"].startswith("сборный") for s in segs)
        assert len(segs) >= 1 + len(PASSPORT["pribory"])

    def test_uklon_kollektora(self):
        segs = router.route_k1(PASSPORT, slope=0.02)
        col = next(s for s in segs if s["naznachenie"].startswith("сборный"))
        (x1, _, z1), (x2, _, z2) = col["start"], col["end"]
        assert (z2 - z1) / (x1 - x2) == pytest.approx(0.02)
        # конец коллектора выше начала: сток течёт к стояку
        assert z2 > z1

    def test_diametry_otvodov(self):
        segs = router.route_k1(PASSPORT)
        col = next(s for s in segs if s["naznachenie"].startswith("сборный"))
        assert col["dia_mm"] == 110  # унитаз и душ требуют 110 (отвод 85/100 -> 110)
        umyv = [s for s in segs if "umyvalnik" in s["naznachenie"]]
        assert umyv and all(s["dia_mm"] == 50 for s in umyv)

    def test_kollektor_na_osi_stoyaka(self):
        segs = router.route_k1(PASSPORT)
        col = next(s for s in segs if s["naznachenie"].startswith("сборный"))
        assert col["start"][0] == PASSPORT["stoyak_k1"]["x"]
        assert col["start"][1] == PASSPORT["stoyak_k1"]["y"]


class TestRouterWater:
    def test_v1_dohodit_do_vseh(self):
        segs = router.route_water(PASSPORT, "v1", main_dn=20)
        opuski = [s for s in segs if s["naznachenie"].startswith("опуск")]
        assert len(opuski) == len(PASSPORT["pribory"])

    def test_t3_bez_unitaza(self):
        segs = router.route_water(PASSPORT, "t3", main_dn=20)
        opuski = [s for s in segs if s["naznachenie"].startswith("опуск")]
        with_t3 = [f for f in PASSPORT["pribory"] if "t3" in f["connectors"]]
        assert len(opuski) == len(with_t3) == 4  # унитазу горячая вода не нужна

    def test_opusk_konchaetsya_v_konnektore(self):
        segs = router.route_water(PASSPORT, "v1", main_dn=20)
        wc = PASSPORT["pribory"][0]["connectors"]["v1"]
        assert any(s["end"] == (wc["x"], wc["y"], wc["z"]) for s in segs)


class TestSizing:
    def test_rashod_sanuzla(self):
        z = PASSPORT["zadanie_inzhenera"]
        flow = sizing.bathroom_flow(FIXTURE_KEYS, z["U_zhiteley"], z["q_hr_u_l"], "tot")
        # q0 максимум набора: ванна/душ с глубоким поддоном либо стиральная = 0,2...0,3
        assert flow["q0"] >= 0.2
        assert 0 < flow["p"] < 1
        assert flow["q_l_s"] > flow["q0"]  # хотя бы больше одного прибора

    def test_podbor_diametra(self):
        d = sizing.pick_water_diameter(0.5)
        assert d["dn"] in sizing.WATER_SORTAMENT
        assert d["v_m_s"] <= sizing.V_MAX_M_S

    def test_stoyak_prohodit(self):
        z = PASSPORT["zadanie_inzhenera"]
        flow = sizing.bathroom_flow(FIXTURE_KEYS, z["U_zhiteley"], z["q_hr_u_l"], "tot")
        st = sizing.check_k1_stack(PASSPORT, flow["q_l_s"])
        assert st["q0s_max"] == 1.6  # унитаз со смывным бачком, табл. А.1
        assert st["ok"]


class TestNormcheck:
    def test_chistye_trassy_prohodyat(self):
        segs = router.route_k1(PASSPORT, slope=0.02)
        findings = checklist.check_k1(segs) + checklist.check_k1_diameters(segs, PASSPORT)
        assert not [f for f in findings if f["status"] == "violation"]

    def test_maly_uklon_lovitsya(self):
        segs = router.route_k1(PASSPORT, slope=0.005)  # меньше 1/110
        findings = checklist.check_k1(segs)
        bad = [f for f in findings if f["status"] == "violation"]
        assert bad and "19.1" in bad[0]["text"]

    def test_otchet_renderitsya(self):
        segs = router.route_k1(PASSPORT)
        report = checklist.render_report(checklist.check_k1(segs))
        assert "Нормоконтроль" in report and "✅" in report
