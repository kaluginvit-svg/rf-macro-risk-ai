# RF Macro Outlook AI

AI-агент для **макро-оценки экономики РФ**: негативные/позитивные тенденции и риск кризисного сценария на горизонте **6 месяцев**.

> **Based on** [Rai220/money_alert_ai](https://github.com/Rai220/money_alert_ai) by Konstantin Krestnikov — спасибо за оригинальную архитектуру.

## Что делает

Анализирует новостной фон по 35 макро-критериям и выдаёт оценку риска кризисного сценария:

| Уровень | Очки | Описание |
|---------|------|----------|
| 🟢 НИЗКИЙ | 0–19 | Ситуация стабильная |
| 🟡 СРЕДНИЙ | 20–39 | Повышенное внимание |
| 🟠 СУЩЕСТВЕННЫЙ | 40–69 | Значимые риски |
| 🔴 ВЫСОКИЙ | 70+ | Требует реакции |
| ⚫ АВАРИЙНЫЙ | — | Триггер аварийных критериев |

Отдельно оценивается **риск доступа к вкладам** (горизонт 1–3 месяца) по 5 специальным критериям.

## Пайплайн

```
lc_money_alert_bot.py
  └─► analysis_core.py → export_web_report()
        ├─► docs/data.json          (результат прогона)
        ├─► docs/index.html         (обновляет inline-данные)
        ├─► git commit + push       (GitHub Pages деплой)
        └─► _call_reporter()
              └─► Бот_репортер/run.py --from-file
                    └─► новый пост в Telegram-канал
```

## Demo

**[kaluginvit.github.io/rf-macro-risk-ai](https://kaluginvit.github.io/rf-macro-risk-ai)** — интерактивная страница с последним обзором, реестром критериев и историей прогонов. Обновляется автоматически после каждого прогона.

## Быстрый старт

### Требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- `TAVILY_API_KEY` (поиск) и ключ выбранного LLM-провайдера

### Установка

```bash
git clone https://github.com/kaluginvit/rf-macro-risk-ai.git
cd rf-macro-risk-ai
cp .env.example .env
# Заполните .env своими ключами
uv sync
```

### Конфигурация `.env`

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `TAVILY_API_KEY` | ✅ | API ключ Tavily для поиска |
| `MODEL_PROVIDER` | ✅ | `openai`, `gemini`, `gigachat` или `anthropic` |
| `OPENAI_API_KEY` | при `openai` | API ключ OpenAI |
| `GOOGLE_API_KEY` | при `gemini` | API ключ Google Gemini |
| `GIGACHAT_USER` / `GIGACHAT_PASSWORD` | при `gigachat` | Доступ к GigaChat |
| `ANTHROPIC_API_KEY` | при `anthropic` | API ключ Anthropic |
| `CRITERIA_FILE` | ❌ | Файл критериев (по умолчанию `criteria.json`) |
| `RESEARCH_LEDGER_FILE` | ❌ | Локальная память источников, по умолчанию `research_ledger.json` (не в git) |
| `EXPORT_WEB_JSON` | ❌ | Путь для экспорта web-отчёта, например `docs/data.json` |
| `BOT_REPORTER_DIR` | ❌ | Путь к Telegram-репортёру — после анализа запустит `run.py --from-file` |

### Запуск

```bash
uv run python src/lc_money_alert_bot.py                     # OpenAI (по умолчанию)
uv run python src/lc_money_alert_bot.py --provider gemini   # Gemini
uv run python src/lc_money_alert_bot.py --provider gigachat # GigaChat
```

Для тестов — сокращённый набор критериев:

```bash
CRITERIA_FILE=criteria_small.json uv run python src/lc_money_alert_bot.py
```

⚠️ Запуск занимает несколько минут и расходует API-кредиты (LLM + поиск).

## Критерии

35 критериев разбиты по скорости реагирования (`fast` / `medium` / `slow`) и типу источника (`official_event`, `official_stats`, `market_data`, `news_event`). Каждый критерий имеет:

- `weight` — вес в итоговом счёте
- `search_query` — поисковый запрос
- `source_policy` — политика первичных/вторичных источников
- `freshness` — окно актуальности в днях

Архив старого профиля «риск заморозки вкладов»:

```bash
CRITERIA_FILE=archive/criteria_deposit_freeze.json
```

## Публикация через Telegram-репортёра

Репозиторий не содержит Telegram-секретов и не публикует сообщения напрямую. Публикацию выполняет отдельный бот-репортёр (`Бот_репортер/`).

Для связки задайте путь:

```bash
BOT_REPORTER_DIR=../Бот_репортер
```

После анализа `analysis_core.py` автоматически запустит `BOT_REPORTER_DIR/run.py --from-file`, который отправит **новый пост** в Telegram-канал.

Бот-репортёр требует собственного `.env` с `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` и `TELEGRAM_ADMIN_CHAT_ID`.

## Структура проекта

```
├── criteria.json                          # 35 макро-критериев (основной набор)
├── criteria_small.json                    # 10 критериев для быстрых тестов
├── archive/
│   ├── criteria_deposit_freeze.json       # Архив: профиль риска заморозки вкладов
│   └── criteria_deposit_freeze_small.json
├── docs/
│   ├── data.json                          # Последний результат прогона (GitHub Pages)
│   └── index.html                         # Интерактивный дашборд
├── src/
│   ├── lc_money_alert_bot.py              # Агент (LangChain) — анализ и запуск
│   ├── analysis_core.py                   # Критерии, история, экспорт, пайплайн
│   ├── scoring.py                         # Подсчёт очков, пороги, deposit_access
│   └── source_registry.py                 # Реестр использованных источников
├── research_ledger.json                   # Локальная память (не в git, .gitignore)
├── runs_history.json                      # История прогонов (не в git)
└── AGENTS.md                              # Подробная документация агента
```

## Зависимости

```
python-dotenv
langchain
langchain-openai
langchain-google-genai
langgraph
httpx
langchain-tavily
```

## Лицензия

MIT License © 2026
