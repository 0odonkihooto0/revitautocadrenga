# Сквозной прогон MVP санузла (эксперимент 02): паспорт -> гидравлика -> трассы ->
# нормоконтроль. Запуск из корня репо: uv run python experiments/02-mvp-sanuzel/run_pipeline.py
# Выход: отчёт в stdout + segments.json рядом (вход для создания труб в Revit через MCP).
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from calc.normcheck import checklist
from calc.trace import router, sizing

HERE = Path(__file__).parent
passport = json.loads((HERE / "passport.json").read_text(encoding="utf-8"))
keys = [f["tip_a1"] for f in passport["pribory"]]
z = passport["zadanie_inzhenera"]

# --- Гидравлика v0 (расчётчик) ---
flows, sized = {}, {}
for kind, label in (("tot", "общий"), ("c", "В1"), ("h", "Т3")):
    flows[kind] = sizing.bathroom_flow(keys, z["U_zhiteley"], z["q_hr_u_l"], kind)
    sized[kind] = sizing.pick_water_diameter(flows[kind]["q_l_s"])
stack = sizing.check_k1_stack(passport, flows["tot"]["q_l_s"])

# --- Трассировка v0 (компоновщик) ---
segs_k1 = router.route_k1(passport, slope=0.02)
segs_v1 = router.route_water(passport, "v1", main_dn=sized["c"]["dn"])
segs_t3 = router.route_water(passport, "t3", main_dn=sized["h"]["dn"])

# --- Нормоконтроль v0 ---
findings = []
findings += checklist.check_k1(segs_k1)
findings += checklist.check_k1_diameters(segs_k1, passport)
findings += checklist.check_water(segs_v1, flows["c"], sized["c"], passport, "V1")
findings += checklist.check_water(segs_t3, flows["h"], sized["h"], passport, "T3")
findings += checklist.check_stack(stack)
findings.append({"status": "info", "text": (
    "высоты установки приборов (СП 73.13330.2016, табл. 3) не проверялись: в модели "
    "семейства-подключения без геометрии бортов"
)})

report = checklist.render_report(findings)
result = {
    "flows": flows, "sized": sized, "stack": stack,
    "segments": segs_k1 + segs_v1 + segs_t3,
    "violations": len([f for f in findings if f["status"] == "violation"]),
}
(HERE / "segments.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
)

print("=== Гидравлика ===")
for kind, label in (("tot", "общий"), ("c", "В1 (холодная)"), ("h", "Т3 (горячая)")):
    f, s = flows[kind], sized[kind]
    print(f"{label}: q0={f['q0']} л/с, N={f['n']}, P={f['p']} -> q={f['q_l_s']} л/с; "
          f"Ду{s['dn']}, v={s['v_m_s']} м/с")
print(f"стояк К1: qs={stack['qs_l_s']} л/с, пропускная {stack['capacity_l_s']} л/с, "
      f"{'OK' if stack['ok'] else 'ПРЕВЫШЕНИЕ'}")
print(f"\n=== Трассы === К1: {len(segs_k1)} сегм., В1: {len(segs_v1)}, Т3: {len(segs_t3)}")
print("\n" + report)
