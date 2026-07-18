"""Тесты напоров (СП 30.13330.2020, пп. 7.10, 8.21, 8.27, 8.28) и высот СП 73."""

import pytest

from calc.sp30 import pressure
from calc.sp30.rules_loader import load_rule


class TestGranitsyNaporov:
    def test_min_svobodny_napor(self):
        # п. 8.21: не менее 20,0 м вод. ст.
        assert pressure.min_free_head_upper_fixture() == 20.0

    def test_max_gidrostatichesky(self):
        # п. 7.10: не более 45 м вод. ст.
        assert pressure.max_hydrostatic_head_lower_fixture() == 45.0

    def test_check_heads_ok(self):
        assert pressure.check_heads(head_at_upper_fixture=22, head_at_lower_fixture=40) == []

    def test_check_heads_narusheniya(self):
        violations = pressure.check_heads(head_at_upper_fixture=15, head_at_lower_fixture=50)
        assert len(violations) == 2
        assert "8.21" in violations[0]
        assert "7.10" in violations[1]


class TestFormuly:
    def test_poteri_na_uchastke(self):
        # формула (15): i=0,1 м/м, l=10 м, хоз-питьевой (kl=0,3): 0,1*10*1,3 = 1,3
        assert pressure.pipe_section_loss(0.1, 10) == pytest.approx(1.3)

    def test_kl_protivopozharny(self):
        # kl = 0,1 для противопожарных сетей
        assert pressure.pipe_section_loss(0.1, 10, network="protivopozharny") == pytest.approx(1.1)

    def test_neizvestnaya_set(self):
        with pytest.raises(ValueError):
            pressure.pipe_section_loss(0.1, 10, network="neizvestnaya")

    def test_trebuemyi_napor(self):
        # формула (14): 12 + 4 + 20 (по умолчанию из п. 8.21) + 1,5 + 3 + 1 = 41,5
        htr = pressure.required_head(
            h_geom=12, sum_pipe_losses=4, sum_meter_losses=1.5, h_heater=3, h_inlet=1
        )
        assert htr == pytest.approx(41.5)

    def test_trebuemyi_napor_yavny_h_pribora(self):
        assert pressure.required_head(10, 2, h_fixture=3) == pytest.approx(15)


class TestVysotySP73:
    def test_tablitsa_3(self):
        # СП 73.13330.2016, таблица 3
        rows = load_rule("vysoty_ustanovki_priborov", doc="sp73")["tablitsa_3"]["stroki"]
        assert rows["umyvalnik_do_verha_borta"]["zhilye"] == 800
        assert rows["vanna_do_verha_borta"]["shkoly_lechebnye"] == 500
        assert rows["pitevoy_fontanchik_podvesnoy_do_verha_borta"]["doshkolnye_invalidy"] is None

    def test_armatura(self):
        # п. 6.2.1: смеситель душа 1200 мм, душевые сетки 2100-2250 мм
        arm = load_rule("vysoty_ustanovki_priborov", doc="sp73")["armatura"]
        assert arm["ot_chistogo_pola_mm"]["smesiteli_dusha"] == 1200
        assert arm["dushevye_setki_mm"]["obychnye_ot_niza_setki"] == [2100, 2250]
