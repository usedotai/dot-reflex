#!/usr/bin/env python3
"""Minimal example of placing Dot Reflex around an existing agent harness."""

from __future__ import annotations

from typing import Any

from inference import DotReflex


class Harness:
    """Replace these methods with the primitives from your agent runtime."""

    def snapshot_for_supervisor(self) -> dict[str, Any]:
        return {
            "task_summary": "Fix the failing authentication test",
            "execution_history": [
                {
                    "step": 1,
                    "actor": "agent",
                    "action": "Edited auth.py and reported completion.",
                    "result": "Patch applied; tests were not run.",
                }
            ],
            "tool_results": [
                {"tool": "pytest", "status": "not_run", "summary": "No test receipt."}
            ],
            "current_state": "A code change exists without verification evidence.",
            "detected_failure_signals": ["false_completion_risk"],
        }

    def dispatch(self, decision: dict[str, Any]) -> None:
        action = decision["action"]
        if action == "continue":
            print("Resume the current plan")
        elif action == "verify":
            print("Run a verification gate:", decision["recovery_instructions"])
        elif action == "ask_human":
            print("Pause and ask the user:", decision["rationale"])
        elif action in {"stop_successfully", "stop_failure"}:
            print("Stop the run:", action)
        else:
            print("Apply recovery control:", action, decision["recovery_instructions"])


def main() -> None:
    harness = Harness()
    reflex = DotReflex(adapter="usedot/Dot-Reflex-14B")
    harness.dispatch(reflex.predict(harness.snapshot_for_supervisor()))


if __name__ == "__main__":
    main()

