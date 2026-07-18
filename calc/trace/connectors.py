"""Синтез точек подключения приборов по нормам — для АР-моделей без MEP-коннекторов.

У архитектурных семейств санприборов нет MEP-коннекторов, поэтому точки подключения
К1/В1/Т3 синтезируются из позиции прибора и нормативных данных:

- высоты водоразборной арматуры от чистого пола — СП 73.13330.2016, п. 6.2.1
  (rules/sp73/vysoty_ustanovki_priborov.yaml);
- минимальные диаметры подводок и отводов — СП 30.13330.2020, табл. А.1
  (rules/sp30/rashody_priborov.yaml);
- высоты канализационных выпусков и подводок к смесителям нормами не заданы —
  приняты конструктивные значения (в паспорте помечаются «⚠️ задание инженера»).
"""

from typing import Any

from calc.sp30.rules_loader import load_rule

# Конструктивные высоты оси канализационного отвода от чистого пола, мм (допущения v0):
# подвесной унитаз — горизонтальный выпуск в стену; умывальник — отвод сифона в стене;
# мойки общепита и трапы — слив вертикально в пол (разрыв струи / лоток в полу).
K1_Z_MM: dict[str, float] = {
    "unitaz_kran": 180.0,
    "unitaz_bachok": 180.0,
    "umyvalnik_smesitel": 500.0,
    "umyvalnik_kran": 500.0,
    "moyka_obshchepit": 0.0,
    "rakovina_kran": 0.0,
    "trap_du50": 0.0,
    "trap_du100": 0.0,
}

# Конструктивная высота подводки воды под бортом прибора, мм (допущение v0);
# для приборов с нормированной высотой арматуры значение берётся из правила СП 73.
WATER_Z_DEFAULT_MM = 600.0

# Смещение пары подводок В1/Т3 от оси прибора вдоль стены, мм (как в модели эксперимента 02)
WATER_OFFSET_MM = 100.0


def _water_z(tip_a1: str) -> tuple[float, str]:
    """Высота точки подключения воды от пола, мм + источник значения.

    Смывной кран унитаза — 800 мм от пола (СП 73.13330.2016, п. 6.2.1);
    остальным приборам — конструктивные 600 мм под бортом (допущение v0).
    """
    armatura = load_rule("vysoty_ustanovki_priborov", doc="sp73")["armatura"]
    if tip_a1 in ("unitaz_kran",):
        z = float(armatura["ot_chistogo_pola_mm"]["smyvnye_krany_unitazov"])
        return z, "СП 73.13330.2016, п. 6.2.1 (смывные краны унитазов)"
    return WATER_Z_DEFAULT_MM, "конструктивно под бортом прибора (⚠️ допущение v0)"


def synthesize_connectors(
    tip_a1: str, x: float, y: float, floor_z: float, axis: str = "y"
) -> dict[str, dict[str, Any]]:
    """Точки подключения прибора {"k1": ..., "v1": ..., "t3": ...} по нормам.

    x, y — точка вставки прибора (для настенных — на оси стены); floor_z — отметка
    чистого пола, мм; axis — ось стены кластера ("y": стена вертикальна в плане,
    пара В1/Т3 разносится по y; "x" — по x). Состав коннекторов — по табл. А.1:
    Т3 только у приборов с q0_h, у трапов воды нет вовсе.
    """
    a1 = load_rule("rashody_priborov")["fixtures"]
    if tip_a1 not in a1:
        raise KeyError(f"Прибор «{tip_a1}» отсутствует в rules/sp30/rashody_priborov.yaml")
    row = a1[tip_a1]
    if tip_a1 not in K1_Z_MM:
        raise KeyError(f"Нет конструктивной высоты выпуска для «{tip_a1}» (K1_Z_MM)")

    connectors: dict[str, dict[str, Any]] = {
        "k1": {"x": x, "y": y, "z": floor_z + K1_Z_MM[tip_a1], "dia_mm": row["d_otvoda"]}
    }
    if row["q0_tot"] is None:  # трапы: только канализация
        return connectors

    z_w, istochnik = _water_z(tip_a1)
    dx, dy = (WATER_OFFSET_MM, 0.0) if axis == "x" else (0.0, WATER_OFFSET_MM)
    connectors["v1"] = {
        "x": x + dx, "y": y + dy, "z": floor_z + z_w,
        "dia_mm": row["d_podvodki"], "istochnik_vysoty": istochnik,
    }
    if row["q0_h"] is not None:
        connectors["t3"] = {
            "x": x - dx, "y": y - dy, "z": floor_z + z_w,
            "dia_mm": row["d_podvodki"], "istochnik_vysoty": istochnik,
        }
    return connectors
