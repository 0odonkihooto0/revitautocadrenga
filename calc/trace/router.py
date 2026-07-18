"""Трассировщик v0: манхэттенские трассы К1/В1/Т3 санузла по паспорту задачи.

Вход — паспорт (experiments/02-mvp-sanuzel/passport.json): коннекторы приборов,
ось существующего стояка К1, точка подключения воды. Выход — сегменты труб
{system, start, end, dia_mm, naznachenie}; в Revit их создаёт MCP `create_pipe`.

Уклон отводных трубопроводов К1 по СП 30.13330.2020 подбирается расчётом (п. 19.1);
v0 принимает проектный уклон по умолчанию 0,02 и проверяет его нормоконтролем
(минимум 1/d для нерасчётных участков, неизменность уклона сборного — п. 18.2).
"""

from typing import Any

from calc.sp30.rules_loader import load_rule

Point = tuple[float, float, float]

# сортамент канализационных труб ПВХ, мм (наружный/условный для v0 совпадают)
SEWER_SORTAMENT = [50, 110]


def _sewer_dn(min_otvod_mm: float) -> int:
    """Диаметр отвода из сортамента: минимальный не меньше d_otvoda по табл. А.1."""
    for dn in SEWER_SORTAMENT:
        if dn >= min_otvod_mm:
            return dn
    raise ValueError(f"Нет трубы под отвод {min_otvod_mm} мм в сортаменте {SEWER_SORTAMENT}")


def _seg(system: str, start: Point, end: Point, dia: float, what: str) -> dict[str, Any]:
    return {"system": system, "start": start, "end": end, "dia_mm": dia, "naznachenie": what}


def route_k1(passport: dict, slope: float = 0.02, z_collector_stack: float | None = None) -> list[dict]:
    """Сборный отводной трубопровод К1 + отводы приборов (манхэттен, уклон к стояку).

    Коллектор идёт под полом по оси стояка (y = y_ст) от стояка до дальнего прибора
    с постоянным уклоном (п. 18.2 — уклон сборного не меняется); отвод прибора —
    вертикальный спуск от коннектора и горизонтальный участок с тем же уклоном.
    """
    stack = passport["stoyak_k1"]
    sx, sy = float(stack["x"]), float(stack["y"])
    fixtures = passport["pribory"]
    a1 = load_rule("rashody_priborov")["fixtures"]
    if z_collector_stack is None:
        # лоток коллектора у стояка: ниже самого низкого коннектора К1 минимум на 100 мм
        z_collector_stack = min(f["connectors"]["k1"]["z"] for f in fixtures) - 100.0

    def z_col(x: float) -> float:
        return z_collector_stack + slope * (sx - x)

    segments = []
    x_far = min(float(f["connectors"]["k1"]["x"]) for f in fixtures)
    collector_dn = max(
        _sewer_dn(a1[f["tip_a1"]]["d_otvoda"]) for f in fixtures
    )
    segments.append(_seg(
        "K1", (sx, sy, z_collector_stack), (x_far, sy, z_col(x_far)),
        collector_dn, "сборный отводной трубопровод к стояку"
    ))
    for f in fixtures:
        c = f["connectors"]["k1"]
        x, y, z = float(c["x"]), float(c["y"]), float(c["z"])
        dn = _sewer_dn(a1[f["tip_a1"]]["d_otvoda"])
        z_join = z_col(x)
        name = f["tip_a1"]
        if abs(y - sy) < 1:
            segments.append(_seg("K1", (x, y, z), (x, y, z_join), dn, f"выпуск {name} в коллектор"))
        else:
            z_drop = z_join + slope * abs(y - sy)
            if z - z_drop > 1:
                segments.append(_seg("K1", (x, y, z), (x, y, z_drop), dn, f"опуск от {name}"))
            segments.append(_seg("K1", (x, y, z_drop), (x, sy, z_join), dn, f"отвод {name} к коллектору"))
    return segments


def route_water(passport: dict, system: str, main_dn: float, podvodka_dn: float = 15) -> list[dict]:
    """Магистраль В1/Т3 под потолком от точки подключения + опуски к приборам.

    system: "v1" | "t3" (ключ коннектора прибора); main_dn — диаметр магистрали
    по гидравлическому расчёту (calc.trace.sizing), podvodka_dn — диаметр подводки
    (не меньше d_podvodki по табл. А.1 — проверяет нормоконтроль).
    """
    tp = passport["tochka_podkl_voda"]
    px, py, z_main = float(tp["x"]), float(tp["y"]), float(tp["z_mag"])
    sysname = system.upper()
    segments = []
    fixtures = [f for f in passport["pribory"] if system in f["connectors"]]
    x_far = min(float(f["connectors"][system]["x"]) for f in fixtures)
    segments.append(_seg(
        sysname, (px, py, z_main), (x_far, py, z_main), main_dn,
        "магистраль под потолком от точки подключения"
    ))
    for f in fixtures:
        c = f["connectors"][system]
        x, y, z = float(c["x"]), float(c["y"]), float(c["z"])
        name = f["tip_a1"]
        if abs(y - py) > 1:
            segments.append(_seg(sysname, (x, py, z_main), (x, y, z_main), podvodka_dn,
                                 f"ответвление к {name}"))
        segments.append(_seg(sysname, (x, y, z_main), (x, y, z), podvodka_dn,
                             f"опуск к {name}"))
    return segments
