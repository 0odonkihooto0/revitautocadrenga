"""Гидравлика v0 для санузла: расходы набора приборов и подбор диаметров.

Расчёт по СП 30.13330.2020: вероятность P — формула (3), расход q = 5·q0·α —
формула (2) (calc.sp30.water_demand); скорость ограничена прил. И / п. 8.26.
"""

import math

from calc.sp30 import sewer, water_demand

WATER_SORTAMENT = [15, 20, 25, 32, 40, 50, 65, 80, 100]
# СП 30.13330.2020, п. 8.26: общественные здания при шуме выше 40 дБ — 1,5 м/с;
# совпадает с прил. И при КМС до 5 (rules/sp30/skorosti_vody.yaml)
V_MAX_M_S = 1.5


def bathroom_flow(fixture_keys: list[str], u: int, q_hr_u: float, kind: str = "tot") -> dict:
    """Расчётный секундный расход воды набора приборов, л/с — ф. (2), (3) СП 30.

    kind: tot | c | h — общий, холодная, горячая. q0 набора принят по прибору
    с максимальным секундным расходом (концевые участки — п. 5.3, прим. 1).
    """
    q0_key = f"q0_{kind}"
    q0s = [water_demand.fixture(k)[q0_key] for k in fixture_keys]
    q0s = [q for q in q0s if q]
    if not q0s:
        raise ValueError(f"Ни у одного прибора нет расхода {q0_key}")
    q0 = max(q0s)
    n = len(q0s)
    p = water_demand.probability(q_hr_u, u, q0, n)
    q = water_demand.q_max(q0, n, p)
    return {"q0": q0, "n": n, "p": round(p, 4), "q_l_s": round(q, 3)}


def pick_water_diameter(q_l_s: float, v_max: float = V_MAX_M_S) -> dict:
    """Минимальный диаметр из сортамента, при котором скорость не выше v_max.

    Условный проход приравнен внутреннему диаметру (упрощение v0).
    """
    for dn in WATER_SORTAMENT:
        area = math.pi * (dn / 1000) ** 2 / 4
        v = (q_l_s / 1000) / area
        if v <= v_max:
            return {"dn": dn, "v_m_s": round(v, 2)}
    raise ValueError(f"Расход {q_l_s} л/с не проходит по сортаменту {WATER_SORTAMENT}")


def pick_podvodka(q0_l_s: float, d_min_mm: float | None = None,
                  v_max: float = V_MAX_M_S) -> int:
    """Диаметр подводки к прибору, мм: по скорости (п. 8.26) и не меньше табл. А.1.

    q0_l_s — секундный расход прибора; d_min_mm — d_podvodki по табл. А.1
    (None = «–», не нормируется: диаметр только по скорости).
    """
    dn_v = pick_water_diameter(q0_l_s, v_max)["dn"]
    need = max(dn_v, d_min_mm or 0)
    for dn in WATER_SORTAMENT:
        if dn >= need:
            return dn
    raise ValueError(f"Подводка {need} мм вне сортамента {WATER_SORTAMENT}")


def pick_k1_stack(passport: dict, q_tot_l_s: float, material: str = "pvh",
                  angle: float = 87.5, otvod_dn: float = 110) -> dict:
    """Подбор диаметра вентилируемого стояка К1 — СП 30.13330.2020, п. 19.2, прил. К.

    qs = q_tot + q0s_max (ф. 5); диаметр — минимальный по таблицам К.1–К.4,
    у которого пропускная способность не ниже qs. Если не проходит даже максимальный
    табличный — ok=False (увеличить диаметр нельзя: рассредоточить расход — п. 19.2).
    """
    a1 = [water_demand.fixture(f["tip_a1"]) for f in passport["pribory"]]
    q0s_max = max(f["q0_s"] for f in a1 if f["q0_s"])
    qs = water_demand.q_stack_sewer(q_tot_l_s, q0s_max)
    podbor = sewer.pick_stack_dn(material, otvod_dn, angle, qs)
    return {
        "qs_l_s": round(qs, 3), "q0s_max": q0s_max,
        "dn": podbor["dn"], "capacity_l_s": podbor["capacity_l_s"], "ok": podbor["ok"],
    }


def check_k1_stack(passport: dict, q_tot_l_s: float,
                   material: str = "pvh", angle: float = 87.5) -> dict:
    """Проверка стояка К1: qs = q_tot + q0s_max (ф. 5) против пропускной способности.

    Стояк вентилируемый — таблицы К.1–К.4 (calc.sp30.sewer.stack_capacity).
    """
    a1 = [water_demand.fixture(f["tip_a1"]) for f in passport["pribory"]]
    q0s_max = max(f["q0_s"] for f in a1 if f["q0_s"])
    qs = water_demand.q_stack_sewer(q_tot_l_s, q0s_max)
    stack_dn = 110  # существующий стояк модели 102 мм ~ Ду 100/110
    otvod_dn = 110
    capacity = sewer.stack_capacity(material, stack_dn, otvod_dn, angle)
    return {
        "qs_l_s": round(qs, 3),
        "q0s_max": q0s_max,
        "capacity_l_s": capacity,
        "ok": qs <= capacity,
    }
