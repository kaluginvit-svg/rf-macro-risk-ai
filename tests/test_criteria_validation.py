import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis_core import validate_criteria_data


def _valid_criteria_data() -> dict:
    return {
        "thresholds": {
            "green": {"min": 0, "max": 19},
            "yellow": {"min": 20, "max": 39},
            "orange": {"min": 40, "max": 69},
            "red": {"min": 70, "max": 999},
        },
        "criteria": [
            {
                "id": "cb_emergency_rate_hike",
                "name": "Emergency rate hike",
                "description": "Emergency unscheduled key-rate hike event.",
                "search_query": "cbr emergency key rate hike",
                "weight": 15,
                "speed": "fast",
                "source_policy": {
                    "requires_official": True,
                    "primary_domains": ["www.CBR.RU/press"],
                    "secondary_domains": ["interfax.ru"],
                    "min_independent_sources": 1,
                },
                "freshness": {"window_days": 7, "fallback_window_days": 30},
            }
        ],
    }


class CriteriaValidationTests(unittest.TestCase):
    def test_validate_criteria_data_accepts_valid_and_normalizes_domains(self):
        data = _valid_criteria_data()
        validated = validate_criteria_data(data)
        source_policy = validated["criteria"][0]["source_policy"]
        self.assertEqual(source_policy["primary_domains"], ["cbr.ru"])
        self.assertEqual(source_policy["secondary_domains"], ["interfax.ru"])
        self.assertTrue(source_policy["allow_reuse_official"])
        self.assertFalse(source_policy["allow_undated_non_official"])

    def test_validate_criteria_data_rejects_missing_required_field(self):
        data = _valid_criteria_data()
        del data["criteria"][0]["speed"]
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            validate_criteria_data(data)

    def test_validate_criteria_data_rejects_duplicate_ids(self):
        data = _valid_criteria_data()
        second = copy.deepcopy(data["criteria"][0])
        second["name"] = "Second"
        data["criteria"].append(second)
        with self.assertRaisesRegex(ValueError, "Duplicate criterion id"):
            validate_criteria_data(data)

    def test_validate_criteria_data_rejects_invalid_threshold_order(self):
        data = _valid_criteria_data()
        data["thresholds"]["red"]["min"] = 10
        with self.assertRaisesRegex(ValueError, "thresholds.red.min"):
            validate_criteria_data(data)

    def test_validate_criteria_data_rejects_invalid_min_independent_sources(self):
        data = _valid_criteria_data()
        data["criteria"][0]["source_policy"]["min_independent_sources"] = 0
        with self.assertRaisesRegex(ValueError, "min_independent_sources"):
            validate_criteria_data(data)


if __name__ == "__main__":
    unittest.main()
