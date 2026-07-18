# Сквозной прогон ВК этажа L1 (эксперимент 03): паспорт (6 кластеров) -> гидравлика ->
# трассы -> чек-лист v1. Запуск из корня репо:
#   uv run python experiments/03-vk-etazh-l1/run_pipeline.py
# Выход: отчёт в stdout + segments.json (вход для создания труб в Revit через MCP).
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from calc.normcheck import checklist
from calc.sp30.rules_loader import load_rule
from calc.trace import router, sizing

HERE = Path(__file__).parent
passport = json.loads((HERE / "passport.json").read_text(encoding="utf-8"))
a1 = load_rule("rashody_priborov")["fixtures"]

Z_MAG_MM = 2700.0  # магистрали/верх стояков над полом (допущение паспорта)

all_segments: list[dict] = []
all_findings: list[dict] = []
itogi = []

for cl in passport["klastery"]:
    floor_z = cl["uroven"]["otmetka_mm"]
    axis = cl["axis"]
    z = cl["zadanie_inzhenera"]
    keys = [f["tip_a1"] for f in cl["pribory"]]

    # --- Гидравлика v0.1 (расчётчик) ---
    flows, sized = {}, {}
    for kind in ("tot", "c", "h"):
        try:
            flows[kind] = sizing.bathroom_flow(keys, z["U_potrebiteley"], z["q_hr_u_l"], kind)
            sized[kind] = sizing.pick_water_diameter(flows[kind]["q_l_s"])
        except ValueError:  # в кластере нет приборов с этим видом расхода
            flows[kind], sized[kind] = None, None
    stack = sizing.pick_k1_stack(cl, flows["tot"]["q_l_s"])
    podvodki = {}
    for kind, q0_key in (("c", "q0_c"), ("h", "q0_h")):
        podvodki[kind] = {
            t: sizing.pick_podvodka(a1[t][q0_key], a1[t]["d_podvodki"])
            for t in set(keys) if a1[t][q0_key]
        }

    # --- Трассировка v0.1 (компоновщик) ---
    segs = router.route_k1(cl, slope=0.02,
                           z_collector_stack=cl["stoyak_k1"]["z_kollektora"], axis=axis)
    segs += router.route_k1_stack(cl, stack["dn"], z_verh=floor_z + Z_MAG_MM)
    segs_v1 = router.route_water(cl, "v1", main_dn=sized["c"]["dn"],
                                 podvodka_dn=podvodki["c"], axis=axis)
    segs_t3 = []
    if any("t3" in f["connectors"] for f in cl["pribory"]):
        segs_t3 = router.route_water(cl, "t3", main_dn=sized["h"]["dn"],
                                     podvodka_dn=podvodki["h"], axis=axis)

    # --- Нормоконтроль: чек-лист v0 + v1 ---
    findings = []
    findings += checklist.check_k1(segs)
    findings += checklist.check_k1_diameters([s for s in segs if s["system"] == "K1"], cl)
    findings += checklist.check_otvod_vs_vypusk(segs, cl)
    findings += checklist.check_water(segs_v1, flows["c"], sized["c"], cl, "V1")
    if segs_t3:
        findings += checklist.check_water(segs_t3, flows["h"], sized["h"], cl, "T3")
    findings += checklist.check_stack(stack)
    findings += checklist.check_fixture_heights(cl, floor_z)

    for f in findings:
        f["klaster"] = cl["id"]
    all_findings += findings
    for s in segs + segs_v1 + segs_t3:
        s["klaster"] = cl["id"]
    all_segments += segs + segs_v1 + segs_t3
    itogi.append({
        "klaster": cl["id"], "flows": flows, "sized": sized, "stack": stack,
        "podvodki": podvodki,
        "segmentov": len(segs) + len(segs_v1) + len(segs_t3),
    })

# --- Hтр по ф. (14) для диктующего кластера (верхний пол — wc_b43) ---
vvod = passport["vvod"]
dikt = max(passport["klastery"], key=lambda c: c["uroven"]["otmetka_mm"])
it = next(i for i in itogi if i["klaster"] == dikt["id"])
verh_z = max(f["connectors"]["v1"]["z"] for f in dikt["pribory"] if "v1" in f["connectors"])
h_geom = (verh_z - vvod["z_mm"]) / 1000.0
# расчётное направление v0: вертикаль шахты от ввода + дальний луч магистрали + опуск
luchi = [s for s in all_segments
         if s["klaster"] == dikt["id"] and s["naznachenie"].startswith("магистраль")]
dl_lucha = max(math.dist(s["start"], s["end"]) for s in luchi) / 1000.0
dlina = (dikt["tochka_podkl_voda"]["z_mag"] - vvod["z_mm"]) / 1000.0 + dl_lucha + Z_MAG_MM / 1000.0
htr_findings = checklist.check_required_head(
    it["flows"]["c"]["q_l_s"], it["sized"]["c"]["dn"], dlina, h_geom,
    vvod["garantirovanny_napor_m"],
)
for f in htr_findings:
    f["klaster"] = dikt["id"]
all_findings += htr_findings

report = checklist.render_report(all_findings)
result = {
    "itogi": itogi,
    "segments": all_segments,
    "violations": len([f for f in all_findings if f["status"] == "violation"]),
}
(HERE / "segments.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
)

print("=== Гидравлика и стояки по кластерам ===")
for it in itogi:
    fc, fh, st = it["flows"]["c"], it["flows"]["h"], it["stack"]
    t3 = f", Т3 {fh['q_l_s']} л/с -> Ду{it['sized']['h']['dn']}" if fh else ""
    print(f"{it['klaster']}: В1 {fc['q_l_s']} л/с -> Ду{it['sized']['c']['dn']}{t3}; "
          f"стояк К1 Ду{st['dn']:g} (qs={st['qs_l_s']} ≤ {st['capacity_l_s']} л/с); "
          f"сегментов {it['segmentov']}")
print(f"\nВсего сегментов: {len(all_segments)}")
print("\n" + report)
