# Third-party license inventory

The project source is Apache-2.0. This file summarizes direct material inputs.
Versions from the completed training environment are frozen in
`config/requirements.lock`; that file is a provenance receipt, not a recommended
cross-platform installer.

| Component | Purpose | License | Source |
|---|---|---|---|
| Qwen3-14B-Base | base weights/tokenizer | Apache-2.0 | https://huggingface.co/Qwen/Qwen3-14B-Base |
| PyTorch | tensor/CUDA training runtime | BSD-3-Clause | https://github.com/pytorch/pytorch |
| Transformers | model loading/training | Apache-2.0 | https://github.com/huggingface/transformers |
| PEFT | LoRA/QLoRA adapter implementation | Apache-2.0 | https://github.com/huggingface/peft |
| Accelerate | device/runtime integration | Apache-2.0 | https://github.com/huggingface/accelerate |
| bitsandbytes | 4-bit quantization/optimizer | MIT | https://github.com/bitsandbytes-foundation/bitsandbytes |
| Datasets | dataset utilities | Apache-2.0 | https://github.com/huggingface/datasets |
| scikit-learn | supporting metrics dependency | BSD-3-Clause | https://github.com/scikit-learn/scikit-learn |
| Matplotlib | charts | PSF-based | https://matplotlib.org/stable/project/license.html |
| PyYAML | configuration parsing | MIT | https://github.com/yaml/pyyaml |

The generated inventory preserves package metadata as reported by the installed
distributions; blank or ambiguous metadata is not silently assigned a license.
