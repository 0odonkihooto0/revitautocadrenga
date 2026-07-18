"""Rule-based чек-лист трасс санузла: уклоны, диаметры, скорости, стояк.

Каждое замечание — с цитатой пункта СП (источники берутся из YAML-правил слоя 1).
Вход — сегменты calc.trace.router и результаты calc.trace.sizing.
"""

import math
from typing import Any

from calc.sp30.rules_loader import load_rule
from calc.trace.sizing import V_MAX_M_S

Finding = dict[str, Any]  # {status: ok|violation|info, text: str}


def _f(status: str, text: str) -> Finding:
    return {"status": status, "text": text}


def _geometry(seg: dict) -> tuple[float, float]:
    """(горизонтальная длина, перепад высот start-end) сегмента, мм."""
    (x1, y1, z1), (x2, y2, z2) = seg["start"], seg["end"]
    return math.hypot(x2 - x1, y2 - y1), z1 - z2


def check_k1(segments: list[dict]) -> list[Finding]:
    """Уклоны и диаметры самотёчных сегментов К1 — СП 30.13330.2020, пп. 18.2, 19.1."""
    findings = []
    slopes = []
    for seg in segments:
        dxy, dz_to_end = _geometry(seg)
        if dxy < 1:
            continue  # вертикальный участок
        # сток должен течь к концу сегмента (конец ниже начала — уклон положительный)
        slope = -dz_to_end / dxy if seg["naznachenie"].startswith("сборный") else abs(dz_to_end) / dxy
        slopes.append(round(abs(slope), 4))
        min_slope = 1.0 / seg["dia_mm"]  # 1/d, напр. 1/110 = 0,009 — п. 19.1
        if abs(slope) + 1e-9 < min_slope:
            findings.append(_f(
                "violation",
                f"уклон {abs(slope):.4f} сегмента «{seg['naznachenie']}» меньше минимального "
                f"1/d = {min_slope:.4f} (СП 30.13330.2020, п. 19.1, нерасчётные участки)",
            ))
        else:
            findings.append(_f(
                "ok",
                f"уклон {abs(slope):.4f} ≥ 1/d = {min_slope:.4f} — «{seg['naznachenie']}» "
                f"(СП 30.13330.2020, п. 19.1)",
            ))
    if len(set(slopes)) > 1:
        findings.append(_f(
            "violation",
            f"уклон сборного/отводных участков непостоянен {sorted(set(slopes))} — менять уклон "
            f"сборного отводного трубопровода не допускается (СП 30.13330.2020, п. 18.2)",
        ))
    else:
        findings.append(_f(
            "ok", "уклон горизонтальных участков постоянен (СП 30.13330.2020, п. 18.2)"
        ))
    return findings


def check_k1_diameters(segments: list[dict], passport: dict) -> list[Finding]:
    """Диаметры отводов не меньше минимальных по табл. А.1 и не убывают к стояку."""
    findings = []
    a1 = load_rule("rashody_priborov")["fixtures"]
    collector = max(s["dia_mm"] for s in segments if s["naznachenie"].startswith("сборный"))
    for f in passport["pribory"]:
        d_min = a1[f["tip_a1"]]["d_otvoda"]
        segs = [s for s in segments if f["tip_a1"] in s["naznachenie"]]
        d_fact = min(s["dia_mm"] for s in segs) if segs else None
        if d_fact is None:
            findings.append(_f("violation", f"нет отвода для прибора {f['tip_a1']}"))
        elif d_fact < d_min:
            findings.append(_f(
                "violation",
                f"отвод {f['tip_a1']} Ду{d_fact} меньше минимального {d_min} мм "
                f"(СП 30.13330.2020, табл. А.1)",
            ))
        else:
            findings.append(_f(
                "ok",
                f"отвод {f['tip_a1']} Ду{d_fact} ≥ {d_min} мм (СП 30.13330.2020, табл. А.1)",
            ))
        if d_fact and d_fact > collector:
            findings.append(_f(
                "violation",
                f"диаметр отвода {f['tip_a1']} Ду{d_fact} больше сборного Ду{collector} — "
                f"диаметр не должен убывать по потоку (СП 30.13330.2020, п. 18.34 по аналогии)",
            ))
    return findings


