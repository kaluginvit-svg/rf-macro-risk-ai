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
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, ToolUseBlock, ToolResultBlock
from telegram import Bot

load_dotenv()

# Папка для логов
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Цены Claude Opus 4 (январь 2026)
OPUS_INPUT_PRICE = 15.0 / 1_000_000  # $15 per 1M input tokens
OPUS_OUTPUT_PRICE = 75.0 / 1_000_000  # $75 per 1M output tokens

# Лимиты контекста
CONTEXT_LIMIT = 200_000  # Максимум токенов для Opus 4
CONTEXT_SOFT_LIMIT = 150_000  # Мягкий лимит - после него прекращаем поиски


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Рассчитывает стоимость в USD."""
    return input_tokens * OPUS_INPUT_PRICE + output_tokens * OPUS_OUTPUT_PRICE


def estimate_tokens(text: str) -> int:
    """Примерная оценка токенов (для русского ~2.5 символа = 1 токен)."""
    return max(1, len(text) // 2)


class Logger:
    """Логгер для записи в файл и консоль."""
    
    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOGS_DIR / f"run_{timestamp}.log"
        self._file = open(self.log_file, "w", encoding="utf-8")
        
    def log(self, message: str, to_console: bool = True):
        """Записывает сообщение в лог и опционально в консоль."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        self._file.write(log_line + "\n")
        self._file.flush()
        if to_console:
            print(message)
    
    def close(self):
        """Закрывает файл лога."""
        self._file.close()
        
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def format_telegram_report(result: dict, stats: dict) -> str:
    """Форматирует отчёт для отправки в Telegram (plain text)."""
    final_result = result.get("result")
    
    lines = []
    lines.append("🤖 Мониторинг финансовых рисков")
    lines.append(f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append("")
    
    if final_result:
        risk_level = final_result.get("risk_level", "unknown")
        risk_emojis = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        risk_labels = {"green": "НИЗКИЙ", "yellow": "СРЕДНИЙ", "red": "ВЫСОКИЙ"}
        
        emoji = risk_emojis.get(risk_level, "❓")
        label = risk_labels.get(risk_level, "НЕИЗВЕСТНО")
        
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
        
        # Важные тезисы (всегда показываем)
        key_insights = final_result.get('key_insights', [])
        if key_insights:
            lines.append("")
            lines.append("📝 Важные тезисы:")
            for insight in key_insights:
                lines.append(f"   {insight}")
    else:
        lines.append("⚠️ Не удалось получить результат от агента")
    
    lines.append("")
    lines.append("-" * 30)
    lines.append(f"⏱️ Время: {stats['time_seconds']:.0f}с")
    lines.append(f"📊 Шагов: {stats['steps']} | Поисков: {stats['tool_calls']}")
    lines.append(f"💰 Стоимость: ${stats['cost_usd']:.4f}")
    
    return "\n".join(lines)


async def send_telegram_report(report: str) -> bool:
    """Отправляет отчёт в Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHANNEL_ID")
    
    if not token:
        print("⚠️ TELEGRAM_BOT_TOKEN не установлен в .env")
        return False
    
    if not chat_id:
        print("⚠️ TELEGRAM_CHANNEL_ID не установлен в .env")
        return False
    
    try:
        bot = Bot(token=token)
        await bot.send_message(
            chat_id=chat_id,
            text=report,
        )
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
    lines = []
    for c in criteria_data["criteria"]:
        lines.append(f"""
### {c['id']} (вес: {c['weight']})
**{c['name']}**
{c['description']}
Поисковый запрос: `{c['search_query']}`
""")
    return "\n".join(lines)


SYSTEM_PROMPT = """Ты — аналитик экономической безопасности России. Твоя задача — проверить список критериев риска заморозки вкладов и дать итоговую оценку.

📅 **Сегодня: {today_date}**

## ⚠️ ЛИМИТЫ

### Лимит поисков: {search_limit}
- Максимум **{search_limit} поисков**
- Группируй похожие критерии в один поиск
- После {search_limit} поисков — СТОП поиски!

### Лимит контекста: {context_soft_limit:,} токенов
- Каждый поиск добавляет ~2000-5000 токенов результатов
- Когда контекст приблизится к лимиту — СТОП поиски!
- Используй уже собранную информацию для выводов

**Правило:** Если исчерпан ЛЮБОЙ из лимитов — прекращай поиски и выдавай финальный JSON!

## ТВОИ ИНСТРУМЕНТЫ
- WebSearch: поиск актуальных новостей в интернете

## 📋 ШАГ 0: ПЛАНИРОВАНИЕ (ОБЯЗАТЕЛЬНО!)

**ПЕРЕД первым поиском** проанализируй все критерии и сгруппируй их по темам для экономии поисков:

1. **Изучи все критерии** и найди пересечения по темам
2. **Создай группы** похожих критериев, которые можно проверить одним поиском:
   - Группа "ЦБ и банки": санации, лицензии, мораторий, временная администрация
   - Группа "Валюта и ограничения": валютные ограничения, лимиты на снятие, переводы
   - Группа "Бюджет и госфинансы": секвестр, ФНБ, кассовые разрывы
   - Группа "Рынки": ОФЗ, биржа, ставки
   - И т.д.
3. **Составь план поисков** — сколько поисков нужно и какие критерии покрывает каждый
4. **Начни с критичных** (вес 20) — они важнее всего!

Пример плана:
```
ПЛАН ПОИСКОВ (оценка: ~15-20 поисков на 46 критериев):
1. Критичные (вес 20): заморозка вкладов, мораторий ЦБ, банковские каникулы — 2-3 поиска
2. Группа ЦБ: санации, лицензии, послабления — 2 поиска
3. Группа валюта: ограничения, курс, контроль — 2 поиска
...
```

## ПРАВИЛА РАБОТЫ
1. **Сначала СПЛАНИРУЙ** — составь план группировки критериев (ШАГ 0)
2. **Потом ВЫПОЛНЯЙ** — делай поиски по плану
3. **Оценивай результаты честно**:
   - Ищи ТОЛЬКО события в РОССИИ за последние 7 дней
   - Игнорируй старые новости (2022-2024), фейки, прогнозы без источников
   - При сомнениях — критерий НЕ сработал
4. **Веди учёт поисков** — после каждого поиска отмечай какие критерии проверены
5. **ВАЖНО:** После {search_limit} поисков — ПРЕКРАТИ искать и выдай финальный JSON!

## ФОРМАТ ИТОГА
Когда закончишь поиски (или когда лимит исчерпан), ОБЯЗАТЕЛЬНО выдай финальный JSON:

```json
{{
  "checked_criteria": ["id1", "id2", ...],
  "triggered_criteria": [
    {{"id": "criterion_id", "evidence": "краткое описание найденного", "confidence": 0.9}}
  ],
  "total_score": <сумма весов сработавших критериев>,
  "risk_level": "green/yellow/red",
  "summary": "Краткое резюме ситуации",
  "recommendation": "Что делать",
  "key_insights": [
    "• Тезис 1 — краткое объяснение",
    "• Тезис 2 — краткое объяснение",
    "• Тезис 3 — краткое объяснение"
  ]
}}
```

**ВАЖНО про key_insights:** Это список из 2-3 важных тезисов для телеграм-канала.

Что включать в тезисы:
- Критерии, которые **почти сработали** но не дотянули до порога
- Критерии, которые **могли бы сработать**, но были отброшены с логичным объяснением
- Интересные сигналы, которые стоит отслеживать в будущем

Формат каждого тезиса: `• [Название критерия/темы] — [объяснение почему не сработал или на что обратить внимание]`

Пример:
```json
"key_insights": [
  "• Валютные ограничения — обсуждаются в СМИ, но пока на уровне экспертных мнений без официальных решений",
  "• Ставка ЦБ — сохранена на уровне 21%, рынок ожидал повышения, ситуация стабильная",
  "• Санации банков — нет новых случаев, но ЦБ ужесточает надзор за средними банками"
]
```

## ПОРОГИ РИСКА
- 🟢 НИЗКИЙ (green): 0-9 очков — ситуация стабильная
- 🟡 СРЕДНИЙ (yellow): 10-19 очков — повышенное внимание
- 🔴 ВЫСОКИЙ (red): 20+ очков — срочные меры

## КРИТЕРИИ ДЛЯ ПРОВЕРКИ

{criteria}

---
ВАЖНО: 
- Начни с ПЛАНИРОВАНИЯ (ШАГ 0) — сгруппируй критерии для экономии поисков!
- Не спрашивай разрешения — сразу составь план и начинай работу.
- Считай поиски! Лимит: {search_limit}.
- После каждого поиска пиши статус:
  "📊 Поиск X/{search_limit} | Проверено: [критерии] | Осталось: [критерии]"
- Когда ЛЮБОЙ лимит исчерпан — СТОП поиски! Финализируй выводы.
- Для непроверенных критериев напиши "не проверено" в итоговом JSON.
"""


async def run_agent(criteria_path: str = "criteria.json", logger: Logger | None = None) -> dict:
    """Запускает агента для анализа критериев."""
    
    def log(msg: str, to_console: bool = True):
        if logger:
            logger.log(msg, to_console)
        elif to_console:
            print(msg)
    
    log("=" * 60)
    log("🤖 Агент мониторинга финансовых рисков")
    log(f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    log("=" * 60)
    log("")
    
    # Загружаем критерии
    log("📋 Загрузка критериев...")
    criteria_data = load_criteria(criteria_path)
    criteria_text = format_criteria_for_prompt(criteria_data)
    log(f"   Загружено: {len(criteria_data['criteria'])} критериев")
    log("")
    
    # Настройки агента
    search_limit = 50  # Лимит поисков (указываем боту)
    max_turns = 100    # Реальный лимит шагов (даём запас на финализацию)
    
    # Формируем промпт
    today_date = datetime.now().strftime("%d.%m.%Y")
    prompt = SYSTEM_PROMPT.format(
        criteria=criteria_text, 
        search_limit=search_limit,
        context_soft_limit=CONTEXT_SOFT_LIMIT,
        context_soft_limit_k=CONTEXT_SOFT_LIMIT // 1000,
        today_date=today_date,
    )
    
    # Оценка токенов промпта (для подсчёта стоимости)
    prompt_tokens = estimate_tokens(prompt)
    
    # Статистика
    estimated_context_tokens = prompt_tokens  # Текущий размер контекста
    estimated_output_tokens = 0
    total_input_tokens = 0  # Реальные токены (из ResultMessage)
    total_output_tokens = 0
    step_count = 0
    tool_calls_count = 0
    context_limit_reached = False
    start_time = datetime.now()
    
    log("🔍 Агент начинает работу:")
    log(f"   📊 Лимит поисков: {search_limit}")
    log(f"   📊 Лимит контекста: {CONTEXT_SOFT_LIMIT:,} токенов (из {CONTEXT_LIMIT:,})")
    log(f"   📊 Размер промпта: ~{prompt_tokens:,} токенов")
    log("-" * 60)
    
    final_result = None
    
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model="claude-opus-4-5",
            allowed_tools=["WebSearch", "WebFetch"],
            permission_mode="acceptEdits",
            max_turns=max_turns,
        ),
    ):
        # Оценка текущей стоимости
        estimated_cost = calculate_cost(estimated_context_tokens, estimated_output_tokens)
        elapsed = (datetime.now() - start_time).total_seconds()
        context_percent = (estimated_context_tokens / CONTEXT_SOFT_LIMIT) * 100
        
        if isinstance(message, AssistantMessage):
            step_count += 1
            
            # Оцениваем токены этого шага
            step_output_tokens = 0
            step_text = ""
            
            # Проверяем лимиты
            searches_remaining = search_limit - tool_calls_count
            context_remaining = CONTEXT_SOFT_LIMIT - estimated_context_tokens
            
            log("")
            log("─" * 60)
            log(f"📝 ШАГ {step_count} | 🔍 поисков: {tool_calls_count}/{search_limit} (осталось: {searches_remaining})")
            log(f"   📊 Контекст: ~{estimated_context_tokens:,}/{CONTEXT_SOFT_LIMIT:,} токенов ({context_percent:.0f}%) | осталось: ~{context_remaining:,}")
            log(f"   ⏱️ {elapsed:.0f}с | 💵 ~${estimated_cost:.4f}")
            
            # Предупреждения о лимитах
            if tool_calls_count >= search_limit:
                log("   🛑 ЛИМИТ ПОИСКОВ ИСЧЕРПАН!")
            if estimated_context_tokens >= CONTEXT_SOFT_LIMIT:
                log("   🛑 ЛИМИТ КОНТЕКСТА ДОСТИГНУТ!")
                context_limit_reached = True
            elif context_percent >= 80:
                log(f"   ⚠️ ВНИМАНИЕ: контекст заполнен на {context_percent:.0f}%!")
            
            if tool_calls_count >= search_limit or context_limit_reached:
                log("   ➡️ Бот должен ПРЕКРАТИТЬ поиски и выдать финальный JSON")
            
            log("─" * 60)
            
            for block in message.content:
                # Текстовый блок
                if hasattr(block, "text"):
                    text = block.text
                    step_text += text
                    step_output_tokens += estimate_tokens(text)
                    
                    # Выводим первые несколько строк текста
                    lines = text.strip().split("\n")
                    preview_lines = lines[:5]  # Показываем до 5 строк
                    for line in preview_lines:
                        if line.strip():
                            log(f"   {line[:120]}")
                    if len(lines) > 5:
                        log(f"   ... (ещё {len(lines) - 5} строк)")
                    
                    # Логируем полный текст в файл (без консоли)
                    log(f"\n--- ПОЛНЫЙ ТЕКСТ ШАГА {step_count} ---\n{text}\n--- КОНЕЦ ---\n", to_console=False)
                    
                    # Проверяем на финальный JSON
                    if "```json" in text and '"risk_level"' in text:
                        log("")
                        log("   🎯 Обнаружен финальный JSON!")
                        try:
                            json_start = text.find("```json") + 7
                            json_end = text.find("```", json_start)
                            if json_end > json_start:
                                json_str = text[json_start:json_end].strip()
                                final_result = json.loads(json_str)
                        except (json.JSONDecodeError, ValueError):
                            pass
                
                # Вызов инструмента
                elif isinstance(block, ToolUseBlock):
                    tool_calls_count += 1
                    tool_name = getattr(block, 'name', 'unknown')
                    tool_input = getattr(block, 'input', {})
                    
                    # Извлекаем поисковый запрос если это WebSearch
                    search_query = ""
                    if isinstance(tool_input, dict):
                        search_query = tool_input.get('query', tool_input.get('search_query', ''))
                    
                    log(f"   🔧 Вызов инструмента #{tool_calls_count}: {tool_name}")
                    if search_query:
                        log(f"      Запрос: \"{search_query[:80]}{'...' if len(search_query) > 80 else ''}\"")
                    
                    # Оцениваем токены результата поиска (~3000 токенов на поиск)
                    estimated_context_tokens += 3000
                
                # Результат инструмента
                elif isinstance(block, ToolResultBlock):
                    result_content = str(getattr(block, 'content', ''))
                    result_tokens = estimate_tokens(result_content)
                    result_preview = result_content[:200]
                    log(f"   📥 Результат (~{result_tokens:,} токенов): {result_preview}...")
                    # Логируем полный результат в файл
                    log(f"\n--- РЕЗУЛЬТАТ ИНСТРУМЕНТА ---\n{result_content[:5000]}\n--- КОНЕЦ ---\n", to_console=False)
                    # Уточняем оценку контекста реальным размером результата
                    estimated_context_tokens += result_tokens - 3000  # Корректируем предварительную оценку
            
            # Обновляем оценку токенов
            estimated_output_tokens += step_output_tokens
            # Контекст растёт с каждым шагом
            estimated_context_tokens += step_output_tokens
            
            # Показываем статистику шага
            step_cost = calculate_cost(step_output_tokens, step_output_tokens)
            log(f"   💵 Шаг: ~{step_output_tokens:,} токенов (~${step_cost:.4f})")
                            
        elif isinstance(message, ResultMessage):
            if message.usage:
                input_tokens = message.usage.get("input_tokens", 0)
                output_tokens = message.usage.get("output_tokens", 0)
                step_cost = calculate_cost(input_tokens, output_tokens)
                total_input_tokens = input_tokens  # Финальные реальные значения
                total_output_tokens = output_tokens
                
                log("")
                log(f"   📊 ФИНАЛ: {input_tokens:,} in / {output_tokens:,} out (${step_cost:.4f})")
            
            # Пробуем извлечь финальный результат
            if message.result and not final_result:
                try:
                    result_text = message.result
                    if "```json" in result_text:
                        json_start = result_text.find("```json") + 7
                        json_end = result_text.find("```", json_start)
                        if json_end > json_start:
                            json_str = result_text[json_start:json_end].strip()
                            final_result = json.loads(json_str)
                    elif result_text.strip().startswith("{"):
                        final_result = json.loads(result_text)
                except (json.JSONDecodeError, ValueError):
                    pass
    
    total_time = (datetime.now() - start_time).total_seconds()
    log("")
    log("-" * 60)
    log(f"✅ Агент завершил работу за {total_time:.0f} секунд")
    log("")
    
    # Используем реальные токены если есть, иначе оценку
    final_input = total_input_tokens if total_input_tokens > 0 else estimated_context_tokens
    final_output = total_output_tokens if total_output_tokens > 0 else estimated_output_tokens
    
    # Расчёт стоимости
    cost_input = final_input * OPUS_INPUT_PRICE
    cost_output = final_output * OPUS_OUTPUT_PRICE
    total_cost = cost_input + cost_output
    
    # Итоговый отчёт
    log("=" * 60)
    log("📊 ИТОГОВЫЙ ОТЧЁТ")
    log("=" * 60)
    log("")
    
    if final_result:
        risk_level = final_result.get("risk_level", "unknown")
        risk_emojis = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        risk_labels = {"green": "НИЗКИЙ", "yellow": "СРЕДНИЙ", "red": "ВЫСОКИЙ"}
        
        emoji = risk_emojis.get(risk_level, "❓")
        label = risk_labels.get(risk_level, "НЕИЗВЕСТНО")
        
        log(f"Уровень риска: {emoji} {label}")
        log(f"Очки: {final_result.get('total_score', '?')}")
        log("")
        
        triggered = final_result.get("triggered_criteria", [])
        if triggered:
            log("⚠️  Сработавшие критерии:")
            for t in triggered:
                log(f"   • {t.get('id', '?')}: {t.get('evidence', '')[:60]}...")
            log("")
            log("📝 Резюме:")
            log(f"   {final_result.get('summary', 'Нет данных')}")
            log("")
            log("💡 Рекомендация:")
            log(f"   {final_result.get('recommendation', 'Нет данных')}")
        else:
            log("✅ Сработавших критериев нет")
        
        # Важные тезисы (всегда показываем)
        key_insights = final_result.get('key_insights', [])
        if key_insights:
            log("")
            log("📝 Важные тезисы:")
            for insight in key_insights:
                log(f"   {insight}")
    else:
        log("⚠️  Не удалось получить структурированный результат от агента")
    
    log("")
    log("-" * 60)
    log("💰 СТАТИСТИКА")
    log("-" * 60)
    log(f"   ⏱️  Время работы: {total_time:.0f} секунд ({total_time/60:.1f} мин)")
    log(f"   📝 Шагов агента: {step_count}")
    log(f"   🔧 Вызовов инструментов: {tool_calls_count}/{search_limit}")
    final_context_percent = (estimated_context_tokens / CONTEXT_SOFT_LIMIT) * 100
    log(f"   📊 Контекст: ~{estimated_context_tokens:,}/{CONTEXT_SOFT_LIMIT:,} токенов ({final_context_percent:.0f}%)")
    is_estimate = total_input_tokens == 0
    prefix = "~" if is_estimate else ""
    log(f"   📥 Input токены: {prefix}{final_input:,}")
    log(f"   📤 Output токены: {prefix}{final_output:,}")
    log(f"   💵 Стоимость input: ${cost_input:.4f}")
    log(f"   💵 Стоимость output: ${cost_output:.4f}")
    log(f"   💰 ИТОГО: ${total_cost:.4f}" + (" (оценка)" if is_estimate else ""))
    log("=" * 60)
    
    return {
        "result": final_result,
        "stats": {
            "steps": step_count,
            "tool_calls": tool_calls_count,
            "time_seconds": total_time,
            "input_tokens": final_input,
            "output_tokens": final_output,
            "cost_usd": total_cost,
        }
    }


async def main():
    """Точка входа."""
    with Logger() as logger:
        logger.log(f"📁 Лог-файл: {logger.log_file}")
        
        result = await run_agent("criteria.json", logger)
        
        # Отправка в Telegram
        logger.log("")
        logger.log("📤 Отправка в Telegram...")
        report = format_telegram_report(result, result["stats"])
        await send_telegram_report(report)
        
        logger.log(f"📁 Лог сохранён: {logger.log_file}")
        
        return result


if __name__ == "__main__":
    asyncio.run(main())
