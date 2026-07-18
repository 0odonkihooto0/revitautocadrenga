"""Тесты самотёчной канализации (СП 30.13330.2020, п. 19.1 и приложение К)."""

import pytest

from calc.sp30 import sewer


class TestSamoochishchenie:
    def test_usloviye_vypolneno(self):
        # 0,71 * sqrt(0,51) = 0,507 >= 0,5 (полимер); V и h/d выше минимумов
        assert sewer.check_self_cleaning(v=0.71, h_over_d=0.51, polymer=True) == []

    def test_narushena_formula_33(self):
        # 0,7 * sqrt(0,5) = 0,495 < 0,5
        violations = sewer.check_self_cleaning(v=0.7, h_over_d=0.5, polymer=True)
        assert len(violations) == 1
        assert "формула (33)" in violations[0]

    def test_narushena_skorost(self):
        # 0,65 * sqrt(0,6) = 0,503 >= 0,5, но V < 0,7 м/с
        violations = sewer.check_self_cleaning(v=0.65, h_over_d=0.6, polymer=True)
        assert len(violations) == 1
        assert "0,7" in violations[0].replace("0.7", "0,7")

    def test_chugun_zhestche_polimera(self):
        # для непполимерных K = 0,6: 1,0 * sqrt(0,25) = 0,5 < 0,6 и h/d < 0,3
        violations = sewer.check_self_cleaning(v=1.0, h_over_d=0.25, polymer=False)
        assert len(violations) == 2

    def test_uklon_neraschetnykh(self):
        assert sewer.min_slope_non_calculated(110) == pytest.approx(1 / 110)
        assert sewer.min_slope_non_calculated(50) == pytest.approx(0.02)


class TestPropusknayaStoyakov:
    def test_pvh(self):
        # таблица К.1
        assert sewer.stack_capacity("pvh", stack_dn=110, otvod_dn=50, angle=45) == 8.22
        assert sewer.stack_capacity("pvh", stack_dn=110, otvod_dn=110, angle=87.5) == 3.58

    def test_pp(self):
        # таблица К.2
        assert sewer.stack_capacity("pp", stack_dn=50, otvod_dn=40, angle=60) == 1.14

    def test_chugun(self):
        # таблица К.3
        assert sewer.stack_capacity("chugun", stack_dn=100, otvod_dn=50, angle=87.5) == 3.67

    def test_sml(self):
        # таблица К.4
        assert sewer.stack_capacity("sml", stack_dn=150, otvod_dn=100, angle=60) == 13.50

    def test_nenormiruemaya_kombinatsiya(self):
        # «–» в таблице: стояк 50 при отводе 110
        with pytest.raises(ValueError):
            sewer.stack_capacity("pvh", stack_dn=50, otvod_dn=110, angle=45)

    def test_neizvestny_material(self):
        with pytest.raises(ValueError):
            sewer.stack_capacity("med", stack_dn=110, otvod_dn=50, angle=45)

    def test_sanuzel_prokhodit_po_stoyaku(self):
        # сквозной вывод: qs санузла 1,962 л/с (см. test_water_demand) проходит
        # через вентилируемый стояк ПВХ 110 даже при угле 87,5° (3,58 л/с)
        assert sewer.stack_capacity("pvh", 110, 110, 87.5) >= 1.962


class TestNeventiliruemyeStoyaki:
    def test_pvh_k5(self):
        # таблица К.5: высота 1 м и 9 м, крайние колонки
        assert sewer.stack_capacity_unvented("pvh", 50, 50, 45, work_height_m=1) == 1.80
        assert sewer.stack_capacity_unvented("pvh", 110, 110, 87.5, work_height_m=9) == 1.10

    def test_pp_k6(self):
        # таблица К.6: отвод 40 нормируется только для ПП
        assert sewer.stack_capacity_unvented("pp", 50, 40, 60, work_height_m=2) == 0.91
        assert sewer.stack_capacity_unvented("pp", 110, 40, 87.5, work_height_m=5) == 1.77

    def test_chugun_k7(self):
        # таблица К.7: высоты до 13 м
        assert sewer.stack_capacity_unvented("chugun", 150, 150, 45, work_height_m=1) == 20.0
        assert sewer.stack_capacity_unvented("chugun", 150, 100, 60, work_height_m=13) == 1.40

    def test_vysota_okruglyaetsya_vverkh(self):
        # 2,4 м -> строка 3 м (консервативно): ПВХ 110/110 45° = 5,00
        assert sewer.stack_capacity_unvented("pvh", 110, 110, 45, work_height_m=2.4) == 5.00

    def test_vysota_bolshe_tablichnoy(self):
        with pytest.raises(ValueError):
            sewer.stack_capacity_unvented("pvh", 110, 110, 45, work_height_m=9.5)

    def test_nenormiruemaya_para(self):
        # отвод 40 не нормируется для ПВХ
        with pytest.raises(ValueError):
            sewer.stack_capacity_unvented("pvh", 50, 40, 45, work_height_m=1)

    def test_vozdushny_klapan_k8(self):
        # таблица К.8
        assert sewer.stack_capacity_air_valve("pp", 110, 50, 45) == 6.81
        assert sewer.stack_capacity_air_valve("sml", 100, 110, 87.5) == 2.88

    def test_klapan_nenormiruemy(self):
        # «–»: стояк 50 при отводе 110
        with pytest.raises(ValueError):
            sewer.stack_capacity_air_valve("pvh", 50, 110, 45)
