# Integration guide

## Architecture

Dot Reflex is a sidecar supervisor around an existing agent loop:

```text
user task
   │
   ▼
worker agent ──► tools / workspace / tests
   │                       │
   └──── structured events ◄┘
                  │
                  ▼
         trajectory normalizer
                  │
                  ▼
          Dot Reflex decision
                  │
                  ▼
     deterministic policy gate
                  │
                  ▼
  resume / verify / recover / ask / stop
```

The worker can use any underlying model. Compatibility depends on whether the
harness exposes enough state and can implement the selected control, not on the
worker model family.

## When to invoke it

Useful decision points include:

- after a tool timeout, provider error, or malformed tool result;
- after the same failure or action repeats;
- after a patch, migration, dependency change, or environment mutation;
- after a test, lint, typecheck, build, or deployment receipt;
- before accepting an agent's completion claim;
- before a destructive, privileged, costly, or externally visible action;
- after context restoration, workspace switching, or checkpoint recovery.

Avoid calling after every language-model token. Dot Reflex was trained on
trajectory snapshots, not token-by-token hidden states.

## Normalize events into the input contract

The required fields are deliberately framework-neutral:

| Dot Reflex field | Populate with |
|---|---|
| `task_summary` | Current user objective and relevant acceptance criteria |
| `execution_history` | Ordered, evidence-bearing agent actions and their observed results |
| `tool_results` | Commands/tools, explicit status, and concise output summary |
| `current_state` | Workspace, plan, verification, dependency, and blocker state now |
| `detected_failure_signals` | Conservative tags produced by deterministic monitors |

Use `trajectory.schema.json` as the boundary contract. Extra properties are
rejected at the root so accidental labels, secrets, or internal objects are not
silently passed into the prompt. History and tool items allow extra fields for
stable IDs, timestamps, working directories, exit codes, or receipt hashes.

### Normalization rules

1. Preserve observations, not the worker's private reasoning.
2. Include exact exit status and a compact error signature when a command fails.
3. Mark missing verification as missing; never represent it as success.
4. Include working directory, revision, branch, or checkpoint when stale state
   is plausible.
5. Deduplicate noisy logs while retaining repetition count and whether inputs
   changed.
6. Redact credentials, user data, private prompts, and unnecessary source text.
7. Keep the rendered prompt within 2,048 tokens. The reference runtime rejects
   oversized inputs rather than truncating them.

Failure-signal strings are open vocabulary. Useful examples include
`false_completion_risk`, `missing_verification`, `identical_retry_loop`,
`stale_workspace`, `wrong_working_directory`, `dependency_failure`,
`provider_timeout`, `unsafe_continuation`, and `authority_required`. Signals
should summarize deterministic evidence; they must not encode the desired
answer.

## Framework compatibility

| Harness | Practical fit | Adapter work required |
|---|---|---|
| Custom Python/TypeScript tool loop | Strong | Serialize native events and dispatch the returned action |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/graph-api) | Strong | Build a supervisor node from graph state and route by `action` |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/agents/#lifecycle-events-hooks) | Strong | Summarize tool/run events in a hook or wrapper, then gate continuation |
| [OpenHands SDK/runtime](https://docs.openhands.dev/sdk/api-reference/openhands.sdk.event) | Strong | Convert action/observation events and workspace receipts |
| [AutoGen](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/messages.html) | Moderate | Normalize message/tool events and add explicit recovery transitions |
| CrewAI | Moderate | Wrap task/tool callbacks and implement centralized control semantics |
| Google ADK | Moderate | Normalize session/events and route through a supervisor callback |
| Cursor, Claude Code, Codex CLI, Aider | Wrapper required | Capture their observable events; no native plug-in is shipped here |
| Plain chat UI | Poor | It can answer, but this release is optimized for structured supervision |

This table describes architectural compatibility, not tested official plug-ins.
Framework APIs change; use their current event, callback, trace, and state
interfaces when writing the small normalizer.

## Python: direct in-process use

Load the controller once and reuse it:

```python
from inference import DotReflex

reflex = DotReflex(adapter="usedot/Dot-Reflex-14B")

trajectory = {
    "task_summary": "Fix the authentication regression",
    "execution_history": [
        {
            "step": 1,
            "actor": "agent",
            "action": "Changed auth.py and claimed success.",
            "result": "Patch applied; tests not run.",
        }
    ],
    "tool_results": [
        {"tool": "pytest", "status": "not_run", "summary": "No receipt."}
    ],
    "current_state": "Unverified code change.",
    "detected_failure_signals": ["false_completion_risk"],
}

decision = reflex.predict(trajectory)
if not decision["parse_valid"]:
    raise RuntimeError("Supervisor output was invalid; apply conservative fallback")
```

Do not reload the 14B base for every event. One `DotReflex` instance is intended
to supervise many sequential decisions.

## HTTP client

Run the local service described in `INSTALL.md`, then call it from any language:

```python
import requests

response = requests.post(
    "http://127.0.0.1:8080/v1/decision",
    json=trajectory,
    timeout=30,
)
response.raise_for_status()
decision = response.json()
```

The caller should set a timeout longer than its measured local generation
latency and treat timeouts as supervisor unavailability, not permission to
continue a risky action.

## Dispatch controls safely

The action names are semantic recommendations. Implement them as explicit
harness primitives:

```python
def dispatch(decision, harness):
    action = decision["action"]
    if action == "continue":
        return harness.resume()
    if action == "verify":
        return harness.run_verification(decision["recovery_instructions"])
    if action == "retry_differently":
        return harness.retry_with_changed_method(decision["recovery_instructions"])
    if action == "replan":
        return harness.invalidate_plan_and_replan()
    if action == "rollback":
        return harness.rollback_to_verified_checkpoint()
    if action == "branch":
        return harness.try_in_isolated_branch()
    if action == "switch_model":
        return harness.route_to_alternate_model()
    if action == "ask_human":
        return harness.pause_for_user(decision["rationale"])
    return harness.stop(status=action, receipt=decision)
```

Never implement `rollback` as an unscoped destructive filesystem command.
Never implement `switch_model` as silent cost escalation. Never let `continue`
bypass your deterministic authorization policy.

## Conservative policy layer

The generated confidence is useful telemetry but is not enough for access
control. A production wrapper should define:

- actions that always need human approval;
- commands, paths, networks, and external side effects the agent may access;
- a fallback when Reflex times out or returns invalid JSON;
- maximum retry/replan counts independent of the model;
- verification gates required before `stop_successfully`;
- immutable receipts for input, decision, dispatched action, and outcome.

A sensible fail-closed fallback is `ask_human` for ambiguous privileged work and
`verify` for an unproven completion claim. The correct fallback depends on your
own risk model and must be deterministic.

## Evaluation before deployment

Build a private, independently authored test set from your actual harness
semantics without including secrets or production user content. At minimum,
measure action accuracy, per-class recall, false-stop rate, unsafe-continue rate,
invalid-output rate, calibration, latency, and post-action recovery success.

Do not tune against the published synthetic benchmark and then cite it as an
independent result. Do not ship until rollback, branching, human escalation,
timeouts, and malformed model output have executable tests.
