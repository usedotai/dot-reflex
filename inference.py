#!/usr/bin/env python3
"""Deterministic inference runtime for the Dot Reflex QLoRA adapter."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

BASE_MODEL = "Qwen/Qwen3-14B-Base"
BASE_REVISION = "0b0bd3732e2c374d483664439ea334928b65f304"
DEFAULT_ADAPTER = "usedot/Dot-Reflex-14B"
MAX_INPUT_TOKENS = 2048
MAX_NEW_TOKENS = 160
ACTIONS = (
    "continue",
    "verify",
    "retry_differently",
    "replan",
    "rollback",
    "branch",
    "switch_model",
    "ask_human",
    "stop_successfully",
    "stop_failure",
)

SYSTEM_PROMPT = (
    "You are Dot Reflex, an execution supervisor. Observe the trajectory and "
    "choose exactly one control action. Protect the user from false completion, "
    "ineffective loops, and unsafe operations. Return only a compact JSON object "
    "with keys action, rationale, confidence, and recovery_instructions. Valid "
    "actions: "
    + ", ".join(ACTIONS)
    + "."
)

DECISION_POLICY = """Decision policy:
- continue only when useful progress is occurring without an unmet gate
- verify when completion or a risky assumption lacks evidence
- retry_differently when the immediate approach failed but the plan remains sound
- replan when core assumptions or the overall approach failed
- rollback after a harmful or regressive change
- branch when multiple plausible paths should be isolated and compared
- switch_model for persistent model/provider capability failure
- ask_human for material ambiguity, authority, secrets, or external decisions
- stop_successfully only with adequate completion evidence
- stop_failure only when no safe, authorized recovery remains"""


def schema_path() -> Path:
    return Path(__file__).with_name("trajectory.schema.json")


def validate_trajectory(trajectory: dict[str, Any]) -> None:
    """Validate input strictly against the public trajectory contract."""

    errors: list[str] = []
    required = {
        "task_summary",
        "execution_history",
        "tool_results",
        "current_state",
        "detected_failure_signals",
    }

    def check_string(value: Any, path: str, minimum: int, maximum: int) -> None:
        if not isinstance(value, str):
            errors.append(f"{path}: must be a string")
        elif not minimum <= len(value) <= maximum:
            errors.append(f"{path}: length must be between {minimum} and {maximum}")

    if not isinstance(trajectory, dict):
        raise ValueError("Invalid trajectory:\n- $: must be an object")
    missing = sorted(required - set(trajectory))
    extra = sorted(set(trajectory) - required)
    for key in missing:
        errors.append(f"$: missing required property '{key}'")
    for key in extra:
        errors.append(f"$: unexpected property '{key}'")
    if missing:
        raise ValueError("Invalid trajectory:\n- " + "\n- ".join(errors))

    check_string(trajectory["task_summary"], "task_summary", 1, 4000)
    check_string(trajectory["current_state"], "current_state", 1, 8000)

    history = trajectory["execution_history"]
    if not isinstance(history, list):
        errors.append("execution_history: must be an array")
    elif len(history) > 100:
        errors.append("execution_history: must contain at most 100 items")
    else:
        for index, item in enumerate(history):
            path = f"execution_history.{index}"
            if not isinstance(item, dict):
                errors.append(f"{path}: must be an object")
                continue
            for key in ("step", "actor", "action", "result"):
                if key not in item:
                    errors.append(f"{path}: missing required property '{key}'")
            if not all(key in item for key in ("step", "actor", "action", "result")):
                continue
            step = item["step"]
            if not isinstance(step, int) or isinstance(step, bool) or step < 0:
                errors.append(f"{path}.step: must be a non-negative integer")
            check_string(item["actor"], f"{path}.actor", 1, 200)
            check_string(item["action"], f"{path}.action", 1, 4000)
            check_string(item["result"], f"{path}.result", 0, 8000)

    tool_results = trajectory["tool_results"]
    if not isinstance(tool_results, list):
        errors.append("tool_results: must be an array")
    elif len(tool_results) > 100:
        errors.append("tool_results: must contain at most 100 items")
    else:
        for index, item in enumerate(tool_results):
            path = f"tool_results.{index}"
            if not isinstance(item, dict):
                errors.append(f"{path}: must be an object")
                continue
            for key in ("tool", "status", "summary"):
                if key not in item:
                    errors.append(f"{path}: missing required property '{key}'")
            if not all(key in item for key in ("tool", "status", "summary")):
                continue
            check_string(item["tool"], f"{path}.tool", 1, 300)
            check_string(item["status"], f"{path}.status", 1, 100)
            check_string(item["summary"], f"{path}.summary", 0, 8000)

    signals = trajectory["detected_failure_signals"]
    if not isinstance(signals, list):
        errors.append("detected_failure_signals: must be an array")
    elif len(signals) > 50:
        errors.append("detected_failure_signals: must contain at most 50 items")
    else:
        for index, item in enumerate(signals):
            check_string(item, f"detected_failure_signals.{index}", 1, 200)
        try:
            if len(set(signals)) != len(signals):
                errors.append("detected_failure_signals: items must be unique")
        except TypeError:
            pass

    if errors:
        raise ValueError("Invalid trajectory:\n- " + "\n- ".join(errors[:10]))


def render_prompt(trajectory: dict[str, Any]) -> str:
    """Render the same strong recovery prompt used for adapter evaluation."""

    return (
        SYSTEM_PROMPT
        + "\n\n"
        + DECISION_POLICY
        + "\n\nTrajectory:\n"
        + json.dumps(trajectory, sort_keys=True, ensure_ascii=False)
        + "\nDecision JSON:"
    )


def parse_decision(text: str) -> dict[str, Any]:
    """Parse one JSON object without retrying or inventing a missing action."""

    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else stripped
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return {
            "action": None,
            "rationale": "",
            "confidence": 0.0,
            "recovery_instructions": None,
            "parse_valid": False,
            "parse_error": "generation was not one JSON object",
            "raw_text": text,
        }

    if not isinstance(value, dict):
        return {
            "action": None,
            "rationale": "",
            "confidence": 0.0,
            "recovery_instructions": None,
            "parse_valid": False,
            "parse_error": "generation JSON was not an object",
            "raw_text": text,
        }

    action = value.get("action")
    rationale = value.get("rationale")
    recovery = value.get("recovery_instructions")
    confidence = value.get("confidence")
    valid = (
        action in ACTIONS
        and isinstance(rationale, str)
        and isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and math.isfinite(float(confidence))
        and 0.0 <= float(confidence) <= 1.0
        and (recovery is None or isinstance(recovery, (str, list)))
    )
    result = {
        "action": action if action in ACTIONS else None,
        "rationale": rationale[:500] if isinstance(rationale, str) else "",
        "confidence": (
            float(confidence)
            if isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and math.isfinite(float(confidence))
            else 0.0
        ),
        "recovery_instructions": recovery,
        "parse_valid": valid,
    }
    if not valid:
        result["parse_error"] = "generation did not satisfy the decision contract"
        result["raw_text"] = text
    return result


class DotReflex:
    """One loaded Dot Reflex controller suitable for repeated decisions."""

    def __init__(
        self,
        adapter: str = DEFAULT_ADAPTER,
        *,
        four_bit: bool = True,
        max_input_tokens: int = MAX_INPUT_TOKENS,
        max_new_tokens: int = MAX_NEW_TOKENS,
    ) -> None:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if not torch.cuda.is_available():
            raise RuntimeError(
                "The reference runtime requires an NVIDIA CUDA GPU. "
                "No CPU, MLX, or GGUF runtime is included."
            )

        self.adapter = adapter
        self.max_input_tokens = max_input_tokens
        self.max_new_tokens = max_new_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(adapter, use_fast=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"

        load_kwargs: dict[str, Any] = {
            "revision": BASE_REVISION,
            "device_map": "auto",
            "low_cpu_mem_usage": True,
            "torch_dtype": torch.bfloat16,
        }
        if four_bit:
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
            )

        base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, **load_kwargs)
        self.model = PeftModel.from_pretrained(base, adapter)
        self.model.eval()
        self.model.config.use_cache = True
        self.input_device = self.model.get_input_embeddings().weight.device

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "base_model": BASE_MODEL,
            "base_revision": BASE_REVISION,
            "actions": list(ACTIONS),
        }

    def predict(self, trajectory: dict[str, Any]) -> dict[str, Any]:
        import torch

        validate_trajectory(trajectory)
        prompt = render_prompt(trajectory)
        encoded = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
        prompt_tokens = int(encoded["input_ids"].shape[1])
        if prompt_tokens > self.max_input_tokens:
            raise ValueError(
                f"Rendered trajectory is {prompt_tokens} tokens; limit is "
                f"{self.max_input_tokens}. Summarize older events before inference."
            )
        encoded = {key: value.to(self.input_device) for key, value in encoded.items()}

        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            generated = self.model.generate(
                **encoded,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                use_cache=True,
            )
        torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - started) * 1000.0

        token_ids = generated[0, prompt_tokens:].tolist()
        if self.tokenizer.eos_token_id in token_ids:
            token_ids = token_ids[: token_ids.index(self.tokenizer.eos_token_id) + 1]
        text = self.tokenizer.decode(token_ids, skip_special_tokens=True)
        decision = parse_decision(text)
        decision["usage"] = {
            "input_tokens": prompt_tokens,
            "output_tokens": len(token_ids),
        }
        decision["latency_ms"] = round(latency_ms, 3)
        return decision


def load_trajectory(path: str) -> dict[str, Any]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Trajectory JSON must be one object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one deterministic Dot Reflex recovery decision."
    )
    parser.add_argument("input", help="trajectory JSON path, or - for stdin")
    parser.add_argument(
        "--adapter",
        default=DEFAULT_ADAPTER,
        help="local adapter directory or Hugging Face model ID",
    )
    parser.add_argument(
        "--no-4bit",
        action="store_true",
        help="load BF16 weights instead of NF4 (requires substantially more VRAM)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate input without downloading or loading model weights",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        trajectory = load_trajectory(args.input)
        validate_trajectory(trajectory)
        if args.validate_only:
            print(json.dumps({"valid": True, "input": args.input}, indent=2))
            return 0
        controller = DotReflex(args.adapter, four_bit=not args.no_4bit)
        decision = controller.predict(trajectory)
        print(json.dumps(decision, indent=2, ensure_ascii=False))
        return 0 if decision["parse_valid"] else 2
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"dot-reflex: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
