"""Тесты расчёта расходов воды (СП 30.13330.2020, раздел 5, приложения А и Б).

Опорные значения — точки таблиц Б.1, Б.2, 5.1, А.1, сверенные с PDF,
и ручные расчёты по формулам (2), (3), (5), (7) с промежуточными значениями.
"""

import pytest

from calc.sp30 import water_demand as wd


class TestAlphaB2:
    def test_tochki_tablitsy(self):
        # точные точки таблицы Б.2
        assert wd.alpha_b2(0.015) == 0.202
        assert wd.alpha_b2(0.2) == 0.449
        assert wd.alpha_b2(1.6) == 1.261
        assert wd.alpha_b2(8.0) == 3.524

    def test_np_menee_poroga(self):
        # «Менее 0,015» -> 0,200
        assert wd.alpha_b2(0.01) == 0.200

    def test_interpolyatsiya(self):
        # между 0,032 (0,241) и 0,033 (0,243)
        assert wd.alpha_b2(0.0325) == pytest.approx(0.242, abs=1e-9)

    def test_vne_diapazona(self):
        with pytest.raises(ValueError):
            wd.alpha_b2(1300)


class TestAlphaB1:
    def test_tochki_tablitsy(self):
        assert wd.alpha_b1(2, 0.1) == 0.39
        assert wd.alpha_b1(10, 0.2) == 1.25
        assert wd.alpha_b1(200, 0.8) == 39.50

    def test_vne_diapazona(self):
        with pytest.raises(ValueError):
            wd.alpha_b1(300, 0.2)
        with pytest.raises(ValueError):
            wd.alpha_b1(10, 0.9)


class TestFormuly:
    def test_veroyatnost_formula_3(self):
        # квартира: ванна >=1500 мм (q_hr_u_tot = 11,6 л по табл. А.2), U=3, N=3, q0=0,3
        p = wd.probability(q_hr_u=11.6, u=3, q0=0.3, n=3)
        assert p == pytest.approx(34.8 / 3240, rel=1e-9)  # 0,01074

    def test_q_max_po_b2(self):
        # P <= 0,1 -> Б.2: N*P = 0,032, α = 0,241, q = 5*0,3*0,241 = 0,3615
        q = wd.q_max(q0=0.3, n=3, p=0.032 / 3)
        assert q == pytest.approx(0.3615, abs=1e-6)

    def test_q_max_po_b1(self):
        # P > 0,1 и N <= 200 -> Б.1: α(10; 0,2) = 1,25, q = 5*0,2*1,25 = 1,25
        assert wd.q_max(q0=0.2, n=10, p=0.2) == pytest.approx(1.25, abs=1e-9)

    def test_q_stokov_stoyaka_formula_5(self):
        # qs = q_tot + q0s_max: 0,3615 + 1,6 (унитаз со смывным бачком) = 1,9615
        assert wd.q_stack_sewer(0.3615, 1.6) == pytest.approx(1.9615)

    def test_ks_tablitsa_5_1(self):
        assert wd.ks(n=8, length_m=3) == 0.53
        assert wd.ks(n=1000, length_m=1000) == 0.71

    def test_q_gorizontalny_formula_7(self):
        # qsL = 3,6/3,6 + 0,53*1,6 = 1,848
        assert wd.q_horizontal_sewer(3.6, 0.53, 1.6) == pytest.approx(1.848)


class TestFixtures:
    def test_unitaz(self):
        f = wd.fixture("unitaz_bachok")
        assert f["q0_s"] == 1.6
        assert f["d_otvoda"] == 85

    def test_vanna(self):
        f = wd.fixture("vanna_smesitel")
        assert f["q0_tot"] == 0.25
        assert f["q0_s"] == 1.1

    def test_neizvestny_pribor(self):
        with pytest.raises(KeyError):
            wd.fixture("dzhakuzi")


class TestSanuzelSkvoznoy:
    """Сквозной расчёт типового санузла (унитаз + умывальник + ванна), 3 жителя.

    Жилой дом с ваннами >= 1500 мм: q_hr_u_tot = 11,6 л, q0_tot = 0,3 л/с (табл. А.2).
    """

    def test_raschet(self):
        n, u = 3, 3
        p = wd.probability(q_hr_u=11.6, u=u, q0=0.3, n=n)
        assert p < 0.1  # применима таблица Б.2
        q = wd.q_max(q0=0.3, n=n, p=p)
        # N*P = 0,0322; α между 0,032 (0,241) и 0,033 (0,243)
        assert q == pytest.approx(5 * 0.3 * 0.2413, abs=0.001)
        qs = wd.q_stack_sewer(q, wd.fixture("unitaz_bachok")["q0_s"])
        assert qs == pytest.approx(1.962, abs=0.001)
