# Аналитик v0.1 (эксперимент 03): сборка паспорта этажа L1 из инвентаризации АР-модели.
# Запуск из корня репо: uv run python experiments/03-vk-etazh-l1/build_passport.py
# Вход — inventory.json (сырьё из Revit MCP), выход — passport.json (кластеры санузлов
# с синтезированными по нормам коннекторами — calc/trace/connectors.py).
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from calc.trace.connectors import synthesize_connectors

HERE = Path(__file__).parent

# Маппинг АР-семейств на приборы табл. А.1 СП 30 (решение аналитика; спорное — в паспорт)
FAMILY_TIP = {
    "Toilet-Commercial-Wall-3D": "unitaz_kran",   # подвесной коммерческий: смывной кран
    "Sink-Wall-Barrier Free-3D": "umyvalnik_smesitel",
    "Floor Drain-2D": "trap_du50",
    "Sink-3 Basin": "moyka_obshchepit",
    "Sink-Produce": "moyka_obshchepit",
    "Hand Sink": "umyvalnik_smesitel",
    "Mop Sink_Rect": "rakovina_kran",             # мойка инвентарная с водоразборным краном
    "Plumb_Floor Sink": "trap_du100",
}
# Водоразборная арматура моек — отдельными приборами не считается (учтена мойками)
ARMATURA = {"Mop Sink Faucet", "Faucet_Combo", "Faucet_Swing"}

# Кластеры-санузлы: регион в плане, отметка пола, ось стены и позиция стояка/шахты.
# Позиции стояков — допущение аналитика (у стены-хоста или в шахтной стене Chase),
# подлежат подтверждению инженером.
CLUSTERS = [
    {
        "id": "wc_b35", "opisanie": "санузлы Block 35 (2 WC + 2 умывальника + 2 трапа)",
        "region": {"x": [-20500, -18000], "y": [6000, 11500]},
        "uroven": {"name": "L1 - Block 35", "otmetka_mm": -1803.4},
        "axis": "y", "stena": {"revit_id": 737373, "os_x": -19888.2, "width_mm": 184.2},
        "stoyak": {"x": -19696.1, "y": 8574.0},
    },
    {
        "id": "wc_b37_sever", "opisanie": "санузлы Block 37 северные (шахта Chase)",
        "region": {"x": [-12500, -10500], "y": [5500, 11200]},
        "uroven": {"name": "L1 - Block 37", "otmetka_mm": -1054.1},
        "axis": "y", "stena": {"revit_id": 1300721, "os_x": -11961.8, "width_mm": 79.4},
        "stoyak": {"x": -12101.5, "y": 8598.0},  # в шахте за стеной Chase
    },
    {
        "id": "wc_b37_yug", "opisanie": "санузлы Block 37 южные",
        "region": {"x": [-6700, -4500], "y": [1000, 5700]},
        "uroven": {"name": "L1 - Block 37", "otmetka_mm": -1054.1},
        "axis": "y", "stena": {"revit_id": 676300, "os_x": -6172.2, "width_mm": 298.5},
        "stoyak": {"x": -5923.0, "y": 3377.0},
    },
    {
        "id": "wc_b37_vostok", "opisanie": "санузлы Block 37 восточные (у наружной стены)",
        "region": {"x": [7500, 12600], "y": [11000, 13500]},
        "uroven": {"name": "L1 - Block 37", "otmetka_mm": -1054.1},
        "axis": "x", "stena": {"revit_id": 678361, "os_y": 12869.9, "width_mm": 320.7},
        "stoyak": {"x": 12350.0, "y": 12609.6},
    },
    {
        "id": "wc_b43", "opisanie": "санузлы Block 43 (шахта Chase)",
        "region": {"x": [12500, 14500], "y": [7900, 12900]},
        "uroven": {"name": "L1 - Block 43", "otmetka_mm": 0.0},
        "axis": "y", "stena": {"revit_id": 1391115, "os_x": 12827.0, "width_mm": 108.0},
        "stoyak": {"x": 12673.0, "y": 10403.0},  # в шахте за стеной Chase
    },
    {
        "id": "kuhnya_b35", "opisanie": "производственная кухня Block 35 (мойки + напольные трапы)",
        "region": {"x": [-31000, -21000], "y": [9500, 13500]},
        "uroven": {"name": "L1 - Block 35", "otmetka_mm": -1803.4},
        "axis": "x", "stena": {"revit_id": 697710, "os_y": 12869.9, "width_mm": 320.7},
        "stoyak": {"x": -30097.5, "y": 12609.6},  # у западной стены 1304482
    },
]

Z_KOLLEKTOR_NIZHE_POLA_MM = 400.0   # лоток сборного К1 у стояка ниже чистого пола (допущение)
Z_MAGISTRAL_NAD_POLOM_MM = 2700.0   # магистрали В1/Т3 под потолком (допущение, как в эксп. 02)

