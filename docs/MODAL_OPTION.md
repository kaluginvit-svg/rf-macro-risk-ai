# Modal option

Modal deployment is intentionally dormant in this repository.

Current architecture:

- `Money_alert_AI` runs the analysis engine locally or from any external scheduler.
- `Бот_репортер` is a separate neighboring project that publishes the generated analysis.
- This repo has no active `modal` dependency and no active `src/modal_app.py`.

If cloud scheduling is needed later, use the upstream `Rai220/money_alert_ai` `src/modal_app.py` only as a reference and create a separate deployment layer. Do not mix Telegram publishing secrets into this analysis engine unless the architecture is explicitly changed.

Recommended future Modal contract:

1. Build image with this repo only.
2. Run `uv run python src/lc_money_alert_bot.py --provider ...`.
3. Mount or persist `runs_history.json` and `research_ledger.json`.
4. Export `docs/data.json` or another stable JSON artifact.
5. Trigger the reporter as a separate deployment/job, not from inside the analysis image.

Required persistent files if enabled:

- `RUNS_HISTORY_FILE`
- `RESEARCH_LEDGER_FILE`
- exported report JSON

Do not enable Modal by adding dependencies until deployment is actually needed.
