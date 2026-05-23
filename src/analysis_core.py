"""
Общие утилиты анализа: критерии, история прогонов, архив канала, промпт, экспорт.

Не зависит от Telegram и LLM-провайдера.
Telegram-специфичная часть (форматирование, отправка) — в Бот_репортер/telegram_publisher.py.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class Logger:
    """Логгер для записи в файл и консоль."""

    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = LOGS_DIR / f"run_{timestamp}.log"
        self._file = open(self.log_file, "w", encoding="utf-8")
        self.last_assistant_text = ""

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


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_preview(value: object, limit: int = 400) -> str:
    try:
        s = (
            value
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, default=str)
        )
    except Exception:
        s = str(value)
    s = s.replace("\n", "\\n")
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def _extract_first_json_object(text: str) -> dict | None:
    """Извлекает первый корректный JSON-объект из текста."""
    if not text:
        return None

    if "```json" in text:
        idx = 0
        while True:
            start = text.find("```json", idx)
            if start == -1:
                break
            start += len("```json")
            end = text.find("```", start)
            if end == -1:
                break
            candidate = text[start:end].strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            idx = end + 3

    in_str = False
    escape = False
    depth = 0
    start_pos = None
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start_pos = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_pos is not None:
                    candidate = text[start_pos: i + 1].strip()
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        start_pos = None
                        continue

    return None


def load_criteria(path: str = "criteria.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_criteria_for_prompt(criteria_data: dict) -> str:
    thresholds = criteria_data.get("thresholds", {})
    g = thresholds.get("green", {})
    y = thresholds.get("yellow", {})
    r = thresholds.get("red", {})
    header = (
        f"### ПОРОГИ RISK_LEVEL (использовать при выставлении risk_level и deposit_access_risk)\n"
        f"🟢 green (НИЗКИЙ): total_score {g.get('min', 0)}–{g.get('max', 11)}\n"
        f"🟡 yellow (СРЕДНИЙ): total_score {y.get('min', 12)}–{y.get('max', 24)}\n"
        f"🔴 red (ВЫСОКИЙ): total_score {r.get('min', 25)}+\n\n"
        f"### КРИТЕРИИ ДЛЯ ПРОВЕРКИ ({len(criteria_data['criteria'])} шт.)\n"
    )
    speed_label = {"fast": "⚡БЫСТРЫЙ", "medium": "📅СРЕДНИЙ", "slow": "🐢МЕДЛЕННЫЙ"}
    body = "\n".join(
        f"### {c['id']} (вес: {c['weight']}) [{speed_label.get(c.get('speed', 'medium'), '📅СРЕДНИЙ')}]\n"
        f"**{c['name']}**\n{c['description']}\nПоисковый запрос: `{c['search_query']}`\n"
        for c in criteria_data["criteria"]
    )
    return header + body


# ─────────────────────── Run history ────────────────────────

_default_history_path = Path(__file__).parent.parent / "runs_history.json"
RUNS_HISTORY_FILE = Path(os.getenv("RUNS_HISTORY_FILE", str(_default_history_path)))


def load_run_history() -> dict:
    if RUNS_HISTORY_FILE.exists():
        try:
            with open(RUNS_HISTORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"runs": []}


def get_last_run_info(history: dict) -> tuple[int, str | None, str | None, int | None]:
    runs = history.get("runs", [])
    if not runs:
        return 1, None, None, None
    last = runs[-1]
    return last["run_id"] + 1, last.get("timestamp"), last.get("risk_level"), last.get("total_score")


def save_run_result(
    history: dict,
    run_id: int,
    result: dict | None,
    stats: dict,
    criteria_file: str,
) -> None:
    from datetime import timezone

    entry = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "risk_level": (result or {}).get("risk_level", "unknown"),
        "total_score": (result or {}).get("total_score", 0),
        "triggered_ids": [t["id"] for t in ((result or {}).get("triggered_criteria") or [])],
        "criteria_file": criteria_file,
        "model": stats.get("model", ""),
        "cost_usd": stats.get("cost_usd", 0),
    }
    history.setdefault("runs", []).append(entry)
    try:
        with open(RUNS_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Не удалось сохранить историю прогонов: {e}")


def build_history_trend(history: dict, current_run_id: int, max_items: int = 5) -> str:
    runs = history.get("runs", [])
    if not runs:
        return ""
    emoji_map = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    items = [
        f"#{r['run_id']}{emoji_map.get(r.get('risk_level', ''), '❓')}{r.get('total_score', '?')}"
        for r in runs[-max_items:]
    ]
    return " → ".join(items)


# ─────────────────────── Channel archive ────────────────────────


def fetch_channel_archive(
    channel_url: str = "https://t.me/s/money_alert_ai",
    max_posts: int = 20,
) -> tuple[str, int]:
    import httpx as _httpx

    try:
        with _httpx.Client(follow_redirects=True, timeout=30.0, verify=False) as client:
            resp = client.get(
                channel_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            resp.raise_for_status()
            raw_html = resp.text
    except Exception as e:
        return f"Ошибка загрузки архива канала: {e}", 0

    posts = _parse_telegram_posts(raw_html)
    if not posts:
        return "Не удалось извлечь посты из архива канала.", 0

    posts = posts[-max_posts:]
    formatted = [f"[{p['date']}]\n{p['text']}" for p in posts]
    return "\n\n---\n\n".join(formatted), len(posts)


def _parse_telegram_posts(raw_html: str) -> list[dict]:
    from html import unescape as _unescape
    from datetime import datetime as _dt

    posts: list[dict] = []
    blocks = re.split(r'(?=<div[^>]*class="[^"]*tgme_widget_message_wrap)', raw_html)

    for block in blocks:
        text_m = re.search(
            r'<div[^>]*class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            block,
            re.DOTALL,
        )
        if not text_m:
            continue
        raw = text_m.group(1)
        text = re.sub(r"<br\s*/?>", "\n", raw)
        text = re.sub(r"<[^>]+>", "", text)
        text = _unescape(text).strip()
        if not text:
            continue
        date_str = ""
        date_m = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if date_m:
            try:
                dt = _dt.fromisoformat(date_m.group(1))
                date_str = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                date_str = date_m.group(1)
        posts.append({"text": text, "date": date_str})

    return posts


# ─────────────────────── Web export ────────────────────────


def _update_inline_data(data_path: Path, data: dict) -> None:
    index_path = data_path.parent / "index.html"
    if not index_path.exists():
        return
    try:
        import re as _re
        html = index_path.read_text(encoding="utf-8")
        new_json = json.dumps(data, ensure_ascii=False, indent=2)
        html, n = _re.subn(
            r'(<script id="report-data" type="application/json">).*?(</script>)',
            lambda m: m.group(1) + "\n" + new_json + "\n  " + m.group(2),
            html, flags=_re.DOTALL,
        )
        if n:
            index_path.write_text(html, encoding="utf-8")
            print(f"✅ index.html inline data updated (run_id={data.get('run_id')})")
    except Exception as e:
        print(f"⚠️ Failed to update index.html inline data: {e}")


def _auto_git_push(path: Path, data: dict) -> None:
    import subprocess
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(path.parent), capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return
        repo_root = r.stdout.strip()
        rel = path.relative_to(repo_root)
        index_rel = (path.parent / "index.html").relative_to(repo_root)

        run_id  = data.get("run_id", "?")
        risk    = data.get("risk_level", "?")
        score   = data.get("total_score", "?")
        ts      = datetime.now().strftime("%Y-%m-%d")
        msg     = f"auto: data.json {ts} (run #{run_id}, {risk}, {score} pts)"

        subprocess.run(["git", "add", str(rel), str(index_rel)], cwd=repo_root, check=True, timeout=10)
        commit = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=repo_root, capture_output=True, text=True, timeout=15,
        )
        if commit.returncode != 0:
            if "nothing to commit" in commit.stdout + commit.stderr:
                print("ℹ️ Git: нечего коммитить (data.json не изменился)")
                return
            print(f"⚠️ Git commit failed: {commit.stderr.strip()}")
            return
        push = subprocess.run(
            ["git", "push"], cwd=repo_root, capture_output=True, text=True, timeout=30,
        )
        if push.returncode == 0:
            print(f"✅ Git push: {msg}")
        else:
            print(f"⚠️ Git push failed: {push.stderr.strip()}")
    except Exception as e:
        print(f"⚠️ Git auto-push error: {e}")


def export_web_report(
    result: dict | None,
    stats: dict,
    criteria_data: dict,
    run_history: dict,
) -> None:
    export_path = os.getenv("EXPORT_WEB_JSON")
    if not export_path:
        return

    from datetime import timezone

    criteria_by_id = {c["id"]: c for c in criteria_data.get("criteria", [])}
    final = (result or {}).get("result") or result or {}

    triggered = []
    for t in final.get("triggered_criteria", []):
        cid = t.get("id", "")
        meta = criteria_by_id.get(cid, {})
        triggered.append({
            "id": cid,
            "name": meta.get("name", cid),
            "evidence": t.get("evidence", ""),
            "weight": meta.get("weight", 0),
            "confidence": t.get("confidence"),
        })

    criteria_registry = [
        {
            "id": c["id"],
            "name": c["name"],
            "search_query": c.get("search_query", ""),
            "weight": c.get("weight", 0),
            "speed": c.get("speed", "medium"),
        }
        for c in criteria_data.get("criteria", [])
    ]

    runs = run_history.get("runs", [])
    data = {
        "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "run_id": stats.get("run_id"),
        "risk_level": final.get("risk_level", "unknown"),
        "total_score": final.get("total_score", 0),
        "max_score": sum(c.get("weight", 0) for c in criteria_data.get("criteria", [])),
        "thresholds": criteria_data.get("thresholds", {}),
        "confidence": final.get("confidence"),
        "deposit_access_risk": final.get("deposit_access_risk", "green"),
        "triggered_criteria": triggered,
        "summary": final.get("summary", ""),
        "recommendation": final.get("recommendation", ""),
        "positive_trends": final.get("positive_trends", []),
        "negative_trends": final.get("negative_trends", []),
        "key_risks_6m": final.get("key_risks_6m", []),
        "asset_guidance": final.get("asset_guidance", []),
        "watchlist": final.get("watchlist", []),
        "sources": final.get("sources", []),
        "stats": {
            "steps": stats.get("steps", 0),
            "tool_calls": stats.get("tool_calls", 0),
            "time_seconds": stats.get("time_seconds", 0),
            "cost_usd": stats.get("cost_usd", 0),
            "model": stats.get("model", ""),
        },
        "history": [
            {
                "run_id": r["run_id"],
                "timestamp": r.get("timestamp", ""),
                "risk_level": r.get("risk_level", "unknown"),
                "total_score": r.get("total_score", 0),
            }
            for r in runs[-10:]
        ],
        "criteria_registry": criteria_registry,
    }

    try:
        path = Path(export_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Web report exported → {path}")
        _update_inline_data(path, data)
        _auto_git_push(path, data)
    except Exception as e:
        print(f"⚠️ Failed to export web report: {e}")


# ─────────────────────── System prompt ────────────────────────

SYSTEM_PROMPT = """Ты — аналитик макроэкономических и финансовых рисков России. Твоя задача — по новостному фону и официальным данным оценить, к чему идёт экономика РФ (негативные и позитивные тенденции) и каков риск кризисного сценария на горизонте 6 месяцев.

