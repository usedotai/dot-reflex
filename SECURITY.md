# Security and deployment boundaries

Dot Reflex recommends an execution control from supplied trajectory evidence.
It is not a sandbox, policy engine, permission system, malware detector, or
substitute for human authorization.

## Never pass these into the model

- API keys, passwords, private keys, session cookies, or access tokens.
- Raw private user prompts or production conversations without explicit lawful
  purpose, minimization, and consent.
- Entire proprietary repositories when a compact outcome summary is sufficient.
- Provider invoices, internal host addresses, or infrastructure credentials.

Redact at the event normalizer before constructing the trajectory. Prompt-side
instructions are not a security boundary.

## Required external controls

- Run tools in a least-privilege sandbox.
- Enforce path, network, command, and side-effect permissions independently.
- Require explicit approval for destructive or externally visible actions.
- Implement rollback with recoverable checkpoints, never unscoped deletion.
- Put deterministic retry and cost ceilings around the agent loop.
- Treat invalid JSON, timeouts, and model unavailability as explicit failures.
- Store auditable input, decision, dispatched action, and outcome receipts.
- Add authentication, TLS, rate limits, and payload limits before exposing the
  reference HTTP server beyond localhost.

## Untrusted trajectory content

Tool output, repository text, web content, and agent messages can contain prompt
injection. Dot Reflex does not make untrusted content safe. Summarize observed
outcomes structurally, preserve relevant error evidence, and keep authorization
rules outside the language model.

## High-impact domains

Do not autonomously use this research release to authorize destructive,
financial, medical, legal, surveillance, weapons, or offensive security actions.
Use deterministic policy and qualified human review appropriate to the domain.

## Reporting

When reporting a vulnerability, include the version, runtime, minimal redacted
trajectory, raw generation, dispatched behavior, and whether the issue reproduces
with greedy decoding. Do not include active secrets or private user data.

