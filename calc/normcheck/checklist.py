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
        else:
            findings.append(_f(
                "ok",
                f"{system}: подводка {f['tip_a1']} Ду{d_fact} ≥ {d_min} мм "
                f"(СП 30.13330.2020, табл. А.1)",
            ))
    return findings


def check_stack(stack_result: dict) -> list[Finding]:
    """Стояк К1: расход против пропускной способности — прил. К, п. 19.2."""
    if stack_result["ok"]:
        return [_f(
            "ok",
            f"стояк К1: qs = {stack_result['qs_l_s']} л/с ≤ пропускной способности "
            f"{stack_result['capacity_l_s']} л/с (СП 30.13330.2020, прил. К, табл. К.1; ф. (5) п. 5.5)",
        )]
    return [_f(
        "violation",
        f"стояк К1: qs = {stack_result['qs_l_s']} л/с выше пропускной способности "
        f"{stack_result['capacity_l_s']} л/с — увеличить диаметр стояка или рассредоточить "
        f"расход (СП 30.13330.2020, п. 19.2)",
    )]


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
