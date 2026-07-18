"""Трассировщик v0.1: манхэттенские трассы К1/В1/Т3 санузла-кластера по паспорту.

Вход — паспорт задачи (эксперимент 02: один санузел; эксперимент 03: кластер этажа
той же формы): коннекторы приборов, ось стояка К1, точка подключения воды. Выход —
сегменты труб {system, start, end, dia_mm, naznachenie}; в Revit их создаёт MCP.

Уклон отводных трубопроводов К1 по СП 30.13330.2020 подбирается расчётом (п. 19.1);
v0 принимает проектный уклон по умолчанию 0,02 и проверяет его нормоконтролем
(минимум 1/d для нерасчётных участков, неизменность уклона сборного — п. 18.2).

v0.1 (эксперимент 03): стояк может стоять в середине кластера — сборный/магистраль
строятся двумя лучами от стояка; ось трасс задаётся параметром axis ("x" — вдоль X,
как в эксперименте 02, "y" — вдоль Y: координаты транспонируются на входе/выходе);
диаметры подводок могут задаваться словарём по типам приборов.
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


def _swap_connector(c: dict) -> dict:
    return dict(c, x=c["y"], y=c["x"])


def _swap_passport(passport: dict) -> dict:
    """Транспонированная копия паспорта (x <-> y) для трассировки вдоль оси Y."""
    swapped = dict(passport)
    if "stoyak_k1" in passport:
        swapped["stoyak_k1"] = _swap_connector(passport["stoyak_k1"])
    if "tochka_podkl_voda" in passport:
        swapped["tochka_podkl_voda"] = _swap_connector(passport["tochka_podkl_voda"])
    swapped["pribory"] = [
        dict(f, connectors={k: _swap_connector(c) for k, c in f["connectors"].items()})
        for f in passport["pribory"]
    ]
    return swapped


def _swap_segments(segments: list[dict]) -> list[dict]:
    for s in segments:
        (x1, y1, z1), (x2, y2, z2) = s["start"], s["end"]
        s["start"], s["end"] = (y1, x1, z1), (y2, x2, z2)
    return segments


def route_k1(
    passport: dict,
    slope: float = 0.02,
    z_collector_stack: float | None = None,
    axis: str = "x",
) -> list[dict]:
    """Сборный отводной трубопровод К1 + отводы приборов (манхэттен, уклон к стояку).

    Коллектор идёт под полом по оси стояка лучами к крайним приборам с постоянным
    уклоном (п. 18.2 — уклон сборного не меняется); отвод прибора — вертикальный
    спуск от коннектора и горизонтальный участок с тем же уклоном.
    """
    if axis == "y":
        return _swap_segments(route_k1(_swap_passport(passport), slope, z_collector_stack))
    stack = passport["stoyak_k1"]
    sx, sy = float(stack["x"]), float(stack["y"])
    fixtures = passport["pribory"]
    a1 = load_rule("rashody_priborov")["fixtures"]
    if z_collector_stack is None:
        # лоток коллектора у стояка: ниже самого низкого коннектора К1 минимум на 100 мм
        z_collector_stack = min(f["connectors"]["k1"]["z"] for f in fixtures) - 100.0

    def z_col(x: float) -> float:
        return z_collector_stack + slope * abs(sx - x)

    segments = []
    xs = [float(f["connectors"]["k1"]["x"]) for f in fixtures]
    collector_dn = max(
        _sewer_dn(a1[f["tip_a1"]]["d_otvoda"]) for f in fixtures
    )
    for x_end in (min(xs), max(xs)):
        if abs(x_end - sx) < 1:
            continue  # все приборы этой стороны на оси стояка
        segments.append(_seg(
            "K1", (sx, sy, z_collector_stack), (x_end, sy, z_col(x_end)),
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


def route_k1_stack(passport: dict, stack_dn: float, z_verh: float, zapas_niz: float = 300.0) -> list[dict]:
    """Вертикальный стояк К1 кластера: от низа коллектора вниз с запасом до z_verh.

    Продолжение стояка вверх (вентиляционная часть, п. 19.6) и вниз (в подполье
    к магистрали) — вне охвата этажа; запас zapas_niz оставлен под врезку коллектора.
    """
    stack = passport["stoyak_k1"]
    x, y = float(stack["x"]), float(stack["y"])
    z_niz = float(stack["z_kollektora"]) - zapas_niz
    return [_seg("K1", (x, y, z_niz), (x, y, z_verh), stack_dn, "стояк К1")]


def route_water(
    passport: dict,
    system: str,
    main_dn: float,
    podvodka_dn: float | dict[str, float] = 15,
    axis: str = "x",
) -> list[dict]:
    """Магистраль В1/Т3 под потолком от точки подключения + опуски к приборам.

    system: "v1" | "t3" (ключ коннектора прибора); main_dn — диаметр магистрали
    по гидравлическому расчёту (calc.trace.sizing); podvodka_dn — диаметр подводки:
    число для всех приборов или словарь {tip_a1: dn} (не меньше d_podvodki
    по табл. А.1 — проверяет нормоконтроль).
    """
    if axis == "y":
        return _swap_segments(
            route_water(_swap_passport(passport), system, main_dn, podvodka_dn)
        )
    tp = passport["tochka_podkl_voda"]
    px, py, z_main = float(tp["x"]), float(tp["y"]), float(tp["z_mag"])
    sysname = system.upper()
    segments = []
    fixtures = [f for f in passport["pribory"] if system in f["connectors"]]
    xs = [float(f["connectors"][system]["x"]) for f in fixtures]
    for x_end in (min(xs), max(xs)):
        if abs(x_end - px) < 1:
            continue
        segments.append(_seg(
            sysname, (px, py, z_main), (x_end, py, z_main), main_dn,
            "магистраль под потолком от точки подключения"
        ))
    for f in fixtures:
        c = f["connectors"][system]
        x, y, z = float(c["x"]), float(c["y"]), float(c["z"])
        name = f["tip_a1"]
        dn = podvodka_dn.get(name, 15) if isinstance(podvodka_dn, dict) else podvodka_dn
        if abs(y - py) > 1:
            segments.append(_seg(sysname, (x, py, z_main), (x, y, z_main), dn,
                                 f"ответвление к {name}"))
        segments.append(_seg(sysname, (x, y, z_main), (x, y, z), dn,
                             f"опуск к {name}"))
    return segments
