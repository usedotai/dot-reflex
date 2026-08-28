# Dot Reflex 14B

[![Hugging Face](https://img.shields.io/badge/weights-Hugging%20Face-FFD21E?logo=huggingface&logoColor=000)](https://huggingface.co/usedot/Dot-Reflex-14B)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10--3.12-3776AB?logo=python&logoColor=white)](INSTALL.md)

![Dot Reflex benchmark overview](evaluation/benchmark_overview.png)

**Dot Reflex is an execution-recovery controller, not a replacement for the
agent doing the work.** It reads a compact summary of an agent trajectory and
returns one of ten control decisions: continue, verify, retry differently,
replan, rollback, branch, switch model, ask a human, stop successfully, or stop
with failure.

The release is a rank-64 QLoRA adapter for
[`Qwen/Qwen3-14B-Base`](https://huggingface.co/Qwen/Qwen3-14B-Base). It can sit
beside a coding or tool-using agent built on GPT, Claude, Gemini, Qwen, Llama, or
another model. Dot Reflex supervises the **execution loop**, so the worker model
does not need to share its architecture.

> Evaluation status: the published scores are from a held-out **synthetic**
> Agent Recovery Bench, not SWE-bench and not a production trial. A separate
> realistic transfer pilot was authored but its neural-controller run has not
> been completed. Do not treat the synthetic 100% result as proof of universal
> reliability.

## What it returns

Input is ordinary JSON built from events your agent framework already records:

```json
{
  "task_summary": "Add password-reset token validation",
  "execution_history": [
    {
      "step": 1,
      "actor": "agent",
      "action": "Modified auth/reset.py and declared completion.",
      "result": "Patch applied; no verification was run."
    }
  ],
  "tool_results": [
    {
      "tool": "pytest",
      "status": "not_run",
      "summary": "Tests were never executed."
    }
  ],
  "current_state": "Code changed, but there is no evidence it works.",
  "detected_failure_signals": ["false_completion_risk"]
}
```

The controller produces a machine-readable decision:

```json
{
  "action": "verify",
  "rationale": "The agent claimed completion without test evidence.",
  "confidence": 0.98,
  "recovery_instructions": "Run the targeted reset-token tests, then the relevant auth suite.",
  "parse_valid": true
}
```

The exact accepted structure is in [`trajectory.schema.json`](trajectory.schema.json).
This is a lightweight interchange schema, not a universal agent protocol. Most
harnesses need a small event-to-trajectory adapter; examples are documented in
[`INTEGRATION.md`](INTEGRATION.md).

## Quick start

### 1. Install

An NVIDIA GPU and Linux are required by the reference 4-bit runtime. A 24 GB GPU
is the practical minimum for one request at a time; 40-48 GB gives more headroom.

This GitHub repository contains the runtime, integration examples, tests,
evaluation receipts, and documentation. The adapter weights are hosted on
[Hugging Face](https://huggingface.co/usedot/Dot-Reflex-14B) and are downloaded
automatically on first use.

```bash
git clone https://github.com/usedotai/dot-reflex.git
cd dot-reflex
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

The adapter is about 1.03 GB. The pinned Qwen3 base weights are downloaded on
first use and cached by Hugging Face.

### 2. Run one decision

```bash
python3 inference.py examples/trajectory_false_completion.json \
  --adapter usedot/Dot-Reflex-14B
```

Pipe a trajectory through standard input with `-`:

```bash
python3 inference.py - --adapter usedot/Dot-Reflex-14B \
  < examples/trajectory_false_completion.json
```

Generation is greedy and deterministic. The runtime exits non-zero if the input
schema or generated action is invalid, so an orchestrator can fail closed.

### 3. Run a local HTTP service

```bash
python3 -m pip install -r requirements-server.txt
uvicorn serve:app --host 127.0.0.1 --port 8080
```

Then submit the same trajectory:

```bash
curl --fail-with-body \
  -H 'content-type: application/json' \
  --data @examples/trajectory_false_completion.json \
  http://127.0.0.1:8080/v1/decision
```

The server binds to localhost by default in the example. Add authentication,
rate limits, request-size limits, audit logs, and TLS before exposing it to a
network.

## Put it in an agent loop

Call Dot Reflex at evidence gates, not after every token. Good checkpoints are
after a failed tool call, a repeated action, a code edit, a test/build result,
an environment change, or a completion claim.

```python
trajectory = harness.snapshot_for_supervisor()
decision = reflex.predict(trajectory)

if decision["action"] == "continue":
    harness.resume()
elif decision["action"] == "verify":
    harness.require_verification(decision["recovery_instructions"])
elif decision["action"] == "ask_human":
    harness.pause_for_user(decision["rationale"])
elif decision["action"].startswith("stop_"):
    harness.stop(decision)
else:
    harness.apply_recovery_control(decision)
```

Dot Reflex recommends a control. Your harness remains responsible for policy,
permissions, tool execution, rollback mechanics, and the final stop decision.

## Control taxonomy

| Action | Use when | Harness behavior |
|---|---|---|
| `continue` | Useful progress is visible and no gate is unmet | Let the current plan proceed |
| `verify` | A claim or risky assumption lacks evidence | Run the smallest decisive test/check |
| `retry_differently` | The immediate attempt failed but the plan remains sound | Change command, parameters, or local method |
| `replan` | A core assumption or overall approach failed | Build a materially different plan |
| `rollback` | A change is harmful or regressive | Restore a known-good recoverable state |
| `branch` | Multiple plausible approaches should be isolated | Try alternatives in separate worktrees/sandboxes |
| `switch_model` | Persistent provider or model capability failure | Route the next attempt to another model |
| `ask_human` | Authority, secrets, ambiguity, or an external decision is required | Pause and request the missing input |
| `stop_successfully` | Completion is backed by adequate evidence | Return success and preserved receipts |
| `stop_failure` | No safe and authorized recovery remains | Stop, preserve evidence, and report the blocker |

## Where it fits best

- Coding agents with structured tool, patch, test, and build events.
- Long-running research or data agents that can loop or claim completion early.
- Multi-model routers that can implement `switch_model`.
- Human-in-the-loop systems that can pause on `ask_human`.
- Sandboxed agents with real rollback and branching primitives.

It can integrate with LangGraph, the OpenAI Agents SDK, OpenHands, AutoGen,
CrewAI, Google ADK, or a custom tool loop by normalizing their events. It is not
drop-in middleware for Cursor, Claude Code, Codex CLI, or Aider unless their
event stream is captured by a wrapper or hook. See the compatibility matrix and
mapping examples in [`INTEGRATION.md`](INTEGRATION.md).

## Base and adapter

| Property | Value |
|---|---|
| Base model | `Qwen/Qwen3-14B-Base` |
| Exact base revision | `0b0bd3732e2c374d483664439ea334928b65f304` |
| Method | 4-bit NF4 QLoRA, BF16 compute |
| LoRA rank / alpha / dropout | 64 / 128 / 0.05 |
| Target modules | Attention and MLP projection layers |
| Trainable parameters | 256,901,120 (1.710%) |
| Total base parameters | 15,025,208,320 |
| Context used during training | 2,048 tokens |
| License | Apache-2.0 |

## Training receipt

The completed run used 6,000 synthetic training trajectories and 600 synthetic
validation trajectories for one epoch, totaling 375 optimizer steps. Measured
trainer runtime was 1,816.2 seconds on one NVIDIA H200. Final aggregate training
loss was 0.11566 and final validation loss was 0.08640.

![Training dynamics](evaluation/training_dynamics.png)

Exact configuration and receipts:

- [`config/train_qlora.yaml`](config/train_qlora.yaml)
- [`provenance/run_receipt.json`](provenance/run_receipt.json)
- [`provenance/full_training_summary.json`](provenance/full_training_summary.json)

## Synthetic benchmark

Agent Recovery Bench v0 contains 1,000 balanced held-out synthetic trajectories
and 200 separate stateful synthetic recovery episodes. All controllers used the
same pinned Qwen revision where applicable. No failed parse was silently retried.

| Controller | Recovery accuracy | Macro F1 | Simulated recovery | ECE ↓ | Mean added tokens | Mean latency* |
|---|---:|---:|---:|---:|---:|---:|
| Deterministic rules | 0.800 | 0.733 | 0.800 | 0.138 | 9.6 | 0.002 ms |
| Qwen3-14B, minimal prompt | 0.671 | 0.608 | 0.785 | 0.671 | 54.9 | 4.42 s |
| Qwen3-14B, fixed recovery prompt | 0.900 | 0.867 | 1.000 | **0.053** | 93.1 | 6.01 s |
| **Dot Reflex adapter** | **1.000** | **1.000** | **1.000** | 0.070 | **59.3** | 6.13 s |

\* Latency is a run-specific H200 measurement, not a universal serving claim.

![Per-action synthetic benchmark](evaluation/action_accuracy.png)

All four controllers measured 1.000 false-completion detection, 1.000 loop
interruption, 0.000 unsafe-continue, and 0.000 false-stop on the applicable
synthetic cases. Because those diagnostics saturate across every controller,
they should not be used to claim a safety advantage.

Read [`EVALUATION.md`](EVALUATION.md) before citing results. Raw aggregate metric
receipts are preserved in [`evaluation/`](evaluation/).

## Important limitations

- Training, validation, and published benchmark trajectories are synthetic.
- The benchmark is Agentic SWE-flavored classification and simulation, not
  SWE-bench and not end-to-end repository issue resolution.
- The 100% adapter score demonstrates fit to this benchmark distribution. It
  does not establish transfer to independently authored or production failures.
- The model only sees the evidence supplied by the harness. Missing, stale, or
  misleading events can produce a wrong decision.
- Confidence is generated text, not a safety guarantee. Calibrate and threshold
  it again on your own distribution.
- The reference runtime is optimized for one NVIDIA GPU. No GGUF, Ollama,
  MLX, CPU, or merged-weight build is included in this release.
- Do not let the model directly authorize destructive, financial, medical,
  legal, or security-sensitive actions.

## Release integrity

Verify the GitHub source payload from the repository root:

```bash
sha256sum --check SHA256SUMS
```

On macOS, use:

```bash
shasum -a 256 -c SHA256SUMS
```

Validate the pinned base identity, source manifest, JSON examples, schema, and
chart receipts without loading the model:

```bash
python3 scripts/validate_release.py
```

The model weights are intentionally not duplicated in Git history. The canonical
adapter is hosted on [Hugging Face](https://huggingface.co/usedot/Dot-Reflex-14B),
where its published digest is:

```text
48854c62d147af3ee144fa0cb312b1d46af23ff6fc67dbb8a197aad780710361  adapter_model.safetensors
```

## Repository map

| Path | Contents |
|---|---|
| [Hugging Face weights](https://huggingface.co/usedot/Dot-Reflex-14B) | Canonical QLoRA adapter, tokenizer, and model card |
| `adapter_config.json` | PEFT adapter configuration and pinned base |
| `inference.py` | Strict one-shot Python/CLI controller |
| `serve.py` | Optional local FastAPI service |
| `trajectory.schema.json` | Framework-neutral input contract |
| `examples/` | Valid trajectories and an integration loop |
| `INTEGRATION.md` | Harness mapping and compatibility notes |
| `EVALUATION.md` | Benchmark scope, metrics, and claim boundaries |
| `evaluation/` | Charts and raw aggregate metric receipts |
| `provenance/` | Immutable training receipts |
| `config/` | Training, evaluation, and locked environment config |
| `DATASET_CARD.md` | Synthetic data construction and limitations |
| `SECURITY.md` | Deployment boundaries and reporting guidance |

## License and citation

Code and documentation in this repository, and the adapter files hosted on
Hugging Face, are released under Apache-2.0. The Qwen base model is a separate
upstream dependency; review its model card and license before distribution or
deployment. Third-party notices are preserved in
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

```bibtex
@software{dot_reflex_14b_2026,
  title        = {Dot Reflex 14B: An Agent Execution Recovery Controller},
  author       = {{Dot R\&D}},
  year         = {2026},
  url          = {https://github.com/usedotai/dot-reflex},
  note         = {Model weights: https://huggingface.co/usedot/Dot-Reflex-14B},
  version      = {1.0.0}
}
```
