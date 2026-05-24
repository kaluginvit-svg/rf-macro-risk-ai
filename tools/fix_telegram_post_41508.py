from __future__ import annotations

from pathlib import Path

import httpx
from dotenv import dotenv_values


BOT_DIR = Path(r"C:\_Рабочая_папка\Проекты_программирование\Бот_репортер")


def main() -> None:
    cfg = dotenv_values(BOT_DIR / ".env")
    token = cfg.get("TELEGRAM_BOT_TOKEN")
    chat_id = cfg.get("TELEGRAM_CHANNEL_ID")
    msg_id = int(cfg.get("TELEGRAM_EDIT_MSG_ID") or 41508)
    if not token or not chat_id:
        raise SystemExit("missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID")

    report = """<b>Макро-обзор РФ | 23.05.2026</b>
<i>Full-pass: fast 18/18 · medium 13/13 · slow 4/4</i>

Риск кризисного сценария (6м): 🔴 <b>ВЫСОКИЙ</b>
Очки: <b>70</b> / 330 <i>(27+ = красная зона)</i>
Риск доступа к вкладам (1–3м): 🟡 <b>СРЕДНИЙ</b>
Уверенность: medium

⚠️ <b>Сработавшие критерии (11):</b>
<blockquote expandable>• <b>Широкомасштабные перебои платёжной инфраструктуры</b> [9]: ЦБ фиксировал сбой обмена платежной информацией с банками 8 мая <a href="https://amp.rbc.ru/rbcnews/finances/08/05/2026/69fe2ab29a7947670d3e3409">[1]</a>
• <b>Волна корпоративных дефолтов</b> [8]: за неделю 18–22 мая зафиксированы 24 дефолта/техдефолта по корпоративным облигациям <a href="https://ru.investing.com/news/general-news/article-3249640">[2]</a>
• <b>Новые санкции по торговле/финансам</b> [8]: ЕС ввёл транзакционные ограничения против 20 российских банков <a href="https://www.finmarket.ru/news/6607029">[3]</a>
• <b>Системный рост проблемных кредитов</b> [8]: просрочка по корпоративным кредитам выросла до 3,0 трлн руб.; доля 3,6% <a href="https://cbr.ru/statistics/bank_sector/sors/credit/">[4]</a>
• <b>Экстренное ухудшение бюджетных параметров</b> [6]: дефицит бюджета за январь–апрель достиг 5,877 трлн руб. <a href="https://rg.ru/2026/05/08/deficit-federalnogo-biudzheta-v-pervye-mesiacy-etogo-goda-dostig-587-trln-rublej.html">[5]</a>
• <b>Резкий рост банкротств физлиц</b> [6]: в I кв. банкротами признаны 137,5 тыс. граждан, выше 30 тыс. в месяц <a href="https://www.kommersant.ru/doc/8674989">[6]</a>
• <b>Задолженность по зарплате</b> [5]: на конец марта долги по зарплате 2,13 млрд руб., +47,1% г/г <a href="https://rosstat.gov.ru/storage/mediabank/57_22-04-2026.html">[7]</a>
• <b>Стресс потребкредитования</b> [5]: доля просрочки в розничном портфеле близка к максимумам последних лет <a href="https://www.banki.ru/news/lenta/?id=11022995">[8]</a>
• <b>Стресс ипотеки/недвижимости</b> [5]: ипотечная просрочка растёт, ЦБ ужесточает макропруденциальные условия <a href="https://investfuture.ru/articles/tsentrobank-uzhestochaet-usloviya-ipoteki-na-fone-rosta-prosrochek-v-2026-godu-1179072420">[9]</a>
• <b>Финансовый стресс регионов</b> [5]: Минфин ждёт дефицит региональных бюджетов около 1,9 трлн руб. <a href="https://www.kommersant.ru/doc/8623726">[10]</a>
• <b>Ухудшение внешнеторговых условий</b> [5]: профицит текущего счёта снизился, импорт растёт быстрее экспорта <a href="https://www.cbr.ru/press/event/?id=28542">[11]</a></blockquote>

📝 Полный проход 35/35 показывает красную зону не из-за одного шока, а из-за наложения бюджетного, кредитного, санкционного и платёжного стрессов.

🟢 <b>Позитивные тенденции:</b>
  • Недельная инфляция 13–18 мая: 99,98%, с начала года 103,15% — без нового ускорения <a href="https://www.rosstat.gov.ru/storage/mediabank/72_20-05-2026.html">[12]</a>
  • Ставка снижена до 14,5%, инфляционные ожидания в апреле снизились до 12,9% <a href="https://www.cbr.ru/press/event/?id=28513">[13]</a>

🔴 <b>Негативные тенденции:</b>
  • Дефицит бюджета за 4 месяца уже выше годового плана, давление на заимствования сохраняется <a href="https://rg.ru/2026/05/08/deficit-federalnogo-biudzheta-v-pervye-mesiacy-etogo-goda-dostig-587-trln-rublej.html">[5]</a>
  • Санкции бьют по банкам и расчётам, то есть по операционному контуру экономики <a href="https://www.finmarket.ru/news/6607029">[3]</a>

⚠️ <b>Риски на 6 месяцев:</b>
  • Дальнейший рост дефолтов в корпоративном долге при дорогом рефинансировании <a href="https://ru.investing.com/news/general-news/article-3249640">[2]</a>
  • Повторные сбои платежной инфраструктуры могут поднять риск доступа к деньгам до красного <a href="https://amp.rbc.ru/rbcnews/finances/08/05/2026/69fe2ab29a7947670d3e3409">[1]</a>

👀 <b>Watchlist:</b>
  • Заседание ЦБ 19.06.2026
  • Бюджет за май и нефтегазовые доходы
  • Повторные сбои СБП/карт/клиринга
  • ОФЗ и РЕПО: пока watch, не триггер

——
⏱ агентский full-pass · 🔍 35 критериев · источники: пост 13 / аудит 31
<i>Не является инвестиционной рекомендацией.</i>"""

    print(f"report length: {len(report)}")
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": report,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    verify_ssl = str(cfg.get("TELEGRAM_VERIFY_SSL", "1")).lower() not in {"0", "false", "no"}
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    with httpx.Client(verify=verify_ssl, timeout=30) as client:
        resp = client.post(url, json=payload)
    print(resp.status_code)
    print(resp.text[:500])
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise SystemExit(1)
    print(f"edited message {msg_id}")


if __name__ == "__main__":
    main()