📅 **Сейчас: {today_date}** | 🔢 **Прогон №{run_id}**

## 📊 КОНТЕКСТ ПРОГОНА

{last_run_info}

## ⏱️ ВРЕМЕННЫЕ ОКНА ДЛЯ ПОИСКА

Каждый критерий помечен меткой скорости. Используй РАЗНЫЕ горизонты поиска:

- ⚡ **БЫСТРЫЙ** — ищи события **{fast_window}**
  → Цель: что НОВОГО случилось с момента прошлого прогона, а не текущее состояние
- 📅 **СРЕДНИЙ** — ищи текущее состояние и тренды за **последние 30 дней**
- 🐢 **МЕДЛЕННЫЙ** — ищи последние официальные данные за **квартал/месяц**

## ⚠️ ЛИМИТЫ

### Лимит поисков: {search_limit}
- Максимум **{search_limit} поисков**
- Группируй похожие критерии в один поиск
- После {search_limit} поисков — СТОП поиски!

**Правило:** Если лимит исчерпан — прекращай поиски и выдавай финальный JSON!

## ТВОИ ИНСТРУМЕНТЫ
- WebSearch: поиск актуальных новостей в интернете
- WebFetch: загрузка содержимого страницы по URL

## 🚨 ШАГ 0: ЗАГРУЗКА АРХИВА (САМЫЙ ПЕРВЫЙ ШАГ!)

