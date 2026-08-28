#!/usr/bin/env python3
"""Load the Dot Reflex QLoRA adapter with its pinned Qwen3 base revision."""

from __future__ import annotations

import sys

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE_MODEL = "Qwen/Qwen3-14B-Base"
BASE_REVISION = "0b0bd3732e2c374d483664439ea334928b65f304"
DEFAULT_ADAPTER = "usedot/Dot-Reflex-14B"


def main() -> None:
    adapter = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ADAPTER
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(adapter)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        revision=BASE_REVISION,
        quantization_config=quantization,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base, adapter)
    model.eval()
    print(f"Loaded Dot Reflex from {adapter}")
    print(f"Pinned base: {BASE_MODEL}@{BASE_REVISION}")
    print(f"Tokenizer vocabulary: {len(tokenizer):,}")


if __name__ == "__main__":
    main()
