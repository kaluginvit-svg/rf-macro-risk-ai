# Агенты мониторинга макро-рисков РФ

## 1. LangChain агент (`src/lc_money_alert_bot.py`)

**Архитектура:** Один агент с инструментами

- Один агент (LangChain) с инструментами WebSearch/WebFetch
- Получает **все критерии сразу** в системном промпте
- **Сам планирует** порядок проверки
- Использует **WebSearch** для поиска новостей (Tavily)
- Может **группировать** похожие критерии

**Учёт расходов:**
- Выводит итоговую сумму в USD

**Формат вывода:**
```
📊 ИТОГОВЫЙ ОТЧЁТ
Уровень риска: 🟢 НИЗКИЙ
Очки: 0
✅ Сработавших критериев нет

📝 Резюме: ...
💡 Рекомендация: ...

💰 СТАТИСТИКА РАСХОДОВ
   Шагов агента: N
   Input токены: X
   Output токены: Y
   💵 ИТОГО: $Z.ZZZZ
```

**Запуск:**
```bash
uv run python src/lc_money_alert_bot.py                      # OpenAI (по умолчанию)
uv run python src/lc_money_alert_bot.py --provider gemini    # Gemini
uv run python src/lc_money_alert_bot.py --provider gigachat  # GigaChat
uv run python src/lc_money_alert_bot.py --provider anthropic # Anthropic (claude-opus-4-6)
```

⚠️ **Внимание:** Запуск занимает несколько минут и стоит денег (API вызовы).

---

## 2. Web export и выделенный бот-репортёр

Этот репозиторий отвечает за анализ: запускает LLM-агента, сохраняет историю и экспортирует web-данные. Публикация в Telegram вынесена в соседний выделенный проект бота-репортёра.

### Web export

Если задан `EXPORT_WEB_JSON`, после прогона агент:

- пишет свежий отчёт в указанный JSON, обычно `docs/data.json`;
- обновляет inline-данные в `docs/index.html`;
- пытается сделать `git add`, `git commit` и `git push`, чтобы обновить GitHub Pages.

```bash
EXPORT_WEB_JSON=docs/data.json uv run python src/lc_money_alert_bot.py --provider openai
```

### Telegram reporter

После успешного анализа `src/lc_money_alert_bot.py` может передать результат reporter-проекту. Если задан `BOT_REPORTER_DIR` и внутри есть `edit_post.py`, основной скрипт запустит его после анализа.

```bash
BOT_REPORTER_DIR=../Бот_репортер uv run python src/lc_money_alert_bot.py --provider openai
```

Расписание и Telegram-секреты находятся на стороне reporter-проекта, а не в этом репозитории.

### Modal

Modal остаётся неактивной будущей опцией. Не добавляйте `modal` в зависимости и не возвращайте активный `src/modal_app.py`, пока не принято отдельное архитектурное решение. Детали: `docs/MODAL_OPTION.md`.

---

## Критерии

Критерии загружаются из `criteria.json` (по умолчанию) или из файла, заданного в `CRITERIA_FILE`.

- `criteria.json`: **35 критериев** — макро-риски РФ (тенденции + риск кризисного сценария на 6 месяцев)
- `criteria_small.json`: **10 критериев** — сокращённый набор для дешёвых тестовых прогонов
- `archive/criteria_deposit_freeze.json`: архив — старый профиль «риск заморозки вкладов»

**Структура критерия:**
```json
{
  "id": "cb_emergency_rate_hike",
  "name": "Внеплановое экстренное повышение ключевой ставки ЦБ",
  "description": "...",
  "search_query": "...",
  "weight": 15,
  "speed": "fast"
}
```

**Поле `speed`** определяет временной горизонт поиска агента:
- `fast` (⚡) — данные в день прогона; агент ищет события **с момента предыдущего прогона**
- `medium` (📅) — задержка 1-4 нед.; агент ищет за **последние 30 дней**
- `slow` (🐢) — задержка 1-2 мес.; агент ищет **последние официальные данные за квартал**

