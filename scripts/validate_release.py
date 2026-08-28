#!/usr/bin/env python3
"""Validate the public Dot Reflex source release without loading model weights."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inference import validate_trajectory

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BASE = "Qwen/Qwen3-14B-Base"
EXPECTED_REVISION = "0b0bd3732e2c374d483664439ea334928b65f304"
EXPECTED_ADAPTER_SHA256 = "48854c62d147af3ee144fa0cb312b1d46af23ff6fc67dbb8a197aad780710361"

REQUIRED = (
    "README.md",
    "LICENSE",
    "SHA256SUMS",
    "adapter_config.json",
    "trajectory.schema.json",
    "inference.py",
    "serve.py",
    "INSTALL.md",
    "INTEGRATION.md",
    "EVALUATION.md",
    "SECURITY.md",
    "evaluation/benchmark_overview.png",
    "evaluation/action_accuracy.png",
    "evaluation/efficiency.png",
    "evaluation/training_dynamics.png",
    "evaluation/chart_receipt.json",
    "provenance/run_receipt.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        require((ROOT / relative).is_file(), f"missing required file: {relative}", errors)

    adapter_config = json.loads((ROOT / "adapter_config.json").read_text(encoding="utf-8"))
    require(
        adapter_config.get("base_model_name_or_path") == EXPECTED_BASE,
        "adapter base model does not match release identity",
        errors,
    )
    require(
        adapter_config.get("revision") == EXPECTED_REVISION,
        "adapter base revision does not match pinned receipt",
        errors,
    )
    adapter_path = ROOT / "adapter_model.safetensors"
    if adapter_path.is_file():
        require(
            sha256(adapter_path) == EXPECTED_ADAPTER_SHA256,
            "adapter_model.safetensors digest mismatch",
            errors,
        )

    manifest_path = ROOT / "SHA256SUMS"
    if manifest_path.is_file():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            expected, relative = line.split(maxsplit=1)
            relative = relative.lstrip("*").removeprefix("./")
            path = ROOT / relative
            require(path.is_file(), f"source manifest path missing: {relative}", errors)
            if path.is_file():
                require(
                    sha256(path) == expected,
                    f"source manifest digest mismatch: {relative}",
                    errors,
                )

    schema = json.loads((ROOT / "trajectory.schema.json").read_text(encoding="utf-8"))
    require(schema.get("type") == "object", "trajectory schema root must be an object", errors)
    require(
        set(schema.get("required", []))
        == {
            "task_summary",
            "execution_history",
            "tool_results",
            "current_state",
            "detected_failure_signals",
        },
        "trajectory schema required fields differ from runtime contract",
        errors,
    )
    for example in sorted((ROOT / "examples").glob("trajectory_*.json")):
        payload = json.loads(example.read_text(encoding="utf-8"))
        try:
            validate_trajectory(payload)
        except ValueError as exc:
            errors.append(f"{example.relative_to(ROOT)}: {exc}")

    chart_receipt = json.loads((ROOT / "evaluation/chart_receipt.json").read_text(encoding="utf-8"))
    for group in ("sources", "outputs"):
        for relative, expected in chart_receipt[group].items():
            path = ROOT / relative
            require(path.is_file(), f"chart receipt path missing: {relative}", errors)
            if path.is_file():
                require(sha256(path) == expected, f"chart receipt digest mismatch: {relative}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Dot Reflex source release validation passed")
    print(f"base: {EXPECTED_BASE}@{EXPECTED_REVISION}")
    print(f"canonical adapter sha256: {EXPECTED_ADAPTER_SHA256}")
    print(f"local adapter present: {adapter_path.is_file()}")
    print(f"validated examples: {len(list((ROOT / 'examples').glob('trajectory_*.json')))}")
    print(f"validated charts: {len(chart_receipt['outputs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
