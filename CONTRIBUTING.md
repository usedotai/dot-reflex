# Contributing

Dot Reflex welcomes focused fixes to the runtime, trajectory contract,
integration examples, tests, documentation, and evaluation tooling.

## Before opening a pull request

1. Keep model weights and checkpoints out of Git. The canonical adapter lives at
   `usedot/Dot-Reflex-14B` on Hugging Face.
2. Do not include credentials, private prompts, production traces, proprietary
   source code, or user data in issues, tests, or examples.
3. Preserve the distinction between synthetic benchmark results and independent
   transfer or production evidence.
4. Add or update tests for behavior changes.

## Local checks

The contract tests do not download or load model weights:

```bash
python3 -m unittest discover -s tests -v
python3 inference.py examples/trajectory_false_completion.json --validate-only
python3 scripts/validate_release.py
```

Changes to generated charts should include updated raw receipts and a regenerated
`evaluation/chart_receipt.json`. Never edit a metric only in the rendered chart.

## Integration contributions

Framework adapters should remain thin and auditable: normalize observable events
into `trajectory.schema.json`, call the controller, pass the decision through a
deterministic policy gate, and implement recovery controls with recoverable
harness primitives. Do not implement rollback as unscoped deletion or treat model
confidence as authorization.

## Security reports

Do not open a public issue containing an exploitable vulnerability or secret.
Use GitHub's private vulnerability reporting for this repository when available.