**Если архив канала уже есть в сообщении пользователя — НЕ загружай его через WebFetch повторно.**
Если архива нет — тогда загрузи архив канала:

```
WebFetch: https://t.me/s/money_alert_ai
```

После загрузки архива ты ОБЯЗАН:
1. **Выписать темы последних 5-7 постов** — какие тезисы уже были опубликованы
2. **Запомнить "запрещённые темы"** — то, что нельзя повторять (если было недавно — ищи новые углы/индикаторы)

**⚠️ КРИТИЧЕСКИ ВАЖНО:** Каждый пост должен содержать НОВЫЕ тезисы! Читатели видят все посты подряд — повторы недопустимы!

## 📋 ШАГ 1: ПЛАНИРОВАНИЕ

**ПЕРЕД первым поиском** проанализируй все критерии и сгруппируй их по темам:

1. **Изучи все критерии** и найди пересечения
2. **Создай группы** похожих критериев для одного поиска:
   - Группа "Долг и бюджет": дефицит, заимствования, ОФЗ
   - Группа "ДКП и инфляция": инфляция, ожидания, меры ЦБ
   - Группа "Курс и внешние условия": рубль, FX‑ограничения, экспорт/санкции
   - Группа "Банки и кредитный цикл": санации, лицензии, просрочки
   - Группа "Реальная экономика": рынок труда, ипотека/стройка, дефолты компаний
