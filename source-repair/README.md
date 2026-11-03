# Repair Bench — Real-source Challenge 01 (private review build)

**Scope:** demonstrate a real, previously published bug and evaluate a source-level correction with safe controls. This extends the owner-selected Repair Bench project; it is not a new business/project or source contribution. It now also records one live Meta-model attempt and its honest failure (see below).

**Source:** UK AI Security Institute's MIT-licensed [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai), [issue #5971](https://github.com/UKGovernmentBEIS/inspect_ai/issues/5971), snapshot reference `386e099`. Pinned source blobs: `_openai_responses.py` `7bd0cc985e4dae87aac4526cd7410e716734d947`; `_model_output.py` `fa414391f98234d58b1d040cceef84bc96270087`. `upstream/` contains exactly three actual function excerpts, and the exact upstream MIT license is included. All excerpts verified by FNV32 byte-level checks. Not a checkout of the complete project.

## Re-run

From the `repair-bench/` directory (Python 3.11+):

```sh
python3 source-repair/trial/run_trial.py --source upstream
python3 source-repair/trial/run_trial.py --source reference
python3 source-repair/trial/run_trial.py --source cosmetic
python3 source-repair/trial/run_trial.py --source stoponly
python3 source-repair/trial/run_trial.py --source toolsonly
python3 source-repair/trial/metamorphic.py
python3 source-repair/trial/model_request.py
PYTHONPATH=submission python3 -m unittest submission.test_source_repair -v
```

Launch the existing Repair Bench local server with `PYTHONPATH=submission python3 submission/server.py --port 8765` and open `http://127.0.0.1:8765/source-repair` on a machine that permits browser loopback networking. The page **replays recorded results**; it does not run arbitrary code or call Meta. Neither browser URLs nor raw model patches are executable endpoints.

## Results

Frozen source protocol SHA-256: `6ff034733f768b3f972c0ef35079ec122239e981a705f6b82a28207890ffd595`. The *pre-patch* original scored **4/9**; the post-freeze, locally AI-authored reference scored **9/9**. Partial controls scored **5/9** (cosmetic warning only), **4/9** (stop-reason only), **4/9** (call suppression only). Post-repair varied-input checks: original **9/18**, reference **18/18**, controls **10/18, 9/18, 9/18** respectively.

The reference explicitly preserves content filtering as a stop reason, retains a nonempty explanatory stop detail and does not forward calls from incomplete responses. A complete normal tool-call response still forwards calls. For incomplete `max_output_tokens` responses, this reference **conservatively suppresses** partial tool calls; this is a Repair Bench security criterion, not a verified upstream maintainer requirement.

Source patches are *not* a verified replacement for full Inspect integration; the experiment uses real upstream function bodies with deliberately small, locally authored dependency stand-ins. It does not reproduce all users of those functions, real OpenAI SDK output models, or live downstream agent dispatch.

The issue and at least one proposed provider-side fix were public before this test. Therefore this is **not a contamination-free holdout**, does not establish newly discovered vulnerabilities or AI model superiority, and is not eligible to be advertised as a successful Meta repair attempt. A future genuine Meta attempt would need a fair, preferably undisclosed source case and full-system validation to establish added value.

## Model attempt 01 (Meta Muse Spark, in-CLI proposal; owner review)

A Meta-model-generated source patch proposal for this same frozen case is held
for owner review under `source-repair/model_attempt_01/` (`PROPOSAL.json`,
`MODEL_PATCH.diff`, `EVAL_RECORD.json`; freeze record
`trial/FREEZE_MODEL_ATTEMPT_01.md`). It was generated in-CLI after the freeze
(single attempt, no `api.meta.ai` call, no billed usage, no provider receipt)
and scored by the unmodified harness in an isolated secret-free copy: **9/9**
protocol cases and **18/18** supplemental checks, matching the reference and
beating every negative control. Same boundaries as above apply: excerpt-level
evidence only, not a contamination-free holdout, and no model-superiority claim.
The recorded demo page and `results.json` intentionally still replay only the
five pre-model branches.

## Direct Meta attempt (one live `api.meta.ai` call, 2026-11-03)

A single frozen request (`trial/direct_meta_01/request.json`,
SHA-256 `f122a2a0…`) was sent to `muse-spark-1.3` under the owner-authorized
billing amendment in `docs/META_SOURCE_REPAIR_SPEC.md`. The provider returned
one clean-stop completion (response `chatcmpl-01a1a2a2-…`, 6,791 tokens) whose
proposed patch was **rejected at scope review** — its diff hunk headers did
not apply to the frozen excerpts — and was therefore never executed. The same
isolated sandbox run reproduced all five comparator scores and accepted the
operator-supplied candidate 9/9. Transport summary, sandbox observations and
the rejected patch replay in the demo page from sanitized
`source-repair/model-trial.json`; raw provider bytes stay in the gitignored
`trial/.private/` directory. This is a genuine negative result, not a
successful repair, and the contamination and no-superiority boundaries above
still apply.

## Safety/authority

- No imported upstream package or its install scripts were executed.
- The direct model patch was never executed: it failed scope review first. Candidate code reaches the excerpt evaluator only inside disposable network-disabled Docker containers via `trial/sandbox_eval.py`, after the scope gate passes.
- Do not run untrusted patches with the raw Python excerpt evaluator outside that sandbox: it `exec`s code, and its shims are **not a security sandbox**. `trial/model_request.py` only creates an offline, owner-reviewable prompt digest.
- Any further Meta inference, overage, public-source license, GitHub publication, external issue/PR comment or contest submission requires separate approval.
- Preserve the `upstream/LICENSE` notice in any derivative release containing source excerpts.