def check_water(segments: list[dict], flow: dict, sized: dict,
                passport: dict, system: str) -> list[Finding]:
    """Скорость и диаметры В1/Т3 — СП 30.13330.2020, прил. И / п. 8.26, табл. А.1."""
    findings = []
    if sized["v_m_s"] <= V_MAX_M_S:
        findings.append(_f(
            "ok",
            f"{system}: расход {flow['q_l_s']} л/с, Ду{sized['dn']}, скорость {sized['v_m_s']} м/с "
            f"≤ {V_MAX_M_S} м/с (СП 30.13330.2020, прил. И / п. 8.26)",
        ))
    else:
        findings.append(_f(
            "violation",
            f"{system}: скорость {sized['v_m_s']} м/с выше {V_MAX_M_S} м/с "
            f"(СП 30.13330.2020, прил. И / п. 8.26)",
        ))
    a1 = load_rule("rashody_priborov")["fixtures"]
    key = system.lower()
    podvodki = [s for s in segments if s["naznachenie"].startswith(("опуск", "ответвление"))]
    for f in passport["pribory"]:
        if key not in f["connectors"]:
            continue
        d_min = a1[f["tip_a1"]]["d_podvodki"]
        segs = [s for s in podvodki if f["tip_a1"] in s["naznachenie"]]
        if not segs:
            continue
        d_fact = min(s["dia_mm"] for s in segs)
        if d_min and d_fact < d_min:
            findings.append(_f(
                "violation",
                f"{system}: подводка {f['tip_a1']} Ду{d_fact} меньше минимальной {d_min} мм "
                f"(СП 30.13330.2020, табл. А.1)",
            ))
        elif d_min:
            findings.append(_f(
                "ok",
                f"{system}: подводка {f['tip_a1']} Ду{d_fact} ≥ {d_min} мм "
                f"(СП 30.13330.2020, табл. А.1)",
            ))
        else:
            findings.append(_f(
                "ok",
                f"{system}: подводка {f['tip_a1']} Ду{d_fact} — табл. А.1 не нормирует («–»), "
                f"принята по скорости (СП 30.13330.2020, п. 8.26)",
            ))
    return findings


def check_stack(stack_result: dict) -> list[Finding]:
    """Стояк К1: расход против пропускной способности — прил. К, п. 19.2."""
    dn = f" Ду{stack_result['dn']:g}" if "dn" in stack_result else ""
    if stack_result["ok"]:
        return [_f(
            "ok",
            f"стояк К1{dn}: qs = {stack_result['qs_l_s']} л/с ≤ пропускной способности "
            f"{stack_result['capacity_l_s']} л/с (СП 30.13330.2020, прил. К, табл. К.1; ф. (5) п. 5.5)",
        )]
    return [_f(
        "violation",
        f"стояк К1{dn}: qs = {stack_result['qs_l_s']} л/с выше пропускной способности "
        f"{stack_result['capacity_l_s']} л/с — увеличить диаметр стояка или рассредоточить "
        f"расход (СП 30.13330.2020, п. 19.2)",
    )]


# --- Чек-лист v1 (эксперимент 03) ---


def check_otvod_vs_vypusk(segments: list[dict], passport: dict) -> list[Finding]:
    """Отводной трубопровод прибора не уже его выпуска (коннектора К1).

    Прямого пункта в СП 30 нет; конструктивное требование по аналогии с п. 18.34
    (диаметр не должен уменьшаться по потоку). Ловит случай эксперимента 02:
    трап с выпуском 102 мм против отвода Ду50 по табл. А.1.
    """
    findings = []
    for f in passport["pribory"]:
        vypusk = f["connectors"].get("k1", {}).get("dia_mm")
        if not vypusk:
            continue
        segs = [s for s in segments if f["tip_a1"] in s["naznachenie"]]
        if not segs:
            continue
        d_fact = min(s["dia_mm"] for s in segs)
        if d_fact < vypusk:
            findings.append(_f(
                "violation",
                f"отвод {f['tip_a1']} Ду{d_fact} уже выпуска прибора {vypusk} мм — сужение "
                f"по потоку недопустимо (по аналогии с СП 30.13330.2020, п. 18.34)",
            ))
        else:
            findings.append(_f(
                "ok",
                f"отвод {f['tip_a1']} Ду{d_fact} ≥ выпуска прибора {vypusk} мм "
                f"(по аналогии с СП 30.13330.2020, п. 18.34)",
            ))
    return findings