3. **Начни с критичных** (вес 20-12) — они важнее всего!

## 🧠 ЭТАП ДО: РАССУЖДЕНИЕ ПЕРЕД ПОИСКАМИ (НЕ ВЫВОДИТЬ)

Перед тем как вызывать инструменты, сделай короткий внутренний pre‑mortem: что именно ты должен доказать/опровергнуть, и как не ошибиться.

```
ВНУТРЕННИЙ PRE‑MORTEM (НЕ ВЫВОДИТЬ):
1) Для каждой группы критериев:
   - какие 1–2 индикатора подтвердят срабатывание
   - какие 1–2 индикатора опровергнут/снизят вероятность
2) План доказательств:
   - предпочитай официальные данные/регуляторов/статведомств; иначе ≥2 независимых источника
3) Риски ложных срабатываний:
   - перепечатки/старые новости, будущие события, заявления без цифр, единичные кейсы без масштаба
4) Если в группе нет надёжных данных — заранее пометь её как "скорее НЕ сработало" и ищи подтверждение, а не подгоняй вывод.
```

## ПРАВИЛА РАБОТЫ
1. **ШАГ 0 — АРХИВ:** Первым делом загрузи https://t.me/s/money_alert_ai и выпиши темы последних постов
2. **ШАГ 1 — ПЛАН:** Составь план группировки критериев
3. **ШАГ 2 — ПОИСКИ:** Делай поиски по плану
4. **⚠️ ПРОВЕРЯЙ ДАТЫ И ВРЕМЯ!** В поиске часто попадаются старые и будущие новости:
   - Для трендов релевантны материалы за **последние 30 дней**, но приоритет — **последние 7-14 дней**
   - ОБЯЗАТЕЛЬНО смотри дату (и время, если важно)
   - Если событие назначено на ПОЗЖЕ текущего времени — оно ЕЩЁ НЕ ПРОИЗОШЛО, не включай!
   - Игнорируй: фейки, прогнозы без источников, анонсы будущих событий (как факт)
