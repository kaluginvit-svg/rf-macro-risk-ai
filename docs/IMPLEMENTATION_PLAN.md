# План развития локального анализатора

Цель: сделать анализатор не просто LLM-агентом с поиском, а системой мониторинга свежих сигналов по критериям. Код должен гарантировать свежесть, уникальность и правила источников; модель должна заниматься интерпретацией уже очищенной выборки.

## 1. Схема критериев

Добавить к каждому критерию машиночитаемые поля:

- `source_group`: `official_event`, `official_stats`, `market_data`, `news_event`, `weak_noisy`.
- `source_policy.primary_domains`: предпочтительные официальные или первичные домены.
- `source_policy.secondary_domains`: допустимые подтверждающие источники.
- `source_policy.requires_official`: можно ли сработать без официального источника.
- `source_policy.min_independent_sources`: сколько независимых доменов нужно, если official нет.
- `source_policy.allow_reuse_official`: можно ли использовать официальный URL повторно при новых данных.
- `source_policy.allow_undated_non_official`: можно ли отдавать модели материал СМИ без даты.
- `freshness.window_days`: основное окно свежести.
- `freshness.fallback_window_days`: запасное окно для slow/statistical критериев.

## 2. Research ledger

Создать локальный `research_ledger.json`, игнорируемый git. Он хранит:

- canonical URL и original URL;
- domain;
- published date;
- first seen / last seen;
- used runs;
- related criteria;
- title/snippet hash;
- status: `used`, `rejected_old`, `rejected_duplicate`, `background`;
- official/non-official.

## 3. Source registry

Вынести работу с источниками в `src/source_registry.py`:

- canonicalize URL;
- strip tracking params;
- classify official domains;
- parse dates;
- map `time_range` to max age;
- filter old, undated and duplicate results;
- persist ledger.

## 4. Retrieval layer

Текущий `WebSearch(query)` должен стать контролируемым retrieval layer:

1. Tavily raw results.
2. Canonical URL normalization.
3. Freshness filter.
4. Ledger dedup.
5. Official reuse policy.
6. Compact output to LLM.

Следующий шаг после этого: добавить отдельный tool `SearchCriterion(criterion_id)`, чтобы код сам выбирал `search_query`, `speed` и `source_policy`.

## 5. Evidence policy

Для срабатывания критерия:

- `official_event`: официальный источник или явное подтверждение официального решения.
- `official_stats`: статистический/регуляторный источник, СМИ только как пересказ.
- `market_data`: источник с датой данных.
- `news_event`: минимум 2 независимых домена, если нет official.
- `weak_noisy`: максимум `watch`, пока нет сильного подтверждения.

## 6. Пульс критериев

Добавить к итоговому JSON:

```json
"criteria_status": [
  {
    "id": "corporate_default_wave",
    "status": "watch",
    "delta": "worse",
    "fresh_signals_count": 3,
    "new_sources_count": 5,
    "evidence_strength": "medium"
  }
]
```

Статусы: `quiet`, `watch`, `warming_up`, `triggered`, `cooling_down`.

## 7. Кодовая валидация результата

После ответа модели код должен:

- пересчитать `total_score`;
- выставить `risk_level` по thresholds;
- проверить `checked_criteria`;
- проверить freshness/dedup sources;
- проверить ссылки `[N]`;
- по возможности исправить результат или запросить короткую финализацию.

## 8. Что взять из upstream

Из `Rai220/money_alert_ai` стоит взять идеи, но не возвращать старую архитектуру:

- dedup `asset_guidance` по архиву канала;
- Telegram-safe formatting contract: HTML escaping, linkify `[N]`, лимит 4096, expandable blockquote;
- admin notification pattern, но реализовывать его в соседнем `Бот_репортер`;
- архив канала как anti-repeat context, не как доказательную базу.

Не возвращать в этот репозиторий:

- прямую отправку Telegram;
- `python-telegram-bot` dependency;
- активный Modal runtime;
- подсчет score силами LLM без валидации.

## 9. Modal как dormant option

Modal оставить только как будущую неактивную опцию:

- документировать в `docs/MODAL_OPTION.md`;
- не добавлять `modal` в зависимости основного проекта;
- не добавлять активный `src/modal_app.py`, пока не принято решение о деплое;
- при необходимости использовать upstream `modal_app.py` как reference для отдельного deployment layer.

## 10. Порядок внедрения

1. Source registry + ledger.
2. Freshness/dedup filter в `WebSearch`.
3. Документация reporter contract и Modal option.
4. JSON validator.
5. `source_group/source_policy` в критериях.
6. `criteria_status` и pulse score.
7. `SearchCriterion(criterion_id)`.
8. Обновление web report и reporter contract.

## 11. Статус внедрения

Реализовано в текущей локальной версии:

- `source_group`, `source_policy`, `freshness` добавлены в `criteria.json` и `criteria_small.json`;
- добавлен `src/source_registry.py`;
- добавлен `research_ledger.json` как локальная память источников;
- Tavily-результаты фильтруются по свежести, дублям, canonical URL и отсутствию даты у неофициальных источников;
- добавлен tool `SearchCriterion(criterion_id)`;
- финальный JSON нормализуется кодом: `checked_criteria`, `triggered_criteria`, `total_score`, `risk_level`, `criteria_status`, `pulse_score`;
- финальные `sources` принимаются только из URL, реально найденных текущими search tools;
- Modal описан как dormant option без зависимости и активного runtime.

Следующий этап:

- заменить свободные групповые поиски на планировщик `SearchCriterion` по группам критериев;
- добавить строгую проверку `min_independent_sources`;
- обновить UI `docs/index.html` под `criteria_status` и `pulse_score`;
- согласовать schema v2 с соседним `Бот_репортер`.
