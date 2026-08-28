# Installation and serving

## Supported reference configuration

The published runtime loads the Qwen3-14B base at its exact training revision
and applies the Dot Reflex PEFT adapter at inference time.

| Component | Reference requirement |
|---|---|
| Operating system | Linux x86_64 |
| Accelerator | NVIDIA CUDA GPU |
| VRAM | 24 GB minimum for 4-bit, 40-48 GB recommended |
| Precision | NF4 weights with BF16 compute |
| Python | 3.10-3.12 recommended |
| Disk | Plan for the adapter, base-model cache, Python environment, and temporary downloads |

The original training run used Python 3.10.12, PyTorch 2.13.0, Transformers
5.15.1, PEFT 0.20.0, bitsandbytes 0.50.1, CUDA 13.0, and one NVIDIA H200. The
full frozen environment is preserved in `config/requirements.lock`; it is a
provenance receipt, not the recommended cross-machine installer.

The smaller `requirements.txt` uses bounded compatible ranges for deployment.
If exact reproduction matters, build a container from the frozen receipt and
match a compatible NVIDIA driver/CUDA environment.

## Install from a clone

```bash
git clone https://github.com/usedotai/dot-reflex.git
cd dot-reflex
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Check the input contract without loading any model:

```bash
python3 inference.py examples/trajectory_false_completion.json --validate-only
```

Load and run locally:

```bash
python3 inference.py examples/trajectory_false_completion.json \
  --adapter usedot/Dot-Reflex-14B
```

The GitHub repository intentionally does not duplicate the 980 MB adapter.
PEFT downloads the canonical adapter and tokenizer from Hugging Face on first
use. To run offline, download the Hugging Face repository separately and pass
its local path through `--adapter` or `DOT_REFLEX_ADAPTER`.

## Use the Hugging Face weights

The default adapter ID is `usedot/Dot-Reflex-14B`, so this shorter command is
equivalent:

```bash
python3 inference.py examples/trajectory_false_completion.json
```

For an offline deployment, pre-download both repositories into your controlled
cache and set `HF_HUB_OFFLINE=1` only after verifying that all required files
are present.

## Memory modes

The default mode is 4-bit NF4 and matches the quantization setup used during
QLoRA training. It is the recommended serving path.

```bash
python3 inference.py examples/trajectory_false_completion.json \
  --adapter usedot/Dot-Reflex-14B
```

Full BF16 loading is available for research comparisons but requires much more
VRAM and host memory:

```bash
python3 inference.py examples/trajectory_false_completion.json \
  --adapter usedot/Dot-Reflex-14B --no-4bit
```

Do not assume BF16 and NF4 outputs are identical. Evaluate the exact serving
configuration you plan to deploy.

## Local API

```bash
python3 -m pip install -r requirements-server.txt
uvicorn serve:app --host 127.0.0.1 --port 8080
```

Health check:

```bash
curl --fail http://127.0.0.1:8080/healthz
```

Decision request:

```bash
curl --fail-with-body \
  -H 'content-type: application/json' \
  --data @examples/trajectory_false_completion.json \
  http://127.0.0.1:8080/v1/decision
```

The reference server serializes generations with a lock. This is deliberate:
it favors predictable one-GPU behavior over throughput. For production, use a
GPU serving layer that supports PEFT adapters and validate its generated JSON,
token limits, quantization, and concurrency semantics against this reference.

## Unsupported packaging in this release

- No merged full-weight checkpoint.
- No GGUF or Ollama manifest.
- No MLX conversion for Apple Silicon.
- No CPU-optimized runtime.
- No TensorRT-LLM, vLLM, TGI, or SGLang deployment recipe has been validated.

These are engineering targets, not impossible formats. Publishing a conversion
without a parity evaluation would make the release easier to install but less
trustworthy, so this repository does not claim them yet.

## Troubleshooting

### `python: command not found`

Use `python3` explicitly and activate the virtual environment:

```bash
source .venv/bin/activate
python3 --version
```

### CUDA is unavailable

Confirm that the driver can see the GPU before debugging Python:

```bash
nvidia-smi
python3 -c 'import torch; print(torch.cuda.is_available(), torch.version.cuda)'
```

### Out of memory

- Confirm that `--no-4bit` was not passed accidentally.
- Stop unrelated GPU processes.
- Run one request at a time.
- Reduce trajectory history while preserving the decisive evidence.
- Use a GPU with more VRAM.

### The input exceeds 2,048 tokens

The reference runtime rejects rather than silently truncates. Keep the most
recent evidence-bearing events, summarize older steps, retain failed command
signatures and verification receipts, then resubmit.

### Generated JSON is invalid

The CLI exits with status 2 and does not silently retry. Preserve `raw_text`,
fall back to a conservative harness policy, and record the failure. Do not
coerce an ambiguous generation into a control decision.
