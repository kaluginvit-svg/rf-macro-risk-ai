"""
Простой React агент для мониторинга финансовых рисков.
Один агент проходит по всем критериям, сам планирует поиски и выдаёт оценку.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, ToolUseBlock
from telegram import Bot

load_dotenv()

# Папка для логов
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Цены Claude Opus 4 (январь 2026)
OPUS_INPUT_PRICE = 15.0 / 1_000_000   # $15 per 1M input tokens
OPUS_OUTPUT_PRICE = 75.0 / 1_000_000  # $75 per 1M output tokens


class Logger:
    """Логгер для записи в файл и консоль."""
    
    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOGS_DIR / f"run_{timestamp}.log"
        self._file = open(self.log_file, "w", encoding="utf-8")
        
    def log(self, message: str, to_console: bool = True):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._file.write(f"[{timestamp}] {message}\n")
        self._file.flush()
        if to_console:
            print(message)
    
    def close(self):
        self._file.close()
        
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def format_telegram_report(result: dict, stats: dict) -> str:
    """Форматирует отчёт для отправки в Telegram."""
    final_result = result.get("result")
    lines = ["🤖 Мониторинг финансовых рисков", ""]
    
    if final_result:
        risk_level = final_result.get("risk_level", "unknown")
        risk_map = {
            "green": ("🟢", "НИЗКИЙ"),
            "yellow": ("🟡", "СРЕДНИЙ"),
            "red": ("🔴", "ВЫСОКИЙ")
        }
        emoji, label = risk_map.get(risk_level, ("❓", "НЕИЗВЕСТНО"))
        
        lines.append(f"Уровень риска: {emoji} {label}")
        lines.append(f"Очки: {final_result.get('total_score', '?')}")
        lines.append("")
        
        triggered = final_result.get("triggered_criteria", [])
        if triggered:
            lines.append("⚠️ Сработавшие критерии:")
            for t in triggered:
                lines.append(f"  • {t.get('id', '?')}: {t.get('evidence', '')[:80]}")
            lines.append("")
            lines.append(f"📝 Резюме: {final_result.get('summary', 'Нет данных')}")
            lines.append("")
            lines.append(f"💡 Рекомендация: {final_result.get('recommendation', 'Нет данных')}")
        else:
            lines.append("✅ Сработавших критериев нет")
        
        key_insights = final_result.get('key_insights', [])
        if key_insights:
            lines.append("")
            lines.append("📝 Важные тезисы:")
            for insight in key_insights:
                lines.append(f"   {insight}")
    else:
        lines.append("⚠️ Не удалось получить результат от агента")
    
    lines.extend([
        "",
        "-" * 30,
        f"⏱️ Время: {stats['time_seconds']:.0f}с | 🔍 Поисков: {stats['tool_calls']}",
        f"💰 Стоимость: ${stats['cost_usd']:.4f}",
        "",
        "Не является инвестиционной рекомендацией."
    ])
    
    return "\n".join(lines)


async def send_telegram_report(report: str) -> bool:
    """Отправляет отчёт в Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")
    
    if not token or not chat_id:
        print(f"⚠️ Telegram не настроен (token: {'есть' if token else 'нет'}, chat_id: {chat_id or 'нет'})")
        return False
    
    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=report)
        print(f"✅ Отчёт отправлен в Telegram (chat_id: {chat_id})")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False


def load_criteria(path: str = "criteria.json") -> dict:
    """Загружает критерии из JSON файла."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_criteria_for_prompt(criteria_data: dict) -> str:
    """Форматирует критерии для промпта агенту."""
    return "\n".join(
        f"### {c['id']} (вес: {c['weight']})\n**{c['name']}**\n{c['description']}\nПоисковый запрос: `{c['search_query']}`\n"
        for c in criteria_data["criteria"]
    )


SYSTEM_PROMPT = """Ты — аналитик экономической безопасности России. Твоя задача — проверить список критериев риска заморозки вкладов и дать итоговую оценку.

📅 **Сегодня: {today_date}**

## ⚠️ ЛИМИТЫ

### Лимит поисков: {search_limit}
- Максимум **{search_limit} поисков**
- Группируй похожие критерии в один поиск
- После {search_limit} поисков — СТОП поиски!

**Правило:** Если лимит исчерпан — прекращай поиски и выдавай финальный JSON!

## ТВОИ ИНСТРУМЕНТЫ
- WebSearch: поиск актуальных новостей в интернете
- WebFetch: загрузка содержимого страницы по URL

## 📰 АРХИВ КАНАЛА
Перед финализацией отчёта **ОБЯЗАТЕЛЬНО** загрузи предыдущие посты канала:
```
WebFetch: https://t.me/s/money_alert_ai
```

Это нужно чтобы:
- **НЕ ПОВТОРЯТЬ** тезисы из предыдущих дней
- Писать **РАЗНООБРАЗНЫЕ** тексты каждый день
- Быть **КОНСИСТЕНТНЫМ** в оценках (если вчера риск был низкий и ситуация не изменилась — сегодня тоже низкий)