inv = json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))


def v_regione(f: dict, region: dict) -> bool:
    x, y = f["xyz_mm"][0], f["xyz_mm"][1]
    return region["x"][0] <= x <= region["x"][1] and region["y"][0] <= y <= region["y"][1]


passport = {
    "obekt": inv["obekt"],
    "sozdano": "2026-07-18, аналитик v0.1: кластеризация приборов АР-модели, коннекторы "
               "синтезированы по нормам (calc/trace/connectors.py) — у АР-семейств нет MEP-коннекторов",
    "koordinaty": inv["koordinaty"],
    "pipe_type": inv["pipe_type_default"],
    "sistemy": inv["sistemy"],
    "dopushcheniya": [
        "⚠️ Toilet-Commercial-Wall принят унитазом со смывным краном (табл. А.1 поз. 17) — "
        "подтвердить тип смыва инженеру",
        "⚠️ позиции стояков К1 и шахт В1/Т3 — допущение аналитика (у стены-хоста/в шахте Chase); "
        "подтвердить инженеру",
        "⚠️ трапы Floor Drain-2D в модели размещены с аномальными отметками (выше пола блока); "
        "приняты в уровне чистого пола своего кластера",
        "⚠️ высоты канализационных выпусков и подводок под бортом — конструктивные допущения "
        "(нормами не заданы), см. calc/trace/connectors.py",
        "⚠️ мойки общепита сливают в пол (разрыв струи в напольные трапы) — упрощение v0",
        "⚠️ U и q_hr_u — демонстрационные значения (табл. А.2 не оцифрована); задать инженеру",
        "водоразборная арматура (Mop Sink Faucet, Faucet_Combo, Faucet_Swing) отдельными "
        "приборами не считается — учтена расходами своих моек",
    ],
    "vvod": {
        "z_mm": -5156.0,
        "garantirovanny_napor_m": None,
        "kommentariy": "⚠️ отметка оси ввода принята по уровню Parking (-5156); "
                       "гарантированный напор городской сети — задание инженера",
    },
    "klastery": [],
}

ispolzovano = set()
for cl in CLUSTERS:
    floor_z = cl["uroven"]["otmetka_mm"]
    pribory = []
    for f in inv["fixtures"]:
        if f["family"] in ARMATURA or not v_regione(f, cl["region"]):
            continue
        tip = FAMILY_TIP[f["family"]]
        pribory.append({
            "revit_id": f["id"],
            "tip_a1": tip,
            "revit_name": "%s :: %s" % (f["family"], f["type"]),
            "connectors": synthesize_connectors(
                tip, f["xyz_mm"][0], f["xyz_mm"][1], floor_z, axis=cl["axis"]
            ),
        })
        ispolzovano.add(f["id"])
    passport["klastery"].append({
        "id": cl["id"],
        "opisanie": cl["opisanie"],
        "uroven": cl["uroven"],
        "axis": cl["axis"],
        "stena": cl["stena"],
        "stoyak_k1": {
            "x": cl["stoyak"]["x"], "y": cl["stoyak"]["y"],
            "z_kollektora": floor_z - Z_KOLLEKTOR_NIZHE_POLA_MM,
            "kommentariy": "⚠️ позиция — допущение аналитика",
        },
        "tochka_podkl_voda": {
            "x": cl["stoyak"]["x"], "y": cl["stoyak"]["y"],
            "z_mag": floor_z + Z_MAGISTRAL_NAD_POLOM_MM,
            "kommentariy": "⚠️ шахта В1/Т3 рядом со стояком К1, магистраль под потолком — допущение",
        },
        "zadanie_inzhenera": {"U_potrebiteley": 20, "q_hr_u_l": 15.6,
                              "kommentariy": "⚠️ демо-значения для формулы (3), табл. А.2 не оцифрована"},
        "pribory": pribory,
    })

propushcheno = [f["id"] for f in inv["fixtures"]
                if f["id"] not in ispolzovano and f["family"] not in ARMATURA]
if propushcheno:
    raise SystemExit(f"Приборы вне кластеров: {propushcheno}")

(HERE / "passport.json").write_text(
    json.dumps(passport, ensure_ascii=False, indent=1), encoding="utf-8"
)
n = sum(len(c["pribory"]) for c in passport["klastery"])
print(f"Паспорт собран: {len(passport['klastery'])} кластеров, {n} приборов "
      f"(+{sum(1 for f in inv['fixtures'] if f['family'] in ARMATURA)} ед. арматуры учтено мойками)")
for c in passport["klastery"]:
    tipy = {}
    for p in c["pribory"]:
        tipy[p["tip_a1"]] = tipy.get(p["tip_a1"], 0) + 1
    print(f"  {c['id']}: {tipy}")
