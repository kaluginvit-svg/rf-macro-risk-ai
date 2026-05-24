"""
Scoring engine for the Money Alert AI project.

Computes crisis_score, deposit_access_score, risk_level, and manages the
cooldown/novelty ledger for criteria events.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# ─────────────────────────── Severity multipliers ────────────────────────────

SEVERITY_MULTIPLIERS: dict[str, float] = {
    "quiet": 0.0,
    "watch": 0.25,
    "warming_up": 0.50,
    "triggered": 1.00,
    "critical": 1.50,
    "cooling_down": 0.25,
}

# ─────────────────────── deposit_access formula weights ──────────────────────

DEPOSIT_ACCESS_WEIGHTS: dict[str, int] = {
    "bank_holidays_national": 40,
    "payment_infrastructure_systemic_disruption": 20,
    "systemic_bank_resolution": 20,
    "interbank_liquidity_stress": 10,
    "deposit_outflow_mass": 10,
}

# ─────────────────────────── Public API ──────────────────────────────────────


def severity_multiplier(status: str) -> float:
    """Return the weight multiplier for a given severity status string."""
    return SEVERITY_MULTIPLIERS.get(status, 0.0)


def get_novelty_multiplier(
    criterion_id: str,
    ledger: dict,
    now: datetime | None = None,
) -> float:
    """
    Return novelty multiplier for a criterion based on its cooldown state.

    - If cooldown_until is in the future  → 0.25  (already counted, reduce weight)
    - Otherwise                           → 1.0   (fresh trigger, full weight)
    """
    now = now or datetime.now(timezone.utc)
    events: dict = (ledger or {}).get("events", {})
    entry = events.get(criterion_id)
    if not entry:
        return 1.0
    cooldown_str = entry.get("cooldown_until")
    if not cooldown_str:
        return 1.0
    try:
        cooldown_until = datetime.fromisoformat(cooldown_str)
        if cooldown_until.tzinfo is None:
            cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
        if cooldown_until > now:
            return 0.25
    except Exception:
        pass
    return 1.0


def compute_crisis_score(
    criteria_status_list: list[dict],
    criteria_by_id: dict[str, dict],
    ledger: dict,
    now: datetime | None = None,
) -> int:
    """
    Compute total crisis score.

    Formula per criterion:
        weight * severity_multiplier(status) * novelty_multiplier(id, ledger)

    Returns the rounded integer sum.
    """
    now = now or datetime.now(timezone.utc)
    total = 0.0
    for item in criteria_status_list or []:
        cid = item.get("id")
        if not cid:
            continue
        criterion = criteria_by_id.get(cid, {})
        weight = criterion.get("weight", 0)
        status = item.get("status", "quiet")
        sev = severity_multiplier(status)
        nov = get_novelty_multiplier(cid, ledger, now=now)
        total += weight * sev * nov
    return int(round(total))


def compute_deposit_access_score(criteria_status_by_id: dict[str, str]) -> int:
    """
    Compute deposit access risk score.

    criteria_status_by_id: {criterion_id: status_string}

    Uses hardcoded DEPOSIT_ACCESS_WEIGHTS and severity_multiplier to compute
    a weighted sum representing short-term deposit/payment access risk.
    """
    total = 0.0
    for cid, weight in DEPOSIT_ACCESS_WEIGHTS.items():
        status = criteria_status_by_id.get(cid, "quiet")
        sev = severity_multiplier(status)
        total += weight * sev
    return int(round(total))


def risk_level_from_score(
    score: int,
    thresholds: dict,
    criteria_status_by_id: dict[str, str] | None = None,
    criteria_by_id: dict[str, dict] | None = None,
) -> str:
    """
    Determine risk level from score, with black override for shock triggers.

    Black level is triggered when ANY criterion with triggers_black=True has
    status 'triggered' or 'critical'.

    Threshold order: black (code-triggered) → red → orange → yellow → green.
    Falls back to green if no threshold matches.
    """
    # Check black level first
    if criteria_status_by_id and criteria_by_id:
        for cid, status in criteria_status_by_id.items():
            if status in ("triggered", "critical"):
                criterion = criteria_by_id.get(cid, {})
                if criterion.get("triggers_black", False):
                    return "black"

    # Score-based levels in descending order
    for level in ("red", "orange", "yellow", "green"):
        cfg = thresholds.get(level, {})
        min_score = cfg.get("min", 0)
        max_score = cfg.get("max", 999)
        if min_score <= score <= max_score:
            return level

    return "green"


def deposit_access_risk_from_score(score: int) -> str:
    """
    Map deposit_access_score to a risk label.

    red:    score >= 30
    yellow: score >= 10
    green:  score < 10
    """
    if score >= 30:
        return "red"
    if score >= 10:
        return "yellow"
    return "green"


def record_criterion_events(
    ledger: dict,
    criteria_status: list[dict],
    criteria_by_id: dict[str, dict],
    now: datetime | None = None,
) -> None:
    """
    Update ledger["events"] based on current criteria status.

    For each criterion with status triggered/critical:
    - Record last_triggered timestamp
    - Set cooldown_until = now + cooldown_days
    - Increment trigger_count

    For criteria with status quiet/watch/warming_up/cooling_down:
    - Do not reset existing events (cooldown continues)
    """
    if ledger is None:
        return
    now = now or datetime.now(timezone.utc)
    events: dict = ledger.setdefault("events", {})

    for item in criteria_status or []:
        cid = item.get("id")
        if not cid:
            continue
        status = item.get("status", "quiet")
        criterion = criteria_by_id.get(cid, {})
        cooldown_days = criterion.get("cooldown_days", 14)

        if status in ("triggered", "critical"):
            entry = events.setdefault(cid, {
                "criterion_id": cid,
                "trigger_count": 0,
                "first_triggered": now.isoformat(),
            })
            entry["last_triggered"] = now.isoformat()
            entry["cooldown_days"] = cooldown_days
            # cooldown_days=0 means ongoing events (e.g. force_majeure, sovereign_debt)
            if cooldown_days > 0:
                entry["cooldown_until"] = (now + timedelta(days=cooldown_days)).isoformat()
            else:
                entry["cooldown_until"] = now.isoformat()
            entry["trigger_count"] = entry.get("trigger_count", 0) + 1


# ─────────────────────────── Self-test ───────────────────────────────────────

if __name__ == "__main__":
    # Quick sanity checks
    assert severity_multiplier("quiet") == 0.0
    assert severity_multiplier("triggered") == 1.0
    assert severity_multiplier("critical") == 1.5
    assert severity_multiplier("unknown") == 0.0

    # compute_crisis_score
    criteria_by_id = {"test_a": {"weight": 10}, "test_b": {"weight": 5}}
    statuses = [
        {"id": "test_a", "status": "triggered"},
        {"id": "test_b", "status": "watch"},
    ]
    score = compute_crisis_score(statuses, criteria_by_id, {})
    assert score == 11, f"Expected 11, got {score}"  # 10*1.0 + 5*0.25

    # deposit_access_score
    da_status = {"bank_holidays_national": "triggered"}
    da_score = compute_deposit_access_score(da_status)
    assert da_score == 40, f"Expected 40, got {da_score}"

    # risk_level_from_score
    thresholds = {
        "green": {"min": 0, "max": 19},
        "yellow": {"min": 20, "max": 39},
        "orange": {"min": 40, "max": 69},
        "red": {"min": 70, "max": 999},
    }
    assert risk_level_from_score(0, thresholds) == "green"
    assert risk_level_from_score(25, thresholds) == "yellow"
    assert risk_level_from_score(50, thresholds) == "orange"
    assert risk_level_from_score(80, thresholds) == "red"

    # black override
    cby_id = {"bank_holidays_national": {"triggers_black": True, "weight": 20}}
    cstatus = {"bank_holidays_national": "triggered"}
    assert risk_level_from_score(5, thresholds, cstatus, cby_id) == "black"

    # deposit_access_risk_from_score
    assert deposit_access_risk_from_score(5) == "green"
    assert deposit_access_risk_from_score(15) == "yellow"
    assert deposit_access_risk_from_score(35) == "red"

    # record_criterion_events
    ledger: dict = {}
    cby_id2 = {"test_crit": {"cooldown_days": 14}}
    record_criterion_events(ledger, [{"id": "test_crit", "status": "triggered"}], cby_id2)
    assert "test_crit" in ledger["events"]
    assert ledger["events"]["test_crit"]["trigger_count"] == 1

    print("ok")
