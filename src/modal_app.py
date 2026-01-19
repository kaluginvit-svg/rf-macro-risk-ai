"""
Modal приложение для запуска бота мониторинга по расписанию.

Запуск:
  modal deploy src/modal_app.py   # Деплой с расписанием
  modal run src/modal_app.py      # Ручной тестовый запуск

Секреты Modal:
  - anthropic-secret: ANTHROPIC_API_KEY
  - telegram: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
"""

import modal
from pathlib import Path

# Путь к корню проекта (относительно этого файла)
PROJECT_ROOT = Path(__file__).parent.parent

# Создаём Modal приложение
app = modal.App("money-alert-bot")

# Определяем image с зависимостями и локальными файлами
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "claude-agent-sdk>=0.1.20",
        "python-dotenv>=1.2.1",
        "python-telegram-bot>=21.0",
    )
    # Копируем файлы проекта в образ
    .add_local_file(PROJECT_ROOT / "criteria.json", "/app/criteria.json")
    .add_local_dir(PROJECT_ROOT / "src", "/app/src")
)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("anthropic-secret"),  # ANTHROPIC_API_KEY
        modal.Secret.from_name("telegram"),  # TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
    ],
    timeout=1800,  # 30 минут таймаут (агент может работать долго)
    schedule=modal.Cron("0 6 * * *"),  # 6:00 UTC = 9:00 MSK
)
async def run_daily_check():
    """Ежедневная проверка в 9:00 по Москве."""
    import os
    import sys
    
    # Переходим в директорию приложения
    os.chdir("/app")
    sys.path.insert(0, "/app/src")
    
    print(f"📤 Telegram chat ID: {os.getenv('TELEGRAM_CHANNEL_ID', 'не задан')}")
    
    # Импортируем и запускаем бота
    from money_alert_bot import run_agent, format_telegram_report, send_telegram_report, Logger
    
    with Logger() as logger:
        result = await run_agent("criteria.json", logger)
        
        # Отправка в Telegram
        report = format_telegram_report(result, result["stats"])
        await send_telegram_report(report)
    
    # Логируем результат
    if result and result.get("result"):
        risk_level = result["result"].get("risk_level", "unknown")
        score = result["result"].get("total_score", 0)
        print(f"✅ Проверка завершена: risk_level={risk_level}, score={score}")
    else:
        print("⚠️ Проверка завершена без структурированного результата")
    
    return result


@app.local_entrypoint()
def main_entrypoint():
    """Локальная точка входа для тестового запуска через `modal run`."""
    result = run_daily_check.remote()
    print(f"Результат: {result}")

