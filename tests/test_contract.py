from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inference import parse_decision, validate_trajectory


class ContractTests(unittest.TestCase):
    def test_examples_validate(self) -> None:
        for path in sorted((ROOT / "examples").glob("trajectory_*.json")):
            with self.subTest(path=path.name):
                validate_trajectory(json.loads(path.read_text(encoding="utf-8")))

    def test_extra_root_property_is_rejected(self) -> None:
        trajectory = {
            "task_summary": "x",
            "execution_history": [],
            "tool_results": [],
            "current_state": "x",
            "detected_failure_signals": [],
            "gold_action": "verify",
        }
        with self.assertRaisesRegex(ValueError, "unexpected property 'gold_action'"):
            validate_trajectory(trajectory)

    def test_valid_decision_parses(self) -> None:
        decision = parse_decision(
            json.dumps(
                {
                    "action": "verify",
                    "rationale": "Completion lacks test evidence.",
                    "confidence": 0.9,
                    "recovery_instructions": "Run the targeted tests.",
                }
            )
        )
        self.assertTrue(decision["parse_valid"])
        self.assertEqual(decision["action"], "verify")

    def test_malformed_decision_fails_closed(self) -> None:
        self.assertFalse(parse_decision("not json")["parse_valid"])

    def test_non_finite_confidence_is_rejected(self) -> None:
        decision = parse_decision(
            '{"action":"continue","rationale":"x","confidence":NaN,'
            '"recovery_instructions":null}'
        )
        self.assertFalse(decision["parse_valid"])
        self.assertEqual(decision["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()

