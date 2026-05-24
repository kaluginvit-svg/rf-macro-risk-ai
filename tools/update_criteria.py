"""Script to update criteria.json and criteria_small.json with new recalibration fields."""
import json
from pathlib import Path

# ── Role assignments ──
ROLES = {
    "force_majeure_state_event": "shock",
    "sovereign_domestic_debt_event": "shock",
    "bank_holidays_national": "shock",
    "cb_emergency_rate_hike": "shock",
    "moex_trading_halt": "shock",
    "systemic_bank_resolution": "shock",
    "cb_emergency_actions_fin_stability": "shock",
    "new_fx_controls_severe": "shock",
    "bank_license_chain_or_large": "shock",
    "deposit_outflow_mass": "leading",
    "payment_infrastructure_systemic_disruption": "leading",
    "cash_m0_surge": "leading",
    "corporate_default_wave": "leading",
    "wage_arrears": "leading",
    "new_sanctions_trade_finance": "leading",
    "cbr_repo_volume_spike": "leading",
    "cash_fx_premium_spike": "leading",
    "banking_npl_systemic_rise": "leading",
    "deposit_rate_spread_spike": "leading",
    "ofz_yield_curve_inversion_spike": "leading",
    "interbank_liquidity_stress": "leading",
    "ruble_depreciation_shock": "leading",
    "ofz_market_stress": "leading",
    "household_credit_stress": "leading",
    "mortgage_real_estate_stress": "leading",
    "personal_bankruptcy_surge": "leading",
    "budget_emergency_amendments": "leading",
    "inflation_reacceleration": "context",
    "labor_market_deterioration": "context",
    "regional_finance_crisis": "context",
    "external_trade_deterioration": "context",
    "oil_price_shock_urals": "context",
    "rzd_freight_collapse": "context",
    "retail_sales_real_decline": "context",
    "industrial_output_contraction": "context",
}

# ── triggers_black ──
TRIGGERS_BLACK = {
    "force_majeure_state_event",
    "sovereign_domestic_debt_event",
    "bank_holidays_national",
    "moex_trading_halt",
    "cb_emergency_rate_hike",
}

# ── cooldown_days ──
COOLDOWN_DAYS = {
    "force_majeure_state_event": 0,
    "sovereign_domestic_debt_event": 0,
    "bank_holidays_national": 14,
    "cb_emergency_rate_hike": 14,
    "moex_trading_halt": 14,
    "systemic_bank_resolution": 14,
    "cb_emergency_actions_fin_stability": 14,
    "new_fx_controls_severe": 14,
    "bank_license_chain_or_large": 14,
    "deposit_outflow_mass": 14,
    "payment_infrastructure_systemic_disruption": 14,
    "cash_m0_surge": 14,
    "cbr_repo_volume_spike": 14,
    "cash_fx_premium_spike": 14,
    "deposit_rate_spread_spike": 14,
    "ofz_yield_curve_inversion_spike": 14,
    "ruble_depreciation_shock": 14,
    "corporate_default_wave": 21,
    "wage_arrears": 21,
    "new_sanctions_trade_finance": 21,
    "banking_npl_systemic_rise": 21,
    "interbank_liquidity_stress": 21,
    "ofz_market_stress": 21,
    "household_credit_stress": 21,
    "mortgage_real_estate_stress": 21,
    "personal_bankruptcy_surge": 21,
    "budget_emergency_amendments": 21,
    "inflation_reacceleration": 30,
    "labor_market_deterioration": 30,
    "regional_finance_crisis": 30,
    "external_trade_deterioration": 30,
    "oil_price_shock_urals": 30,
    "rzd_freight_collapse": 30,
    "retail_sales_real_decline": 30,
    "industrial_output_contraction": 30,
}

_SHOCK_LEVELS = {
    "watch": "Неофициальные сигналы/слухи, обсуждения без официального решения",
    "warming_up": "Официальные подготовительные действия или промежуточные решения без окончательного вступления в силу",
    "triggered": "Официальное решение принято и вступило в силу",
    "critical": "Официальное решение с немедленными системными последствиями для финансовой системы",
}

