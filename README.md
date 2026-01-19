# 💰 Money Alert AI

AI-агент для мониторинга финансовой стабильности и оценки рисков заморозки вкладов в России.

Ведёт Telegram-канал [@money_alert_ai](https://t.me/money_alert_ai)

## 🎯 Что делает

Анализирует новостной фон по 46 критериям риска и выдаёт оценку:

- 🟢 **НИЗКИЙ** (0-9 очков) — ситуация стабильная
- 🟡 **СРЕДНИЙ** (10-19 очков) — повышенное внимание
- 🔴 **ВЫСОКИЙ** (20+ очков) — срочные меры

## 🏗️ Архитектура

**React-агент** на базе Claude Sonnet 4.5:

- Получает все критерии в системном промпте
- Сам планирует порядок проверки (начинает с критичных — вес 20)
- Использует WebSearch для поиска актуальных новостей
- Группирует похожие критерии для эффективности

## 🚀 Быстрый старт

### Требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — быстрый менеджер пакетов
- API ключ Anthropic

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/Rai220/money_alert_ai.git
cd money_alert_ai

# Скопировать пример конфигурации и заполнить своими ключами
cp .env.example .env

# Установить зависимости
uv sync
```

### Конфигурация

Отредактируйте `.env` файл:

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `ANTHROPIC_API_KEY` | ✅ | API ключ от [Anthropic Console](https://console.anthropic.com/) |
| `CRITERIA_FILE` | ❌ | Путь к файлу критериев (по умолчанию `criteria.json`) |
| `TELEGRAM_BOT_TOKEN` | ❌ | Токен бота для отправки отчётов в Telegram |
| `TELEGRAM_CHANNEL_ID` | ❌ | ID чата/канала для публикации |

Для тестов можно использовать сокращённый набор критериев:
```bash
CRITERIA_FILE=criteria_small.json
```

### Локальный запуск

```bash
uv run python src/money_alert_bot.py
```

⚠️ **Внимание:** Запуск занимает несколько минут и стоит денег (API вызовы Claude).

### ☁️ Деплой на Modal.com (по расписанию)

Бот может автоматически запускаться каждый день в 9:00 по Москве.

**1. Создать секреты в Modal:**

```bash
# Anthropic API ключ
modal secret create anthropic-secret ANTHROPIC_API_KEY=sk-ant-...

# Telegram секреты
modal secret create telegram \
  TELEGRAM_BOT_TOKEN=123456789:ABC... \
  TELEGRAM_CHANNEL_ID=123456789
```

**2. Задеплоить:**

```bash
modal deploy src/modal_app.py
```

**3. Тестовый запуск (с логами):**

```bash
modal run src/modal_app.py
```

**4. Посмотреть логи:**

```bash
modal app logs money-alert-bot
```

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
├── money_alert_bot.py    # Основной агент
├── criteria.json         # 46 критериев риска с весами
├── criteria_small.json   # Сокращённый набор для тестов
├── src/
│   ├── analyzer.py       # Многоагентная система (альтернатива)
│   ├── criteria_loader.py
│   ├── report.py
│   └── telegram_bot.py   # Telegram интеграция
└── AGENTS.md             # Подробная документация
```

## 🔧 Зависимости

```
claude-agent-sdk>=0.1.20
python-dotenv>=1.2.1
python-telegram-bot>=21.0
modal>=0.67.0
```

## 📜 Лицензия

MIT License © 2026 Konstantin Krestnikov