**Поля источников** управляют фильтрацией до модели:
- `source_group` — тип доказательств: `official_event`, `official_stats`, `market_data`, `news_event`
- `source_policy.primary_domains` — предпочтительные первичные домены
- `source_policy.secondary_domains` — допустимые подтверждающие домены
- `source_policy.requires_official` — можно ли сработать без official
- `source_policy.min_independent_sources` — сколько независимых источников нужно без official
- `freshness.window_days` — окно свежести для фильтрации Tavily-результатов

**Пороги риска:**
- 🟢 **НИЗКИЙ** (green): 0-12 очков — ситуация стабильная
- 🟡 **СРЕДНИЙ** (yellow): 13-26 очков — повышенное внимание
- 🔴 **ВЫСОКИЙ** (red): 27+ очков — срочные меры

---

## Зависимости

```
python-dotenv>=1.2.1
langchain>=1.2.10
langchain-anthropic>=0.3.0
langchain-openai>=0.3.0
langchain-google-genai>=2.1.0
langgraph>=1.0.8
httpx>=0.27.0
langchain-tavily>=0.2.17
```

### Переменные окружения

Для локального запуска — в файле `.env`:
- `TAVILY_API_KEY` — ключ Tavily для поиска
- `MODEL_PROVIDER` — `openai`, `gigachat`, `gemini` или `anthropic`
- `OPENAI_API_KEY` — ключ OpenAI (если `MODEL_PROVIDER=openai`)
- `GOOGLE_API_KEY` — ключ Google Gemini (если `MODEL_PROVIDER=gemini`)
- `ANTHROPIC_API_KEY` — ключ Anthropic (если `MODEL_PROVIDER=anthropic`)
- `RESEARCH_LEDGER_FILE` — путь к локальной памяти использованных источников (опционально, по умолчанию `research_ledger.json`)
- `EXPORT_WEB_JSON` — путь для экспорта web-отчёта (опционально)
- `BOT_REPORTER_DIR` — путь к внешнему Telegram reporter с `edit_post.py` (опционально)

## Cursor Cloud specific instructions

**Project type:** Pure Python CLI application (no web server, no database, no Docker). Uses `uv` as the sole package manager.

**Running the bot locally:** `uv run python src/lc_money_alert_bot.py --provider <openai|gemini|gigachat|anthropic>`. Requires `TAVILY_API_KEY` and an LLM provider key (`OPENAI_API_KEY`, `GOOGLE_API_KEY`/`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or GigaChat credentials). Telegram is optional and handled only through external `BOT_REPORTER_DIR`.

**Quick test run:** `CRITERIA_FILE=criteria_small.json uv run python src/lc_money_alert_bot.py --provider openai` — uses 10 criteria instead of 35, finishes in ~30s, costs ~$0.18 (OpenAI) or ~$0.33 (Gemini).

**Tavily initialization:** `TavilySearch` is initialized lazily on the first `WebSearch` call, not at module import.

**Gotcha — Gemini preview models:** `gemini-3.1-pro-preview` may have high latency or time out from cloud VMs. Override with `GEMINI_MODEL=gemini-2.5-flash` for faster/more reliable runs. The library accepts both `GOOGLE_API_KEY` and `GEMINI_API_KEY`.

**Linting:** No linter is configured in `pyproject.toml`. Use `uvx ruff check src/` for ad-hoc linting.

**Tests:** No test suite exists. Verify correctness by running the core utilities directly (criteria loading, prompt formatting, report export — see `src/analysis_core.py`), or by running the bot end-to-end with `criteria_small.json`.

**Criteria files:** `criteria.json` (35 criteria, default), `criteria_small.json` (10 criteria, for testing). Set `CRITERIA_FILE=criteria_small.json` for cheaper/faster test runs.

**Run history:** Each run appends a record to `runs_history.json` (created automatically and ignored by git). Set `RUNS_HISTORY_FILE` to override the path.