SEVERITY_LEVELS = {
    "force_majeure_state_event": {
        "watch": "Обсуждения/слухи об экстраординарных мерах без официального решения",
        "warming_up": "Официальные подготовительные меры (мобилизационные документы, указы без объявления ЧП)",
        "triggered": "Официально объявлено: военное положение/ЧП/смена власти/ядерный инцидент/столкновение с НАТО",
        "critical": "Одновременно несколько системных событий с прямым влиянием на финансовую систему",
    },
    "sovereign_domestic_debt_event": {
        "watch": "Слухи/неофициальные сигналы о затруднениях с обслуживанием ОФЗ",
        "warming_up": "Официальные консультации или поручения о пересмотре условий внутреннего долга",
        "triggered": "Официальное решение о реструктуризации/переносе выплат/принудительном обмене ОФЗ",
        "critical": "Реструктуризация вступила в силу, рынок ОФЗ заморожен, держатели несут потери",
    },
    "bank_holidays_national": _SHOCK_LEVELS,
    "cb_emergency_rate_hike": {
        "watch": "Слухи/обсуждения внепланового повышения ставки, неофициальные заявления",
        "warming_up": "ЦБ публично сигнализирует о готовности к экстренным мерам, объявлено о созыве внепланового заседания",
        "triggered": "Внеплановое заседание ЦБ проведено, ставка повышена немедленно",
        "critical": "Ставка поднята на 5+ п.п. за одно решение (как 28.02.2022: 9,5% -> 20%)",
    },
    "moex_trading_halt": _SHOCK_LEVELS,
    "systemic_bank_resolution": {
        "watch": "Неофициальные сообщения/слухи о проблемах крупного банка без подтверждения ЦБ",
        "warming_up": "ЦБ проводит проверку, стресс-тест или экстренные переговоры с банком",
        "triggered": "Официально начата санация/введена временная администрация в крупном банке",
        "critical": "Санация системно значимого банка с немедленным ограничением доступа клиентов",
    },
    "cb_emergency_actions_fin_stability": {
        "watch": "ЦБ публично предупреждает о рисках финансовой стабильности",
        "warming_up": "ЦБ объявляет о внеплановых мерах поддержки или созывает внеплановое заседание",
        "triggered": "Внеплановое заседание ЦБ состоялось, приняты экстренные меры по финстабильности",
        "critical": "Системный пакет чрезвычайных мер с прямым эффектом на доступность денег",
    },
    "new_fx_controls_severe": {
        "watch": "Обсуждение/слухи о новых валютных ограничениях без официального решения",
        "warming_up": "Опубликованы проекты нормативных актов или официально анонсированы меры",
        "triggered": "Новые валютные ограничения официально введены и вступили в силу",
        "critical": "Полный запрет или фактическая заморозка валютных операций для физлиц/компаний",
    },
    "bank_license_chain_or_large": {
        "watch": "Слухи/неофициальные сигналы об отзыве лицензии у крупного банка",
        "warming_up": "ЦБ публично предупреждает банк или начинает проверку без решения об отзыве",
        "triggered": "Официальный отзыв лицензии у заметного банка или 2+ отзыва за 2 недели",
        "critical": "Цепочка 3+ отзывов за месяц или отзыв у банка с розничной базой 500к+ клиентов",
    },
    "deposit_outflow_mass": {
        "watch": "Данные ЦБ показывают снижение вкладов на 1-3% за месяц или отдельные заявления банков",
        "warming_up": "Снижение вкладов на 3-5% за месяц или официальные заявления ЦБ о повышенном оттоке",
        "triggered": "Сокращение совокупного портфеля вкладов физлиц на 5%+ за месяц или 3%+ за 2 месяца подряд",
        "critical": "Отток превысил 10% за месяц или нарастающая динамика паники со СМИ-подтверждением",
    },
    "payment_infrastructure_systemic_disruption": {
        "watch": "Единичные сообщения о перебоях в СБП/картах, неподтверждённые НСПК/ЦБ",
        "warming_up": "Несколько независимых подтверждений перебоев, НСПК/ЦБ выпустили официальное уведомление",
        "triggered": "Системные перебои СБП/карт/межбанка подтверждены НСПК/ЦБ, затронули несколько регионов",
        "critical": "Межбанковские расчёты/СБП не работают более 4 часов по всей стране",
    },
    "cash_m0_surge": {
        "watch": "М0 вырос на 2-5% за месяц, но без одновременного сокращения депозитов",
        "warming_up": "М0 вырос на 5-10% за месяц или на 300-500 млрд руб., возможно при сокращении депозитов",
        "triggered": "М0 вырос на 5%+ за месяц при одновременном сокращении депозитов, ЦБ подтверждает рост спроса на наличные",
        "critical": "М0 вырос на 10%+ за месяц или более 500 млрд руб. за месяц на фоне паники и пустых банкоматов",
    },
    "corporate_default_wave": {
        "watch": "1-3 дефолта по облигациям за месяц без явной системности",
        "warming_up": "3-9 дефолтов или реструктуризаций за месяц в 1-2 секторах",
        "triggered": "10+ дефолтов/реструктуризаций за месяц ИЛИ 3+ сектора затронуты одновременно",
        "critical": "Волна дефолтов охватила системно важные эмитенты, рынок облигаций заморожен",
    },
    "wage_arrears": {
        "watch": "Единичные сообщения о задержках зарплаты в 1-2 компаниях/регионах",
        "warming_up": "Официальная статистика Росстата фиксирует рост задолженности по зарплате на 20%+ г/г",
        "triggered": "Системные задержки в 5+ регионах/отраслях, подтверждённые официальными источниками",
        "critical": "Федеральный реестр задолженности по зарплате показывает новый исторический максимум",
    },
    "new_sanctions_trade_finance": {
        "watch": "Обсуждения/угрозы новых санкций без их официального введения",
        "warming_up": "Санкции официально объявлены, но ещё не вступили в силу",
        "triggered": "Новые санкции введены и уже влияют на расчёты/экспорт/клиринг",
        "critical": "Санкции против системных банков или полная блокировка расчётного канала",
    },
    "cbr_repo_volume_spike": {
        "watch": "Объём РЕПО с ЦБ вырос в 1,5-2x относительно месячного среднего",
        "warming_up": "Объём РЕПО с ЦБ вырос в 2-3x, держится 3+ рабочих дня вне налогового периода",
        "triggered": "Объём РЕПО с ЦБ вырос в 3x+ относительно скользящего среднего за 4 недели",
        "critical": "Объём РЕПО с ЦБ в 5x+ от среднего устойчиво, межбанк де-факто заморожен",
    },
    "cash_fx_premium_spike": {
        "watch": "Наличный курс превышает официальный на 5-10% в 1-2 банках",
        "warming_up": "Наличный курс превышает официальный на 10-15% в большинстве крупных банков",
        "triggered": "Наличный курс устойчиво превышает официальный на 15%+ в топ-5 банках 3+ рабочих дня",
        "critical": "Наличный курс превышает официальный на 30%+ (как февраль 2022: спред до 50%+)",
    },
    "banking_npl_systemic_rise": {
        "watch": "Доля NPL 5-8% или рост на 1-2 п.п. за квартал",
        "warming_up": "Доля NPL 8-10% или рост более 1,5 п.п. за квартал",
        "triggered": "Доля NPL более 8% ИЛИ рост более 2 п.п. за квартал по данным ЦБ",
        "critical": "Доля NPL более 12% или резкое ускорение роста без видимой причины замедления",
    },
    "deposit_rate_spread_spike": {
        "watch": "Спред ставок по вкладам к ключевой 2-4 п.п. в нескольких банках",
        "warming_up": "Спред 4-5 п.п. устойчиво в 5+ банках из топ-20",
        "triggered": "Спред 5+ п.п. устойчиво в 5+ банках из топ-20 в течение 5+ рабочих дней",
        "critical": "Спред 8+ п.п. или обвал предложений по длинным вкладам",
    },
    "ofz_yield_curve_inversion_spike": {
        "watch": "Спред 1-3 п.п. между короткими и длинными ОФЗ, динамика нарастает",
        "warming_up": "Спред 3-5 п.п. или рост на 3 п.п. за 10 рабочих дней",
        "triggered": "Спред 5+ п.п. ИЛИ рост на 3+ п.п. за 10 рабочих дней на фоне ухудшения других индикаторов",
        "critical": "Спред 8+ п.п. или резкая разница аукционных доходностей без объяснения ЦБ",
    },
    "interbank_liquidity_stress": {
        "watch": "RUONIA выше ключевой ставки на 0,5-1 п.п. более 3 дней вне налогового периода",
        "warming_up": "RUONIA выше ключевой на 1-2 п.п. устойчиво более недели",
        "triggered": "RUONIA или MosPrime устойчиво выше ключевой на 2+ п.п., межбанк сжат",
        "critical": "Банки не могут привлечь ликвидность на рынке, ЦБ вынужден вмешиваться экстренно",
    },
    "ruble_depreciation_shock": {
        "watch": "Рубль ослаб на 5-10% за неделю, расширился спред наличного курса",
        "warming_up": "Рубль ослаб на 10-20% за 2 недели или расширение двухкурсовости до 10-15%",
        "triggered": "Рубль ослаб на 20%+ за 2 недели ИЛИ устойчивое расширение спреда наличного к биржевому до 15%+",
        "critical": "Рубль ослаб на 40%+ (как февраль 2022: 75->110+), валютная паника",
    },
    "ofz_market_stress": {
        "watch": "1-2 слабых аукциона или рост доходностей на 0,5-1 п.п. за 2 недели",
        "warming_up": "Серия отказов от аукционов или рост доходностей на 1-2 п.п. за 2 недели",
        "triggered": "3+ отмены/провала аукционов за месяц или рост доходностей на 2+ п.п. за месяц",
        "critical": "Минфин полностью прекращает размещения, рынок ОФЗ парализован",
    },
    "household_credit_stress": {
        "watch": "Рост просрочки по розничным кредитам на 10-20% г/г или единичные банки ужесточают выдачу",
        "warming_up": "Рост просрочки на 20-30% г/г или несколько банков синхронно сужают лимиты",
        "triggered": "Рост просрочки более 30% г/г ИЛИ NPL розницы достигает 5-летнего максимума",
        "critical": "Рост просрочки более 50% г/г и одновременный обвал выдач кредитов",
    },
    "mortgage_real_estate_stress": {
        "watch": "Выдачи ипотеки снизились на 10-30% г/г или просрочка по ипотеке выросла на 0,5-1 п.п.",
        "warming_up": "Выдачи упали на 30-50% г/г, несколько застройщиков получили кассовый разрыв",
        "triggered": "Выдачи упали более 50% г/г ИЛИ 3+ крупных застройщика заморозили проекты/банкротятся",
        "critical": "Системный кризис ипотеки: банки прекращают выдачи, эскроу массово разморожены",
    },
    "personal_bankruptcy_surge": {
        "watch": "Рост банкротств физлиц на 20-40% г/г за один месяц (ниже 30 000/мес)",
        "warming_up": "Рост банкротств на 40%+ г/г или выход на 25 000-30 000/мес",
        "triggered": "Более 30 000 процедур/мес ИЛИ рост более 40% г/г два месяца подряд",
        "critical": "Более 50 000 процедур/мес или нарастающая цепочка рекордов без торможения",
    },
    "budget_emergency_amendments": {
        "watch": "Минфин сигнализирует о плановом уточнении с небольшим ростом дефицита",
        "warming_up": "Внесены поправки, увеличивающие дефицит или заимствования на 15-30% от плана",
        "triggered": "Экстренные поправки с ростом дефицита 30%+ от плана или срочной риторикой",
        "critical": "Дефицит пересматривается дважды за квартал или секвестр расходов объявлен официально",
    },
    "inflation_reacceleration": {
        "watch": "Недельная инфляция выше 0,3% или инфляционные ожидания населения выросли на 1 п.п.",
        "warming_up": "Месячная инфляция выше 1% или инфляционные ожидания достигли 15%+",
        "triggered": "Годовая инфляция ускорилась с тренда снижения ИЛИ ЦБ пересматривает прогноз вверх",
        "critical": "Годовая инфляция выше 15% или ЦБ явно сигнализирует о потере контроля над инфляцией",
    },
    "labor_market_deterioration": {
        "watch": "Безработица выросла на 0,5 п.п. г/г или единичные крупные сокращения в 1-2 регионах",
        "warming_up": "Безработица выросла на 1 п.п. г/г или системные сокращения в 3+ регионах/отраслях",
        "triggered": "Безработица 5%+ (с текущих минимумов) или рост на 2+ п.п. за квартал",
        "critical": "Безработица выше 8% или массовые сокращения в системообразующих секторах",
    },
    "regional_finance_crisis": {
        "watch": "1-2 региона сообщают о бюджетных трудностях или кассовых разрывах",
        "warming_up": "3-5 регионов одновременно имеют кассовые разрывы или секвестр расходов",
        "triggered": "5+ регионов одновременно сталкиваются с секвестрами/кассовыми разрывами/долговыми проблемами",
        "critical": "Системный кризис региональных финансов, федеральный центр вынужден экстренно помогать",
    },
    "external_trade_deterioration": {
        "watch": "Экспортная выручка снизилась на 5-10% г/г или появились новые затруднения в расчётах по одному направлению",
        "warming_up": "Экспортная выручка снизилась на 10-20% г/г или закрылся крупный торговый канал",
        "triggered": "Экспортная выручка упала более 20% г/г или системные трудности с расчётами в 2+ направлениях",
        "critical": "Обвал экспортной выручки на 40%+ или блокировка основного торгового канала",
    },
    "oil_price_shock_urals": {
        "watch": "Urals упал ниже $55/барр или дисконт к Brent вырос до 15-20 $/барр",
        "warming_up": "Urals устойчиво ниже $50/барр или дисконт к Brent 20-25 $/барр",
        "triggered": "Urals устойчиво ниже $45/барр или дисконт к Brent превышает 25 $/барр",
        "critical": "Urals ниже $35/барр или экспорт нефти физически заблокирован санкциями/флотом",
    },
    "rzd_freight_collapse": {
        "watch": "Грузооборот РЖД снизился на 4-8% г/г за один месяц",
        "warming_up": "Грузооборот снизился на 8% г/г за один месяц",
        "triggered": "Грузооборот снизился более 8% г/г два месяца подряд",
        "critical": "Грузооборот снизился более 15% г/г или инфраструктурный коллапс",
    },
    "retail_sales_real_decline": {
        "watch": "Реальные розничные продажи снизились на 2-5% г/г за один месяц",
        "warming_up": "Реальные розничные продажи снизились на 5%+ г/г за один месяц",
        "triggered": "Реальные розничные продажи снизились более 5% г/г два месяца подряд",
        "critical": "Обвал реальных продаж на 15%+ г/г (уровень кризиса 2022 года)",
    },
    "industrial_output_contraction": {
        "watch": "ИПП снизился на 1-3% г/г за один-два месяца",
        "warming_up": "ИПП снизился на 3%+ г/г за два месяца подряд",
        "triggered": "ИПП снизился более 3% г/г три месяца подряд",
        "critical": "ИПП снизился более 8% г/г (уровень 2022 года) или коллапс в ключевых отраслях",
    },
}

