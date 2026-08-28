# Base-model selection record

Date checked: 2026-08-22

## Selected first run

`Qwen/Qwen3-14B-Base` at revision
`0b0bd3732e2c374d483664439ea334928b65f304`.

Reasons:

- 14B base (not generic assistant instruction tuning).
- Apache-2.0 model license, confirmed in official repository metadata.
- Public and ungated at selection time.
- Text-only architecture matches the trajectory-supervision task.
- Direct support in Hugging Face Transformers reduces integration risk.

Official sources:

- https://huggingface.co/Qwen/Qwen3-14B-Base
- https://huggingface.co/Qwen/Qwen3-14B-Base/blob/main/LICENSE

## Evaluated alternative

`mistralai/Ministral-3-14B-Base-2512` is also Apache-2.0 and suitable for
post-training. It includes a 0.4B vision encoder that is unnecessary for the
first text-only controller run and adds avoidable integration surface.

Official source:

- https://huggingface.co/mistralai/Ministral-3-14B-Base-2512

## Reproducibility note

Licenses and upstream revisions can change. The selected revision and copies of
the relevant license metadata are recorded with the run artifacts. No model or
adapter will be published without explicit approval.

Release note, 2026-08-27: publication of this adapter was subsequently approved
by the project owner. The dated selection record above is otherwise unchanged.
