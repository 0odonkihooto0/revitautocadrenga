# Генератор полезной нагрузки для создания труб в Revit (эксперимент 03).
# Читает segments.json, мапит Ду СП -> имперский размер каталога модели, кластер ->
# уровень блока; пишет revit_payload.json: {klaster: {level_id, pipes: [[sys_id, size_mm,
# x1,y1,z1,x2,y2,z2], ...]}}. Трубы создаёт MCP execute_revit_code одной транзакцией
# на кластер (см. docs/lessons.md про транзакции эндпоинта).
import json
from pathlib import Path

HERE = Path(__file__).parent

# id систем и типа труб АР-модели (inventory.json)
SYSTEM_IDS = {"K1": 159911, "V1": 159913, "T3": 159912}
# Ду по СП -> ближайший размер имперского каталога сегментов модели, мм
SIZE_MAP = {15: 12.7, 20: 19.1, 25: 25.4, 32: 31.8, 40: 38.1,
            50: 50.8, 65: 63.5, 80: 76.2, 100: 101.6, 110: 101.6}
LEVEL_IDS = {"L1 - Block 35": 593176, "L1 - Block 37": 633454, "L1 - Block 43": 593142}

segments = json.loads((HERE / "segments.json").read_text(encoding="utf-8"))["segments"]
passport = json.loads((HERE / "passport.json").read_text(encoding="utf-8"))
level_by_cluster = {c["id"]: LEVEL_IDS[c["uroven"]["name"]] for c in passport["klastery"]}

payload: dict[str, dict] = {}
for s in segments:
    cl = s["klaster"]
    entry = payload.setdefault(cl, {"level_id": level_by_cluster[cl], "pipes": []})
    entry["pipes"].append([
        SYSTEM_IDS[s["system"]], SIZE_MAP[int(s["dia_mm"])],
        round(s["start"][0], 1), round(s["start"][1], 1), round(s["start"][2], 1),
        round(s["end"][0], 1), round(s["end"][1], 1), round(s["end"][2], 1),
    ])

(HERE / "revit_payload.json").write_text(
    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
)
for cl, e in payload.items():
    print(f"{cl}: {len(e['pipes'])} труб, уровень {e['level_id']}")