SCENARIO_WEIGHTS = {
    "bank_holidays_national": {"deposit_access": 0.70, "banking_stress": 0.20, "fx_payment_stress": 0.10},
    "payment_infrastructure_systemic_disruption": {"deposit_access": 0.45, "banking_stress": 0.25, "fx_payment_stress": 0.20, "real_economy_decline": 0.10},
    "systemic_bank_resolution": {"deposit_access": 0.40, "banking_stress": 0.45, "corporate_credit_stress": 0.15},
    "deposit_outflow_mass": {"deposit_access": 0.50, "banking_stress": 0.30, "fx_payment_stress": 0.20},
    "cash_m0_surge": {"deposit_access": 0.45, "banking_stress": 0.30, "fx_payment_stress": 0.25},
    "interbank_liquidity_stress": {"deposit_access": 0.25, "banking_stress": 0.55, "fx_payment_stress": 0.20},
    "banking_npl_systemic_rise": {"banking_stress": 0.60, "corporate_credit_stress": 0.25, "deposit_access": 0.15},
    "cbr_repo_volume_spike": {"banking_stress": 0.65, "deposit_access": 0.20, "inflation_rate_stress": 0.15},
    "deposit_rate_spread_spike": {"banking_stress": 0.55, "deposit_access": 0.30, "inflation_rate_stress": 0.15},
    "budget_emergency_amendments": {"budget_stress": 0.60, "inflation_rate_stress": 0.25, "banking_stress": 0.15},
    "regional_finance_crisis": {"budget_stress": 0.55, "real_economy_decline": 0.30, "corporate_credit_stress": 0.15},
    "sovereign_domestic_debt_event": {"budget_stress": 0.50, "banking_stress": 0.30, "fx_payment_stress": 0.20},
    "ruble_depreciation_shock": {"fx_payment_stress": 0.50, "inflation_rate_stress": 0.30, "real_economy_decline": 0.20},
    "cash_fx_premium_spike": {"fx_payment_stress": 0.55, "deposit_access": 0.25, "banking_stress": 0.20},
    "new_fx_controls_severe": {"fx_payment_stress": 0.55, "banking_stress": 0.25, "real_economy_decline": 0.20},
    "new_sanctions_trade_finance": {"fx_payment_stress": 0.45, "real_economy_decline": 0.30, "corporate_credit_stress": 0.25},
    "corporate_default_wave": {"corporate_credit_stress": 0.55, "banking_stress": 0.25, "real_economy_decline": 0.20},
    "wage_arrears": {"corporate_credit_stress": 0.40, "real_economy_decline": 0.40, "banking_stress": 0.20},
    "personal_bankruptcy_surge": {"corporate_credit_stress": 0.45, "banking_stress": 0.30, "real_economy_decline": 0.25},
    "household_credit_stress": {"corporate_credit_stress": 0.45, "banking_stress": 0.35, "real_economy_decline": 0.20},
    "mortgage_real_estate_stress": {"corporate_credit_stress": 0.35, "real_economy_decline": 0.35, "banking_stress": 0.30},
    "rzd_freight_collapse": {"real_economy_decline": 0.65, "corporate_credit_stress": 0.20, "budget_stress": 0.15},
    "industrial_output_contraction": {"real_economy_decline": 0.65, "corporate_credit_stress": 0.20, "budget_stress": 0.15},
    "retail_sales_real_decline": {"real_economy_decline": 0.60, "corporate_credit_stress": 0.25, "banking_stress": 0.15},
    "labor_market_deterioration": {"real_economy_decline": 0.60, "corporate_credit_stress": 0.25, "banking_stress": 0.15},
    "external_trade_deterioration": {"real_economy_decline": 0.40, "fx_payment_stress": 0.35, "budget_stress": 0.25},
    "inflation_reacceleration": {"inflation_rate_stress": 0.70, "banking_stress": 0.20, "real_economy_decline": 0.10},
    "ofz_yield_curve_inversion_spike": {"inflation_rate_stress": 0.45, "banking_stress": 0.35, "budget_stress": 0.20},
    "ofz_market_stress": {"inflation_rate_stress": 0.40, "budget_stress": 0.35, "banking_stress": 0.25},
    "oil_price_shock_urals": {"fx_payment_stress": 0.35, "budget_stress": 0.40, "real_economy_decline": 0.25},
    "force_majeure_state_event": {"deposit_access": 0.25, "banking_stress": 0.25, "fx_payment_stress": 0.25, "budget_stress": 0.25},
    "cb_emergency_rate_hike": {"inflation_rate_stress": 0.45, "banking_stress": 0.30, "corporate_credit_stress": 0.25},
    "moex_trading_halt": {"banking_stress": 0.40, "fx_payment_stress": 0.30, "corporate_credit_stress": 0.30},
    "cb_emergency_actions_fin_stability": {"banking_stress": 0.45, "deposit_access": 0.30, "inflation_rate_stress": 0.25},
    "bank_license_chain_or_large": {"banking_stress": 0.50, "deposit_access": 0.35, "corporate_credit_stress": 0.15},
}

