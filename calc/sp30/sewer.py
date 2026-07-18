"""Самотёчная канализация по СП 30.13330.2020: самоочищение, уклоны, стояки.

Табличные значения — из rules/sp30/uklony_kanalizacii.yaml и propusknaya_stoyakov.yaml.
"""

import math

from calc.sp30.rules_loader import load_rule

_STACK_TABLES = {
    "pvh": "tablitsa_k1_pvh",
    "pp": "tablitsa_k2_pp",
    "chugun": "tablitsa_k3_chugun",
    "sml": "tablitsa_k4_sml",
}


def check_self_cleaning(v: float, h_over_d: float, polymer: bool) -> list[str]:
    """Проверка режима самоочищения — СП 30.13330.2020, п. 19.1, формула (33).

    Условие: V·sqrt(h/d) >= K (K = 0,5 для полимерных труб, 0,6 для прочих);
    дополнительно V >= 0,7 м/с и h/d >= 0,3.
    Возвращает список нарушений с цитатами; пустой список — все условия выполнены.
    """
    rule = load_rule("uklony_kanalizacii")["samoochishchenie"]
    k = rule["K"]["polimernye_truby"] if polymer else rule["K"]["prochie_materialy"]
    violations = []
    lhs = v * math.sqrt(h_over_d)
    if lhs < k:
        violations.append(
            f"V·sqrt(h/d) = {lhs:.3f} < K = {k} — не выполнено условие "
            f"самоочищения (СП 30.13330.2020, п. 19.1, формула (33))"
        )
    if v < rule["min_skorost_m_s"]:
        violations.append(
            f"скорость V = {v} м/с < {rule['min_skorost_m_s']} м/с "
            f"(СП 30.13330.2020, п. 19.1)"
        )
    if h_over_d < rule["min_napolneniye_h_d"]:
        violations.append(
            f"наполнение h/d = {h_over_d} < {rule['min_napolneniye_h_d']} "
            f"(СП 30.13330.2020, п. 19.1)"
        )
    return violations


def min_slope_non_calculated(d_mm: float) -> float:
    """Уклон нерасчётных участков 1/d — СП 30.13330.2020, п. 19.1.

    Применяется, только если условие (33) невыполнимо и увеличить число стояков
    на отводном трубопроводе невозможно.
    """
    return 1.0 / d_mm


def stack_capacity(material: str, stack_dn: float, otvod_dn: float, angle: float) -> float:
    """Пропускная способность вентилируемого стояка, л/с — СП 30.13330.2020, прил. К.

    material: pvh | pp | chugun | sml (таблицы К.1–К.4);
    stack_dn — диаметр стояка, мм; otvod_dn — наружный диаметр поэтажного отвода, мм;
    angle — угол присоединения отвода к стояку, градусов (45, 60, 87,5).
    """
    if material not in _STACK_TABLES:
        raise ValueError(f"Материал «{material}»; доступны: {', '.join(_STACK_TABLES)}")
    rows = load_rule("propusknaya_stoyakov")[_STACK_TABLES[material]]
    for row in rows:
        if float(row["otvod_mm"]) == float(otvod_dn) and float(row["ugol_grad"]) == float(angle):
            qs = {float(k): v for k, v in row["qs"].items()}
            if float(stack_dn) not in qs:
                raise ValueError(
                    f"Диаметра стояка {stack_dn} нет в таблице для {material}: "
                    f"есть {sorted(qs)}"
                )
            value = qs[float(stack_dn)]
            if value is None:
                raise ValueError(
                    f"Комбинация стояк {stack_dn}/отвод {otvod_dn} для {material} "
                    f"не нормируется («–» в таблице)"
                )
            return float(value)
    raise ValueError(
        f"Нет строки для отвода {otvod_dn} мм и угла {angle}° ({material}, прил. К)"
    )
