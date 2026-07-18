"""Тесты трассировщика v0.1 и подборов для кластеров этажа (эксперимент 03).

Синтетический кластер: стена вдоль Y (axis="y"), стояк в середине кластера —
проверяются два луча сборного, транспонирование осей, подбор стояка и подводок.
"""

import pytest

from calc.sp30 import sewer
from calc.trace import router, sizing
from calc.trace.connectors import synthesize_connectors

FLOOR = -1000.0

CLUSTER = {
    "stoyak_k1": {"x": 100.0, "y": 5000.0, "z_kollektora": FLOOR - 400},
    "tochka_podkl_voda": {"x": 100.0, "y": 5000.0, "z_mag": FLOOR + 2700},
    "pribory": [
        {"revit_id": 1, "tip_a1": "unitaz_kran",
         "connectors": synthesize_connectors("unitaz_kran", 0.0, 3000.0, FLOOR, axis="y")},
        {"revit_id": 2, "tip_a1": "umyvalnik_smesitel",
         "connectors": synthesize_connectors("umyvalnik_smesitel", 0.0, 7000.0, FLOOR, axis="y")},
        {"revit_id": 3, "tip_a1": "trap_du50",
         "connectors": synthesize_connectors("trap_du50", 1500.0, 5000.0, FLOOR, axis="y")},
    ],
}


class TestConnectors:
    def test_sostav_po_tabl_a1(self):
        c_wc = CLUSTER["pribory"][0]["connectors"]
        assert set(c_wc) == {"k1", "v1"}  # унитазу горячая вода не нужна
        c_um = CLUSTER["pribory"][1]["connectors"]
        assert set(c_um) == {"k1", "v1", "t3"}
        c_trap = CLUSTER["pribory"][2]["connectors"]
        assert set(c_trap) == {"k1"}  # у трапа только канализация

    def test_vysota_smyvnogo_krana_po_sp73(self):
        v1 = CLUSTER["pribory"][0]["connectors"]["v1"]
        assert v1["z"] == FLOOR + 800  # СП 73.13330.2016, п. 6.2.1
        assert "6.2.1" in v1["istochnik_vysoty"]

    def test_diametry_po_tabl_a1(self):
        assert CLUSTER["pribory"][0]["connectors"]["k1"]["dia_mm"] == 85
        assert CLUSTER["pribory"][1]["connectors"]["k1"]["dia_mm"] == 32
        assert CLUSTER["pribory"][2]["connectors"]["k1"]["dia_mm"] == 50

    def test_neizvestny_pribor(self):
        with pytest.raises(KeyError):
            synthesize_connectors("dzhakuzi", 0, 0, 0)


class TestRouterDvaLucha:
    def test_dva_lucha_sbornogo(self):
        segs = router.route_k1(CLUSTER, slope=0.02, z_collector_stack=FLOOR - 400, axis="y")
        collectors = [s for s in segs if s["naznachenie"].startswith("сборный")]
        assert len(collectors) == 2  # приборы по обе стороны стояка
        for col in collectors:
            assert col["start"][:2] == (100.0, 5000.0)  # оба луча от стояка
            (_, y1, z1), (_, y2, z2) = col["start"], col["end"]
            assert z2 > z1  # конец луча выше: сток течёт к стояку
            assert abs((z2 - z1) / abs(y1 - y2) - 0.02) < 1e-9

    def test_os_vdol_steny(self):
        segs = router.route_k1(CLUSTER, axis="y")
        collectors = [s for s in segs if s["naznachenie"].startswith("сборный")]
        for col in collectors:
            assert col["start"][0] == col["end"][0] == 100.0  # коллектор вдоль Y (x = const)

    def test_voda_dva_lucha_i_opuski(self):
        segs = router.route_water(CLUSTER, "v1", main_dn=40,
                                  podvodka_dn={"unitaz_kran": 40, "umyvalnik_smesitel": 15},
                                  axis="y")
        mains = [s for s in segs if s["naznachenie"].startswith("магистраль")]
        assert len(mains) == 2
        opuski = [s for s in segs if s["naznachenie"].startswith("опуск")]
        assert len(opuski) == 2  # унитаз + умывальник, у трапа воды нет
        wc = next(s for s in opuski if "unitaz" in s["naznachenie"])
        assert wc["dia_mm"] == 40  # подводка смывного крана из словаря
        assert wc["end"][2] == FLOOR + 800

    def test_stoyak_vertikalen(self):
        (seg,) = router.route_k1_stack(CLUSTER, stack_dn=110, z_verh=FLOOR + 2700)
        assert seg["start"][:2] == seg["end"][:2] == (100.0, 5000.0)
        assert seg["start"][2] == FLOOR - 400 - 300
        assert seg["end"][2] == FLOOR + 2700
        assert seg["dia_mm"] == 110


class TestPodbory:
    def test_podvodka_smyvnogo_krana_po_skorosti(self):
        # q0 = 1,4 л/с (унитаз со смывным краном): Ду32 даёт 1,74 м/с > 1,5 — нужен Ду40
        assert sizing.pick_podvodka(1.4, d_min_mm=None) == 40

    def test_podvodka_umyvalnika_ne_menshe_a1(self):
        assert sizing.pick_podvodka(0.09, d_min_mm=10) == 15

    def test_podbor_stoyaka_prohodit(self):
        p = sewer.pick_stack_dn("pvh", otvod_dn=110, angle=87.5, qs_l_s=3.5)
        assert p == {"dn": 110, "capacity_l_s": 3.58, "ok": True}

    def test_podbor_stoyaka_malenkogo(self):
        p = sewer.pick_stack_dn("pvh", otvod_dn=50, angle=45, qs_l_s=1.0)
        assert p["dn"] == 50 and p["ok"]

    def test_podbor_stoyaka_ne_prohodit(self):
        p = sewer.pick_stack_dn("pvh", otvod_dn=110, angle=87.5, qs_l_s=4.0)
        assert p["dn"] == 110 and not p["ok"]

    def test_pick_k1_stack_klastera(self):
        st = sizing.pick_k1_stack(CLUSTER, q_tot_l_s=2.05)
        assert st["q0s_max"] == 1.4  # унитаз со смывным краном, табл. А.1
        assert st["dn"] == 110 and st["ok"]