def check_fixture_heights(passport: dict, floor_z_mm: float) -> list[Finding]:
    """Высоты водоразборной арматуры от чистого пола — СП 73.13330.2016, п. 6.2.1.

    Проверяются только нормированные высоты (смывной кран унитаза — 800 мм ± допуск);
    конструктивные высоты остальных подводок — info.
    """
    rule = load_rule("vysoty_ustanovki_priborov", doc="sp73")["armatura"]
    dopusk = float(rule["dopusk_mm"])
    h_kran = float(rule["ot_chistogo_pola_mm"]["smyvnye_krany_unitazov"])
    findings = []
    konstruktivnye = 0
    for f in passport["pribory"]:
        v1 = f["connectors"].get("v1")
        if not v1:
            continue
        h = float(v1["z"]) - floor_z_mm
        if f["tip_a1"] == "unitaz_kran":
            if abs(h - h_kran) <= dopusk:
                findings.append(_f(
                    "ok",
                    f"смывной кран {f['tip_a1']} на {h:g} мм от пола = {h_kran:g} ± {dopusk:g} мм "
                    f"(СП 73.13330.2016, п. 6.2.1)",
                ))
            else:
                findings.append(_f(
                    "violation",
                    f"смывной кран {f['tip_a1']} на {h:g} мм от пола вне {h_kran:g} ± {dopusk:g} мм "
                    f"(СП 73.13330.2016, п. 6.2.1)",
                ))
        else:
            konstruktivnye += 1
    if konstruktivnye:
        findings.append(_f(
            "info",
            f"высоты подводок {konstruktivnye} приборов конструктивные (600 мм под бортом) — "
            f"СП 73.13330.2016, п. 6.2.1 их не нормирует; борта приборов в АР-модели не проверялись",
        ))
    return findings


def check_required_head(q_l_s: float, main_dn: float, dlina_m: float, h_geom_m: float,
                        garantirovanny_m: float | None = None) -> list[Finding]:
    """Требуемый напор Hтр по формуле (14) — СП 30.13330.2020, п. 8.27.

    Потери по ф. (15) с i по Дарси–Вейсбаху (calc.sp30.pressure.unit_loss_darcy,
    инженерное приближение v0). Если гарантированный напор сети не задан —
    info с расчётным Hтр (сравнение выполняет инженер).
    """
    from calc.sp30 import pressure

    i = pressure.unit_loss_darcy(q_l_s, main_dn)
    losses = pressure.pipe_section_loss(i, dlina_m)
    htr = pressure.required_head(h_geom_m, losses)
    opisanie = (
        f"Hтр = {htr:.1f} м (Hgeom {h_geom_m:.1f} + потери {losses:.1f} по ф. (15), "
        f"i = {i:.4f} м/м Дарси–Вейсбах, + Hпр {pressure.min_free_head_upper_fixture():g} м "
        f"по п. 8.21) — СП 30.13330.2020, п. 8.27, формула (14)"
    )
    if garantirovanny_m is None:
        return [_f("info", opisanie + "; гарантированный напор сети не задан — сравнение "
                                      "с Hтр выполняет инженер (⚠️ задание инженера)")]
    if htr <= garantirovanny_m:
        return [_f("ok", opisanie + f"; ≤ гарантированного {garantirovanny_m:g} м")]
    return [_f("violation", opisanie + f"; выше гарантированного {garantirovanny_m:g} м — "
                                       f"нужна повысительная насосная установка (п. 8.27)")]


def render_report(all_findings: list[Finding]) -> str:
    """Текстовый отчёт нормоконтроля: сначала нарушения, затем пройденные проверки."""
    violations = [f for f in all_findings if f["status"] == "violation"]
    oks = [f for f in all_findings if f["status"] == "ok"]
    infos = [f for f in all_findings if f["status"] == "info"]
    lines = [f"Нормоконтроль: {len(violations)} нарушений, {len(oks)} проверок пройдено", ""]
    for f in violations:
        lines.append(f"❌ {f['text']}")
    for f in infos:
        lines.append(f"ℹ️ {f['text']}")
    for f in oks:
        lines.append(f"✅ {f['text']}")
    return "\n".join(lines)