5. **Оценивай честно**: при сомнениях — критерий НЕ сработал
6. **ПЕРЕД JSON** — сверь positive_trends/negative_trends/key_risks_6m с архивом, убедись что темы НОВЫЕ
7. **Финализацию (JSON) выдавай только когда реально проверил все критерии.**
   - В `checked_criteria` должны быть перечислены **все** `id` из списка критериев.
   - Если ты не уверен, что проверил какой-то критерий — продолжай WebSearch, пока не будешь уверен.
   - Если по критерию нет подтверждений — он всё равно считается проверенным (просто не попадает в triggered).
8. **После {search_limit} поисков** — СТОП! Выдай финальный JSON

## ⚙️ ОГРАНИЧЕНИЕ НА ИНСТРУМЕНТЫ (КРИТИЧНО ДЛЯ КОНТЕКСТА)

- В одном сообщении ассистента делай **не более 8 вызовов** инструментов суммарно (WebSearch + WebFetch).
- Если нужно больше — остановись, коротко перечисли что уже нашёл/что осталось, и продолжай в следующем сообщении.

## 🧠 ФИНАЛЬНЫЙ ШАГ: ГЛУБОКИЙ АНАЛИЗ (ОБЯЗАТЕЛЬНО!)

**ПЕРЕД выдачей JSON** ты ОБЯЗАН провести структурированное рассуждение и самопроверку в 2 прохода,
НО **НЕ ВЫВОДИ** её в ответ (это раздувает контекст). Используй это только для качества финального вывода.

```
ПРОХОД 1 — ВНУТРЕННИЙ АНАЛИЗ (НЕ ВЫВОДИТЬ):
1) Что показали поиски (3-5 ключевых находок)
2) Скрытые тенденции/механизмы передачи (банки ↔ стройка ↔ бюджет ↔ курс ↔ спрос)
3) Контраргументы (почему я мог ошибаться / альтернативные объяснения)
4) Проверка источников: у каждого факта есть [N] и URL в sources
5) Уникальность: не повторяю темы последних постов канала
6) Действия с активами: без паники, без приказов, кратко и практично

ПРОХОД 2 — POST‑MORTEM И ВАЛИДАЦИЯ (НЕ ВЫВОДИТЬ):
7) Я сформировал ЧЕРНОВИК JSON и проверил:
   - `checked_criteria` содержит ВСЕ id критериев (ничего не пропущено)
   - у каждого факта/тезиса есть ссылка [N], и в `sources` есть соответствующий URL
   - длины: summary ≤ 220, recommendation ≤ 170, evidence ≤ 120, пункты трендов/рисков/активов ≤ 120, watchlist ≤ 100
   - total_score = сумма весов triggered_criteria; risk_level выставляется СТРОГО по порогам из раздела "ПОРОГИ RISK_LEVEL" в начале блока критериев
8) Если хоть один пункт нарушен — исправь черновик и проверь заново. В ответе выводи только финальный валидный JSON.
```

⚠️ **ВАЖНО:** В финальном ответе выдай **ТОЛЬКО** JSON-объект (без markdown и без текста вокруг).

## 📏 ЛИМИТЫ ДЛИНЫ (КРИТИЧНО — Telegram обрезает длинные сообщения!)

Итоговый отчёт отправляется в Telegram, где лимит сообщения — 4096 символов. Поэтому:
- **evidence** в triggered_criteria: **макс 120 символов** (только ключевой факт + [N])
- **summary**: макс 220 символов
- **recommendation**: макс 170 символов
- Пункты в positive_trends, negative_trends, key_risks_6m, asset_guidance: **макс 120 символов** каждый
- watchlist: макс 100 символов каждый
- positive_trends и negative_trends: **макс 2 пункта** каждый
- key_risks_6m: **макс 2 пункта**
- watchlist: **макс 3 пункта**
- asset_guidance: **макс 3 пункта**
- **Будь лаконичен!** Один факт — одна цифра — одна ссылка. Не перечисляй всё найденное.

## 📎 ИСТОЧНИКИ (ОБЯЗАТЕЛЬНО!)

