"""Напоры в системах внутреннего водоснабжения по СП 30.13330.2020, раздел 8.

Табличные значения — из rules/sp30/trebuemyi_napor.yaml и svobodnye_napory.yaml.
"""

from calc.sp30.rules_loader import load_rule


def min_free_head_upper_fixture() -> float:
    """Минимальный свободный напор у верхнего прибора, м вод. ст. — СП 30.13330.2020, п. 8.21."""
    return float(load_rule("svobodnye_napory")["svobodny_napor_verhnego_pribora"]["min_m"])


def max_hydrostatic_head_lower_fixture() -> float:
    """Максимальный гидростатический напор у нижнего прибора, м вод. ст. — п. 7.10."""
    return float(load_rule("svobodnye_napory")["gidrostatichesky_napor_nizhnego_pribora"]["max_m"])


def pipe_section_loss(i: float, length_m: float, network: str = "hoz_pitevoy_zhilyh_obshchestvennyh") -> float:
    """Потери напора на участке, м вод. ст. — СП 30.13330.2020, п. 8.28, формула (15).

    Hil = i·l·(1 + kl); i — удельные потери на 1 м, kl — коэффициент местных
    сопротивлений по типу сети (rules/sp30/trebuemyi_napor.yaml, koefficient_kl).
    """
    kl_values = load_rule("trebuemyi_napor")["koefficient_kl"]["values"]
    if network not in kl_values:
        raise ValueError(f"Тип сети «{network}»; доступны: {', '.join(kl_values)}")
    return i * length_m * (1.0 + float(kl_values[network]))


def required_head(
    h_geom: float,
    sum_pipe_losses: float,
    h_fixture: float | None = None,
    sum_meter_losses: float = 0.0,
    h_heater: float = 0.0,
    h_inlet: float = 0.0,
) -> float:
    """Требуемый напор Hтр, м вод. ст. — СП 30.13330.2020, п. 8.27, формула (14).

    Hтр = Hgeom + ΣHil + Hпр + ΣHвод + Hтепл + Hввод.
    h_fixture (Hпр) по умолчанию — минимальный свободный напор по п. 8.21 (20 м);
    h_heater (Hтепл) при наличии водонагревателя ориентировочно 3 м (п. 8.27).
    """
    if h_fixture is None:
        h_fixture = min_free_head_upper_fixture()
    return h_geom + sum_pipe_losses + h_fixture + sum_meter_losses + h_heater + h_inlet


def check_heads(head_at_upper_fixture: float, head_at_lower_fixture: float) -> list[str]:
    """Проверка свободного и гидростатического напоров — пп. 8.21, 7.10/8.22.

    Возвращает список нарушений с цитатами; пустой список — нормы соблюдены.
    """
    violations = []
    h_min = min_free_head_upper_fixture()
    h_max = max_hydrostatic_head_lower_fixture()
    if head_at_upper_fixture < h_min:
        violations.append(
            f"свободный напор у верхнего прибора {head_at_upper_fixture:.1f} м < {h_min:.1f} м "
            f"(СП 30.13330.2020, п. 8.21)"
        )
    if head_at_lower_fixture > h_max:
        violations.append(
            f"гидростатический напор у нижнего прибора {head_at_lower_fixture:.1f} м > {h_max:.1f} м — "
            f"нужны регуляторы давления или зонирование (СП 30.13330.2020, пп. 7.10, 8.22)"
        )
    return violations
