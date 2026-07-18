"""Расчётные расходы воды и стоков по СП 30.13330.2020 (раздел 5, приложения А и Б).

Все табличные значения берутся из rules/sp30/*.yaml (сверены с PDF),
формулы — из rules/sp30/formuly_raskhodov.yaml.
"""

from bisect import bisect_left
from typing import Any

from calc.sp30.rules_loader import load_rule


def _interp1d(xs: list[float], ys: list[float], x: float, what: str) -> float:
    """Линейная интерполяция по табличным точкам; вне диапазона — ValueError."""
    if x < xs[0] or x > xs[-1]:
        raise ValueError(f"{what}={x} вне табличного диапазона [{xs[0]}, {xs[-1]}]")
    i = bisect_left(xs, x)
    if i < len(xs) and xs[i] == x:
        return ys[i]
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def alpha_b2(np_value: float) -> float:
    """Коэффициент α по таблице Б.2 (СП 30.13330.2020, приложение Б).

    Область применения: P (P_hr) <= 0,1 при любом N, а также P > 0,1 при N > 200.
    NP ниже 0,015 -> α = 0,200; промежуточные значения — линейная интерполяция.
    """
    t = load_rule("koefficient_alpha")["tablitsa_b2"]
    if np_value < t["np_menee"]["porog"]:
        return float(t["np_menee"]["alpha"])
    xs = [p[0] for p in t["tochki"]]
    ys = [p[1] for p in t["tochki"]]
    return _interp1d(xs, ys, np_value, "N*P")


def alpha_b1(n: float, p: float) -> float:
    """Коэффициент α по таблице Б.1 (СП 30.13330.2020, приложение Б).

    Область применения: P (P_hr) > 0,1 и N <= 200. Для промежуточных N и P —
    билинейная интерполяция (СП правило интерполяции не задаёт; принято линейное).
    """
    t = load_rule("koefficient_alpha")["tablitsa_b1"]
    p_values = [float(x) for x in t["p_values"]]
    ns = [float(row["n"]) for row in t["stroki"]]
    if not (ns[0] <= n <= ns[-1]):
        raise ValueError(f"N={n} вне диапазона таблицы Б.1 [{ns[0]}, {ns[-1]}]")
    # α для каждого табличного N при заданном P, затем интерполяция по N
    alphas_by_n = [
        _interp1d(p_values, [float(v) for v in row["alpha"]], p, "P")
        for row in t["stroki"]
    ]
    return _interp1d(ns, alphas_by_n, n, "N")


def probability(q_hr_u: float, u: int, q0: float, n: int) -> float:
    """Вероятность действия приборов P — СП 30.13330.2020, п. 5.4а, формула (3).

    P = (q_hr_u * U) / (q0 * N * 3600); при однотипных водопотребителях.
    q_hr_u — расход воды потребителем в час наибольшего водопотребления, л (табл. А.2);
    u — число водопотребителей; q0 — расход прибором, л/с; n — число приборов.
    """
    return (q_hr_u * u) / (q0 * n * 3600)


def q_max(q0: float, n: int, p: float) -> float:
    """Максимальный секундный расход q = 5·q0·α — СП 30.13330.2020, п. 5.3, формула (2).

    Выбор таблицы α по п. 5.3: Б.1 при P > 0,1 и N <= 200, иначе Б.2 (по N*P).
    """
    a = alpha_b1(n, p) if (p > 0.1 and n <= 200) else alpha_b2(n * p)
    return 5 * q0 * a


def q_stack_sewer(q_tot: float, q0s_max: float) -> float:
    """Расчётный расход стоков для стояка qs — СП 30.13330.2020, п. 5.5, формула (5).

    qs = q_tot + q0s_max, где q0s_max — расход стоков от прибора
    с максимальным водоотведением (табл. А.1), л/с.
    """
    return q_tot + q0s_max


def ks(n: float, length_m: float) -> float:
    """Коэффициент Ks — СП 30.13330.2020, таблица 5.1 (билинейная интерполяция)."""
    t = load_rule("formuly_raskhodov")["tablitsa_5_1"]
    l_values = [float(x) for x in t["L_values"]]
    ns = [float(row["n"]) for row in t["stroki"]]
    if not (ns[0] <= n <= ns[-1]):
        raise ValueError(f"N={n} вне диапазона таблицы 5.1 [{ns[0]}, {ns[-1]}]")
    ks_by_n = [
        _interp1d(l_values, [float(v) for v in row["ks"]], length_m, "L")
        for row in t["stroki"]
    ]
    return _interp1d(ns, ks_by_n, n, "N")


def q_horizontal_sewer(q_hr_tot_m3: float, ks_value: float, q0s: float) -> float:
    """Расход стоков горизонтального трубопровода qsL — СП 30.13330.2020, п. 5.7, ф. (7).

    qsL = q_hr_tot / 3,6 + Ks * q0s.
    """
    return q_hr_tot_m3 / 3.6 + ks_value * q0s


def fixture(key: str) -> dict[str, Any]:
    """Характеристики санитарного прибора — СП 30.13330.2020, таблица А.1."""
    fixtures = load_rule("rashody_priborov")["fixtures"]
    if key not in fixtures:
        raise KeyError(f"Прибор «{key}» не найден; доступны: {', '.join(fixtures)}")
    return fixtures[key]