## 📋 ШАГ 0: ПЛАНИРОВАНИЕ (ОБЯЗАТЕЛЬНО!)

**ПЕРЕД первым поиском** проанализируй все критерии и сгруппируй их по темам:

1. **Изучи все критерии** и найди пересечения
2. **Создай группы** похожих критериев для одного поиска:
   - Группа "ЦБ и банки": санации, лицензии, мораторий
   - Группа "Валюта": ограничения, лимиты на снятие
   - Группа "Бюджет": секвестр, ФНБ, кассовые разрывы
3. **Начни с критичных** (вес 20) — они важнее всего!

## ПРАВИЛА РАБОТЫ
1. **Сначала СПЛАНИРУЙ** — составь план группировки критериев
2. **Потом ВЫПОЛНЯЙ** — делай поиски по плану
3. **⚠️ ПРОВЕРЯЙ ДАТЫ!** В поиске часто попадаются старые новости:
   - Релевантны ТОЛЬКО события за **последние 3 дня** (с {today_date} назад)
   - ОБЯЗАТЕЛЬНО смотри дату публикации каждой новости
   - Игнорируй: старые новости (2022-2025), фейки, прогнозы без источников
4. **Оценивай честно**: при сомнениях — критерий НЕ сработал
5. **ПЕРЕД финализацией** — загрузи архив канала (https://t.me/s/money_alert_ai) и убедись, что твои тезисы НЕ повторяют вчерашние
6. **После {search_limit} поисков** — СТОП! Выдай финальный JSON

## ФОРМАТ ИТОГА

```json
{{
  "checked_criteria": ["id1", "id2", ...],
  "triggered_criteria": [
    {{"id": "criterion_id", "evidence": "краткое описание", "confidence": 0.9}}
  ],
  "total_score": <сумма весов сработавших критериев>,
  "risk_level": "green/yellow/red",
  "summary": "Краткое резюме ситуации",
  "recommendation": "Что делать",
  "key_insights": [
    "• Тезис 1 — объяснение",
    "• Тезис 2 — объяснение"
  ]
}}
```

**key_insights** — 2-3 тезиса о критериях, которые почти сработали или отброшены с объяснением.
⚠️ **ВАЖНО:** Тезисы должны быть УНИКАЛЬНЫМИ — не повторяй то, что уже было в предыдущих постах канала!

## ПОРОГИ РИСКА
- 🟢 НИЗКИЙ (green): 0-9 очков
- 🟡 СРЕДНИЙ (yellow): 10-19 очков
- 🔴 ВЫСОКИЙ (red): 20+ очков

## ⚠️ ТОН — СПОКОЙНЫЙ И НЕЙТРАЛЬНЫЙ!
- Пиши **сухо и по факту**, без драматизации и эмоций
- **ЗАПРЕЩЕНО** использовать кричащие формулировки:
  - ❌ "СРОЧНО!", "ВНИМАНИЕ!", "ТРЕВОГА!", "ОПАСНОСТЬ!"
  - ❌ "вклады заморозят", "деньги пропадут", "банки рухнут"
  - ❌ "срочно снимайте", "бегите из банков", "спасайте сбережения"
  - ❌ "катастрофа", "крах", "коллапс", "обвал"
- **ИСПОЛЬЗУЙ** нейтральные формулировки:
  - ✅ "Оцениваю риски как повышенные"
  - ✅ "Рекомендую обратить внимание на..."
  - ✅ "Ситуация требует мониторинга"
  - ✅ "Наблюдается рост/снижение показателя"

## КРИТЕРИИ ДЛЯ ПРОВЕРКИ

{criteria}

---
Начни с ПЛАНИРОВАНИЯ, затем выполняй поиски. Лимит: {search_limit}.
"""


async def run_agent(criteria_path: str = "criteria.json", logger: Logger | None = None) -> dict:
    """Запускает агента для анализа критериев."""
    
    def log(msg: str, to_console: bool = True):
        if logger:
            logger.log(msg, to_console)
        elif to_console:
            print(msg)
    
    telegram_id = os.getenv('TELEGRAM_CHANNEL_ID', 'не задан')
    log("=" * 60)
    log("🤖 Агент мониторинга финансовых рисков")
    log(f"📤 Telegram: {telegram_id}")
    log("=" * 60)
    
    # Загружаем критерии
    criteria_data = load_criteria(criteria_path)
    criteria_text = format_criteria_for_prompt(criteria_data)
    log(f"📋 Загружено критериев: {len(criteria_data['criteria'])}")
    
    # Настройки
    search_limit = 50
    max_turns = 100
    today_date = datetime.now().strftime("%d.%m.%Y")
    
    prompt = SYSTEM_PROMPT.format(
        criteria=criteria_text,
        search_limit=search_limit,
        today_date=today_date,
    )
    
    # Статистика
    step_count = 0
    tool_calls_count = 0
    start_time = datetime.now()
    final_result = None
    total_input_tokens = 0
    total_output_tokens = 0
    
    log(f"🔍 Запуск агента (лимит поисков: {search_limit})")
    log("-" * 60)
    
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model="claude-opus-4-5",
            allowed_tools=["WebSearch", "WebFetch"],
            permission_mode="acceptEdits",
            max_turns=max_turns,
        ),
    ):
        if isinstance(message, AssistantMessage):
            step_count += 1
            elapsed = (datetime.now() - start_time).total_seconds()
            
            log("")
            log(f"📝 ШАГ {step_count} | 🔍 {tool_calls_count}/{search_limit} | ⏱️ {elapsed:.0f}с")
            
            for block in message.content:
                if hasattr(block, "text"):
                    text = block.text
                    # Показываем первые строки
                    lines = text.strip().split("\n")[:5]
                    for line in lines:
                        if line.strip():
                            log(f"   {line[:120]}")
                    if len(text.strip().split("\n")) > 5:
                        log("   ... (ещё строки)")
                    
                    # Полный текст в файл
                    log(f"\n--- ТЕКСТ ШАГА {step_count} ---\n{text}\n---\n", to_console=False)
                    
                    # Ищем финальный JSON
                    if "```json" in text and '"risk_level"' in text:
                        log("   🎯 Обнаружен финальный JSON!")
                        try:
                            json_start = text.find("```json") + 7
                            json_end = text.find("```", json_start)
                            if json_end > json_start:
                                final_result = json.loads(text[json_start:json_end].strip())
                        except json.JSONDecodeError:
                            pass
                
                elif isinstance(block, ToolUseBlock):
                    tool_calls_count += 1
                    tool_name = getattr(block, 'name', 'unknown')
                    tool_input = getattr(block, 'input', {})
                    query_text = tool_input.get('query', '') if isinstance(tool_input, dict) else ''
                    log(f"   🔧 #{tool_calls_count} {tool_name}: {query_text[:60]}...")
                            
        elif isinstance(message, ResultMessage):
            if message.usage:
                total_input_tokens = message.usage.get("input_tokens", 0)
                total_output_tokens = message.usage.get("output_tokens", 0)
            
            # Извлекаем результат если ещё нет
            if message.result and not final_result:
                try:
                    result_text = message.result
                    if "```json" in result_text:
                        json_start = result_text.find("```json") + 7
                        json_end = result_text.find("```", json_start)
                        if json_end > json_start:
                            final_result = json.loads(result_text[json_start:json_end].strip())
                    elif result_text.strip().startswith("{"):
                        final_result = json.loads(result_text)
                except json.JSONDecodeError:
                    pass
    
    total_time = (datetime.now() - start_time).total_seconds()
    total_cost = total_input_tokens * OPUS_INPUT_PRICE + total_output_tokens * OPUS_OUTPUT_PRICE
    
    # Итоговый отчёт
    log("")
    log("=" * 60)
    log("📊 ИТОГОВЫЙ ОТЧЁТ")
    log("=" * 60)
    
    if final_result:
        risk_map = {"green": ("🟢", "НИЗКИЙ"), "yellow": ("🟡", "СРЕДНИЙ"), "red": ("🔴", "ВЫСОКИЙ")}
        emoji, label = risk_map.get(final_result.get("risk_level"), ("❓", "НЕИЗВЕСТНО"))
        
        log(f"Уровень риска: {emoji} {label}")
        log(f"Очки: {final_result.get('total_score', '?')}")
        
        triggered = final_result.get("triggered_criteria", [])
        if triggered:
            log("")
            log("⚠️ Сработавшие критерии:")
            for t in triggered:
                log(f"   • {t.get('id', '?')}: {t.get('evidence', '')[:60]}...")
            log("")
            log(f"📝 Резюме: {final_result.get('summary', 'Нет данных')}")
            log(f"💡 Рекомендация: {final_result.get('recommendation', 'Нет данных')}")
        else:
            log("✅ Сработавших критериев нет")
        
        key_insights = final_result.get('key_insights', [])
        if key_insights:
            log("")
            log("📝 Важные тезисы:")
            for insight in key_insights:
                log(f"   {insight}")
    else:
        log("⚠️ Не удалось получить результат от агента")
    
    log("")
    log("-" * 60)
    log(f"⏱️ Время: {total_time:.0f}с | 📝 Шагов: {step_count} | 🔍 Поисков: {tool_calls_count}")
    log(f"📊 Токены: {total_input_tokens:,} in / {total_output_tokens:,} out")
    log(f"💰 Стоимость: ${total_cost:.4f}")
    log("=" * 60)
    
    return {
        "result": final_result,
        "stats": {
            "steps": step_count,
            "tool_calls": tool_calls_count,
            "time_seconds": total_time,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cost_usd": total_cost,
        }
    }


async def main():
    """Точка входа."""
    with Logger() as logger:
        logger.log(f"📁 Лог: {logger.log_file}")
        
        result = await run_agent("criteria.json", logger)
        
        logger.log("")
        logger.log("📤 Отправка в Telegram...")
        report = format_telegram_report(result, result["stats"])
        await send_telegram_report(report)
        
        logger.log(f"📁 Лог сохранён: {logger.log_file}")
        return result


if __name__ == "__main__":
    asyncio.run(main())
