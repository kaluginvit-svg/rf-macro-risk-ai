# 📈 RF Macro Outlook AI

AI-агент для **макро-оценки экономики РФ**: негативные/позитивные тенденции и риск кризисного сценария на горизонте **6 месяцев**.

Ведёт Telegram-канал [@money_alert_ai](https://t.me/money_alert_ai)

> **Based on** [Rai220/money_alert_ai](https://github.com/Rai220/money_alert_ai) by Konstantin Krestnikov — спасибо за оригинальную архитектуру.

## 🎯 Что делает

Анализирует новостной фон по набору критериев риска и выдаёт оценку риска кризисного сценария (6м):

- 🟢 **НИЗКИЙ** (0-12 очков) — ситуация стабильная
- 🟡 **СРЕДНИЙ** (13-26 очков) — повышенное внимание
- 🔴 **ВЫСОКИЙ** (27+ очков) — срочные меры

## 🏗️ Архитектура

**Один агент** (LangChain) с инструментами WebSearch/WebFetch:

- Получает все критерии в системном промпте
- Сам планирует порядок проверки
- Делает WebSearch по группам критериев
- Выдаёт компактный JSON → форматируется в Telegram-отчёт

## 🌐 Demo

**[kaluginvit.github.io/rf-macro-risk-ai](https://kaluginvit.github.io/rf-macro-risk-ai)** — интерактивная страница с последним обзором, реестром критериев и историей прогонов. Обновляется после каждого локального прогона (`docs/data.json` коммитится и деплоится автоматически).

## 🚀 Быстрый старт

### Требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — быстрый менеджер пакетов
- `TAVILY_API_KEY` (поиск) и `OPENAI_API_KEY`

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/kaluginvit/rf-macro-risk-ai.git
cd rf-macro-risk-ai

# Скопировать пример конфигурации и заполнить своими ключами
cp .env.example .env

# Установить зависимости
uv sync
```

### Конфигурация

Отредактируйте `.env` файл:

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `TAVILY_API_KEY` | ✅ | API ключ Tavily для поиска |
| `MODEL_PROVIDER` | ✅ | `openai`, `gemini`, `gigachat` или `anthropic` |
| `OPENAI_API_KEY` | при `MODEL_PROVIDER=openai` | API ключ OpenAI |
| `GOOGLE_API_KEY` | при `MODEL_PROVIDER=gemini` | API ключ Google Gemini |
| `GIGACHAT_USER`/`GIGACHAT_PASSWORD` | при `MODEL_PROVIDER=gigachat` | доступ к GigaChat |
| `CRITERIA_FILE` | ❌ | Путь к файлу критериев (по умолчанию `criteria.json`) |
| `TELEGRAM_BOT_TOKEN` | ❌ | Токен бота для отправки отчётов в Telegram |
| `TELEGRAM_CHANNEL_ID` | ❌ | ID чата/канала для публикации |

Для тестов можно использовать сокращённый набор критериев:
```bash
CRITERIA_FILE=criteria_small.json
```

Также в репозитории сохранён старый профиль «риск заморозки вкладов»:

```bash
CRITERIA_FILE=archive/criteria_deposit_freeze.json
```

### Локальный запуск

```bash
uv run python src/lc_money_alert_bot.py                    # OpenAI (по умолчанию)
uv run python src/lc_money_alert_bot.py --provider gemini  # Gemini
uv run python src/lc_money_alert_bot.py --provider gigachat # GigaChat
```

⚠️ **Внимание:** Запуск занимает несколько минут и стоит денег (API вызовы LLM + поиск).

### 📅 Автопубликация по расписанию

Демон публикует отчёт в Telegram-канал каждый день в заданное время без ручного запуска:

```bash
# В Бот_репортер/.env:
SCHEDULE_TIME=09:00
EXPORT_WEB_JSON=.../docs/data.json

python Бот_репортер/daemon.py
```

После каждого прогона `docs/data.json` автоматически коммитится и пушится — GitHub Pages обновляется без дополнительных действий.

## 📊 Пример вывода

```
📊 ИТОГОВЫЙ ОТЧЁТ
Уровень риска: 🟢 НИЗКИЙ
Очки: 0
✅ Сработавших критериев нет

📝 Резюме: Финансовая система стабильна...
💡 Рекомендация: Продолжать мониторинг...

💰 СТАТИСТИКА РАСХОДОВ
   Шагов агента: 12
   Input токены: 45,230
   Output токены: 3,450
   💵 ИТОГО: $0.1874
```

## 📁 Структура проекта

```
├── criteria.json                     # Макро-критерии РФ — 35 шт. (по умолчанию)
├── criteria_small.json               # Сокращённый набор — 10 шт. для тестов
├── archive/
│   ├── criteria_deposit_freeze.json       # Архив: старый профиль «риск заморозки вкладов»
│   └── criteria_deposit_freeze_small.json # Архив: сокращённый депозитный набор
├── runs_history.json                 # История прогонов (создаётся автоматически, не в git)
├── src/
│   ├── lc_money_alert_bot.py   # Основной агент (LangChain) — только анализ
│   └── analysis_core.py        # Утилиты: критерии, история, экспорт, промпт
└── AGENTS.md             # Подробная документация
```

## 🔧 Зависимости

```
python-dotenv>=1.2.1
langchain>=1.2.10
langchain-openai>=0.3.0
langchain-google-genai>=2.1.0
langgraph>=1.0.8
httpx>=0.27.0
langchain-tavily>=0.2.17
```

## 📜 Лицензия

MIT License © 2026 Konstantin Krestnikov