_DEFAULT_SEVERITY = {
    "watch": "Слабый сигнал, требует мониторинга",
    "warming_up": "Сигнал усиливается, порог не пройден",
    "triggered": "Критерий сработал по формальным условиям",
    "critical": "Аварийное событие или резкое ухудшение",
}

NEW_THRESHOLDS = {
    "green":  {"min": 0,  "max": 19,  "label": "НИЗКИЙ",       "emoji": "🟢"},
    "yellow": {"min": 20, "max": 39,  "label": "СРЕДНИЙ",       "emoji": "🟡"},
    "orange": {"min": 40, "max": 69,  "label": "СУЩЕСТВЕННЫЙ",  "emoji": "🟠"},
    "red":    {"min": 70, "max": 999, "label": "ВЫСОКИЙ",       "emoji": "🔴"},
    "black":  {"min": 0,  "max": 999, "label": "АВАРИЙНЫЙ",     "emoji": "⚫"},
}


def update_criteria_file(path: str) -> None:
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    for c in data["criteria"]:
        cid = c["id"]
        c["role"] = ROLES.get(cid, "leading")
        c["cooldown_days"] = COOLDOWN_DAYS.get(cid, 14)
        if cid in TRIGGERS_BLACK:
            c["triggers_black"] = True
        c["severity_levels"] = SEVERITY_LEVELS.get(cid, _DEFAULT_SEVERITY)
        c["scenario_weights"] = SCENARIO_WEIGHTS.get(cid, {"banking_stress": 0.5, "real_economy_decline": 0.5})

    data["thresholds"] = NEW_THRESHOLDS

    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Updated {path}: {len(data['criteria'])} criteria, thresholds updated")


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    update_criteria_file(str(base / "criteria.json"))
    update_criteria_file(str(base / "criteria_small.json"))
    print("Done.")
