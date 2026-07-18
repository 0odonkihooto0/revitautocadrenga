# Эксперимент 00: Связка Claude ↔ Revit через MCP (revit-mcp-server)

**Дата:** 2026-07-18
**Статус:** завершён
**Этап плана:** этап 0 — проба связки Claude ↔ САПР

## Цель

Проверить, что Claude Code может читать и изменять модель Revit через MCP-сервер
(pyRevit Routes API): получить данные учебной модели и создать первый элемент (трубу).

## Окружение

| Компонент | Версия / детали |
|---|---|
| ОС | Windows 11 Pro 10.0.26200 |
| Revit | 2026.4 (сборка 20251103_1515) |
| pyRevit | 6.5.3.26176+2017, установка PerUser, движок IronPython 2712 |
| MCP-сервер | Demolinator/revit-mcp-server (48 инструментов), mcp==1.9.0 |
| Python / uv | CPython 3.13.0, uv 0.7.15 |
| Модель | Snowdon Towers Sample Plumbing.rvt (копия в C:\revitTools\models\) |

## Ход эксперимента

1. Установлен pyRevit 6.5.3 (тихая установка `/VERYSILENT`), привязка к Revit 2026
   подтверждена через `pyrevit env`.
2. Склонирован revit-mcp-server в `C:\revitTools\revit-mcp-server`, `uv sync` — 28 пакетов.
3. Расширение скопировано в `%APPDATA%\pyRevit\Extensions\mcp-server-for-revit-python.extension`.
4. Routes Server включён без GUI: `pyrevit configs routes enable` + `routes port 48884`.
5. **Грабли 1:** расширение не загрузилось — в его extension.json стоит
   `default_enabled: False`. Лечится явной записью в pyRevit_config.ini:
   `pyrevit configs "mcp-server-for-revit-python.extension:disabled" disable`.
6. **Грабли 2:** запросы к `localhost:48884` перехватывал локальный Privoxy от
   Autodesk Genuine Service (127.0.0.1:8118) — см. docs/lessons.md. Обход: `NO_PROXY`.
7. MCP-сервер зарегистрирован: `claude mcp add revit --env NO_PROXY=localhost,127.0.0.1
   -- uv run --directory C:\revitTools\revit-mcp-server main.py` — health-check Connected.
8. Прогон пяти команд MCP-клиентом (stdio, скрипт на mcp SDK) — все успешны.

## Результат

Все 5 команд прошли, полная цепочка «MCP-клиент → MCP-сервер → pyRevit Routes →
Revit API» работает на чтение и запись:

| # | Команда | Результат |
|---|---|---|
| 1 | `get_revit_status` | active / healthy, документ Snowdon Towers Sample Plumbing |
| 2 | `get_revit_model_info` | 179 санприборов, 3052 трубы, 27 листов, 128 видов, 11 уровней |
| 3 | `list_levels` | 11 уровней с отметками в мм (Parking −5156 … R2 +17932) |
| 4 | `ai_element_filter` | категория OST_PlumbingFixtures → 179 элементов |
| 5 | `create_pipe` | труба создана на уровне L2: (0,0,3000)→(3000,0,3000) мм |

Проверка записи: повторный `ai_filter` по bounding box вокруг координат нашёл ровно
один элемент — труба id 1738982, уровень L2, тип PVC - DWV. Создание подтверждено.

## Выводы

1. Связка Claude ↔ Revit работает «из коробки»: 48 инструментов, координаты в мм,
   чтение и создание элементов — этап 0 пройден за одну сессию.
2. Главные препятствия оказались инфраструктурными (прокси Autodesk, флаг
   default_enabled расширения), а не в самом MCP — оба задокументированы в
   docs/lessons.md.
3. Учебная модель Snowdon Towers Plumbing богата содержимым (179 санприборов,
   3052 трубы) — хороша для следующих проб: фильтры по этажам, свойства элементов,
   clash detection.

Следующий шаг: перезапустить сессию Claude Code (инструменты MCP появятся прямо в
сессии), попробовать сценарий «найди санузлы и перечисли приборы по этажу» и команды
изменения параметров; параллельно — конспект СП 30.13330.2020 (этап 1).
