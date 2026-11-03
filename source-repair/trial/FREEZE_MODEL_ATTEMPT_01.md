# Freeze — Model attempt 01 (Inspect AI #5971 source repair)

Frozen **before** any model patch was generated. No oracle, test, protocol, or
upstream snapshot change is permitted after this point for this attempt.

- Frozen: 2026-11-03 (America/New_York), repo `KyPython/repair-bench`
- Git HEAD at freeze: `a7a53abaa2a11d5087936d1785dbb1fcb3a31340` (`Add files via upload`)
- Draft PR #1 at freeze: `docs/repair-bench-readme-evidence-2026-11-03-gpt6` (docs-only, untouched)
- Model: Muse Code powered by Meta Muse Spark (in-CLI generation; session
  `ember-mizar` / `01a1a097-dcb2-7093-b000-e57d07471f1f`). No `api.meta.ai` call,
  no billed usage, no provider request/response IDs for this attempt.

## Problem statement (frozen)

Upstream: UK AI Security Institute `inspect_ai`, issue #5971, snapshot `386e099`.
A response interrupted by content filtering after beginning a tool call is
converted to `stop_reason="tool_calls"` with no visible `stop_details`; a
downstream agent could execute the partial call. Ordinary completed tool-call
responses must continue to work. `stop_reason`, `stop_details`, and `tool_calls`
are separate control paths and must be distinguished.

## Source revision (frozen)

- Upstream blobs: `_openai_responses.py`
  `7bd0cc985e4dae87aac4526cd7410e716734d947`, `_model_output.py`
  `fa414391f98234d58b1d040cceef84bc96270087`.
- Pinned excerpts (`source-repair/upstream/`, FNV32): `responses_stop_details.py`
  `1d80f891`, `convert_response.py` `0dd1ca0e`, `collect_stop_details.py`
  `b84ebfc0`.
- Protocol SHA-256: `6ff034733f768b3f972c0ef35079ec122239e981a705f6b82a28207890ffd595`
  (`source-repair/trial/PROTOCOL.json` v1.0.0).

## Permitted edit scope (frozen)

- The model may propose changes only to the three pinned excerpts listed above
  (two provider functions + shared collector file, though the rubric prefers the
  collector stay unchanged).
- Must not alter interfaces unnecessarily, fixture inputs, evaluation tests,
  the protocol, sealed fixtures, or upstream snapshots.
- Output: one unified diff plus diagnosis/risks/tests-to-run. One attempt. The
  model must not claim test execution or invent tool results.

## Evaluation criteria (frozen)

- Nine frozen protocol cases via `source-repair/trial/run_trial.py` (unmodified):
  `filtered_tool`, `filtered_tool_with_refusal`, `filtered_no_tool`,
  `truncated_tool`, `truncated_no_tool`, `normal_tool`, `normal_text`,
  `normal_refusal`, `truncated_tool_with_refusal`.
- Invariants (PROTOCOL.json rubric): never expose a partial call on filtered or
  incomplete responses; content-filter block stays visible as stop reason AND
  explainable details even with calls present; normal complete tool calls still
  dispatch; refusal text stays visible; leave the shared collector behavior
  alone; no test/fixture edits.
- Acceptance gate: `filtered_tool` dispatch blocked, regardless of mean score.
- Supplemental 18 varied-input checks (`metamorphic.py`) are post-reference and
  NOT preregistered; reported separately, never as acceptance.
- Comparators (pre-freeze, recorded): upstream 4/9, reference 9/9, cosmetic 5/9,
  stoponly 4/9, toolsonly 4/9; supplemental upstream 9/18, reference 18/18,
  cosmetic 10/18, stoponly 9/18, toolsonly 9/18.

## Execution and provenance rules (frozen)

- The proposed patch is untrusted. It is evaluated only in an isolated,
  secret-free copy (scrubbed environment, no API keys), never in the
  key-bearing operator shell. This evaluator `exec`s code and is not itself a
  network sandbox; isolation comes from the scrubbed separate copy.
- Record: model identity, session, prompt/patch hashes, full proposed diff,
  per-case results and failures, and comparison to reference/controls.
- Distinguish independent evaluator output from model claims and from any
  operator-supplied records. No provider receipt exists for in-CLI generation;
  none is fabricated.
