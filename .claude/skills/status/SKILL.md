---
description: Сверить docs/status.md с реальным состоянием репозитория и обновить его
disable-model-invocation: true
---

## Текущий статус (docs/status.md)

!`cat docs/status.md 2>/dev/null || cat /home/user/revitautocadrenga/docs/status.md`

## Последние коммиты

!`git log --oneline -15`

## Незакоммиченные изменения

!`git status --short`

## Инструкции

Сверь docs/status.md с реальностью (коммиты, состояние файлов, работа в этой сессии):

1. Обнови разделы «Где мы», чек-лист и «Заметки для следующей сессии»; поставь
   сегодняшнюю дату в «Обновлено».
2. Пиши кратко: status.md импортируется в каждую сессию, держи его до ~40 строк;
   подробности уходят в decisions.md / lessons.md / experiments/.
3. Если за сессию появились решения или уроки — предложи записи для docs/decisions.md
   и docs/lessons.md.