Каждый факт в evidence, positive_trends, negative_trends, key_risks_6m, summary и asset_guidance ДОЛЖЕН иметь ссылку [N] на источник.
- В поле "sources" перечисли все URL из результатов WebSearch, на которые ссылаешься
- Нумерация сквозная: [1], [2], [3]...
- Если для факта нет подтверждённого URL — не ссылайся

### 🚫 ФИЛЬТРАЦИЯ ИСТОЧНИКОВ (КРИТИЧНО!)

В финальный JSON (поле `sources` и ссылки [N] в текстовых полях) **включай ТОЛЬКО** ссылки на ресурсы в доменной зоне **.ru**.

**НЕ включай** в `sources` и не ссылайся [N] на:
- Ресурсы вне зоны .ru (bloomberg.com, reuters.com, ft.com, bbc.com и т.д.)
- СМИ, признанные иноагентами по законодательству РФ

## ФОРМАТ ИТОГА

```json
{{
  "checked_criteria": ["id1", "id2", ...],
  "triggered_criteria": [
    {{"id": "criterion_id", "evidence": "что именно произошло, до 120 символов [1]", "confidence": 0.9}}
  ],
  "total_score": <сумма весов сработавших критериев>,
  "risk_level": "green/yellow/red",
  "confidence": "high/medium/low",
  "deposit_access_risk": "green/yellow/red",
  "summary": "1-2 предложения, МАКС 220 символов",
  "recommendation": "1 предложение, МАКС 170 символов",
  "asset_guidance": [
    "Вклады: кратко (МАКС 120 символов) [8]",
    "Наличность: кратко (МАКС 120 символов) [9]",
    "Валюта/недвижимость: кратко (МАКС 120 символов) [10]"
  ],
  "positive_trends": [
    "Позитивный тренд (МАКС 120 символов) [2]",
    "Позитивный тренд (МАКС 120 символов) [3]"
  ],
  "negative_trends": [
    "Негативный тренд (МАКС 120 символов) [4]",
    "Негативный тренд (МАКС 120 символов) [5]"
  ],
  "key_risks_6m": [
    "Риск на 6м (МАКС 120 символов) [6]",
    "Риск на 6м (МАКС 120 символов) [7]"
  ],
  "watchlist": [
    "Что мониторить (МАКС 100 символов)",
    "Что мониторить (МАКС 100 символов)",
    "Что мониторить (МАКС 100 символов)"
  ],
  "sources": [
    {{"id": 1, "url": "https://..."}},
    {{"id": 2, "url": "https://..."}}
  ]
}}
```

## 🧾 ПРАКТИЧЕСКАЯ ЧАСТЬ ПРО АКТИВЫ (ОБЯЗАТЕЛЬНО!)

Ты ОБЯЗАН дать практическую секцию по активам, но аккуратно и без паники:

- Выведи `deposit_access_risk` (green/yellow/red) — риск ухудшения доступа к вкладам/платежам на горизонте 1–3 месяца
- Заполни `asset_guidance` (3 пункта): вклады/ликвидность/диверсификация, валютные и операционные риски, недвижимость/риски отрасли
- НЕ давай категоричных приказов "покупай/продавай". Используй: "имеет смысл рассмотреть", "если ваша цель — снизить риск...", "можно подумать о..."

### Контекст: топ-10 банков и логика "too big to fail"

При оценке `deposit_access_risk`:
- **Топ-10 банков РФ (Сбер, ВТБ, Газпромбанк, Россельхозбанк, Альфа, Т-Банк, МКБ, ПСБ и др.) де-факто являются "too big to fail"**
- **Лимит АСВ:** 1,4 млн руб. на вкладчика на банк
- Повышай `deposit_access_risk` до yellow/red только при срабатывании критериев `systemic_bank_resolution`, `bank_holidays_national`, `payment_infrastructure_systemic_disruption` или `interbank_liquidity_stress`

## КРИТЕРИИ ДЛЯ ПРОВЕРКИ

{criteria}

---
Начни с ПЛАНИРОВАНИЯ, затем выполняй поиски. Лимит: {search_limit}.
"""
