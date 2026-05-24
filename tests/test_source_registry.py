import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from source_registry import should_keep_source


def _policy() -> dict:
    return {
        "source_policy": {
            "requires_official": False,
            "primary_domains": ["cbr.ru"],
            "secondary_domains": ["interfax.ru", "rbc.ru"],
            "min_independent_sources": 1,
            "allow_reuse_official": True,
            "allow_undated_non_official": False,
        },
        "freshness": {"window_days": 7, "fallback_window_days": 30},
    }


class SourceRegistryFilteringTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 5, 24, tzinfo=timezone.utc)
        self.ledger = {"sources": {}, "events": {}}
        self.seen_urls = set()

    def test_keeps_allowed_fresh_source(self):
        decision = should_keep_source(
            url="https://interfax.ru/economy/123",
            published_date="2026-05-23",
            title="Macro risk update",
            content="Important detailed content about macro-economic changes in markets.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertTrue(decision.keep)
        self.assertEqual(decision.reason, "kept")

    def test_rejects_domain_not_allowed(self):
        decision = should_keep_source(
            url="https://example.com/news",
            published_date="2026-05-23",
            title="Macro risk update",
            content="Important detailed content about macro-economic changes in markets.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "domain_not_allowed")

    def test_rejects_future_date(self):
        decision = should_keep_source(
            url="https://interfax.ru/economy/321",
            published_date="2026-06-10",
            title="Future event",
            content="Detailed content about a future-scheduled announcement.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "future_date")

    def test_rejects_old_source(self):
        old_date = (self.now - timedelta(days=40)).date().isoformat()
        decision = should_keep_source(
            url="https://interfax.ru/economy/old",
            published_date=old_date,
            title="Old event",
            content="Detailed content about old announcement.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "old")

    def test_rejects_undated_non_official_when_disallowed(self):
        decision = should_keep_source(
            url="https://interfax.ru/economy/no-date",
            published_date="",
            title="No date item",
            content="Detailed content without explicit date.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "undated_non_official")

    def test_rejects_low_signal_non_official(self):
        decision = should_keep_source(
            url="https://rbc.ru/economy/short",
            published_date="2026-05-23",
            title="Short",
            content="Tiny",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "low_signal")

    def test_rejects_duplicate_in_run(self):
        self.seen_urls.add("https://interfax.ru/economy/dup")
        decision = should_keep_source(
            url="https://interfax.ru/economy/dup",
            published_date="2026-05-23",
            title="Duplicate",
            content="Detailed content for duplicate URL in current run.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "duplicate_in_run")

    def test_rejects_duplicate_in_ledger_for_non_official(self):
        canonical = "https://interfax.ru/economy/already-used"
        self.ledger["sources"][canonical] = {
            "canonical_url": canonical,
            "snippet_hash": "abc",
        }
        decision = should_keep_source(
            url=canonical,
            published_date="2026-05-23",
            title="Already used",
            content="Detailed content about already seen source.",
            ledger=self.ledger,
            seen_urls=self.seen_urls,
            time_range="month",
            policy=_policy(),
            now=self.now,
        )
        self.assertFalse(decision.keep)
        self.assertEqual(decision.reason, "duplicate_ledger")


if __name__ == "__main__":
    unittest.main()
