# Repair Bench — Real-source Challenge 01 (private review build)

**Scope:** demonstrate a real, previously published bug and evaluate a source-level correction with safe controls. This extends the owner-selected Repair Bench project; it is not a new business/project, source contribution, or Meta-model result.

**Source:** UK AI Security Institute's MIT-licensed [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai), [issue #5971](https://github.com/UKGovernmentBEIS/inspect_ai/issues/5971), snapshot reference `386e099`. Pinned source blobs: `_openai_responses.py` `7bd0cc985e4dae87aac4526cd7410e716734d947`; `_model_output.py` `fa414391f98234d58b1d040cceef84bc96270087`. `upstream/` contains exactly three actual function excerpts, and the exact upstream MIT license is included. All excerpts verified by FNV32 byte-level checks. Not a checkout of the complete project.

## Re-run

From the `repair-bench/` directory (Python 3.11+):

```sh
python source-repair/trial/run_trial.py --source upstream
python source-repair/trial/run_trial.py --source reference
python source-repair/trial/run_trial.py --source cosmetic
python source-repair/trial/run_trial.py --source stoponly
python source-repair/trial/run_trial.py --source toolsonly
python source-repair/trial/metamorphic.py
python source-repair/trial/model_request.py
PYTHONPATH=submission python -m unittest submission.test_source_repair -v
```

Launch the existing Repair Bench local server with `PYTHONPATH=submission python submission/server.py --port 8765` and open `http://127.0.0.1:8765/source-repair` on a machine that permits browser loopback networking. The page **replays recorded results**; it does not run arbitrary code or call Meta. Neither browser URLs nor raw model patches are executable endpoints.

## Results

Frozen source protocol SHA-256: `6ff034733f768b3f972c0ef35079ec122239e981a705f6b82a28207890ffd595`. The *pre-patch* original scored **4/9**; the post-freeze, locally AI-authored reference scored **9/9**. Partial controls scored **5/9** (cosmetic warning only), **4/9** (stop-reason only), **4/9** (call suppression only). Post-repair varied-input checks: original **9/18**, reference **18/18**, controls **10/18, 9/18, 9/18** respectively.

The reference explicitly preserves content filtering as a stop reason, retains a nonempty explanatory stop detail and does not forward calls from incomplete responses. A complete normal tool-call response still forwards calls. For incomplete `max_output_tokens` responses, this reference **conservatively suppresses** partial tool calls; this is a Repair Bench security criterion, not a verified upstream maintainer requirement.

Source patches are *not* a verified replacement for full Inspect integration; the experiment uses real upstream function bodies with deliberately small, locally authored dependency stand-ins. It does not reproduce all users of those functions, real OpenAI SDK output models, or live downstream agent dispatch.

The issue and at least one proposed provider-side fix were public before this test. Therefore this is **not a contamination-free holdout**, does not establish newly discovered vulnerabilities or AI model superiority, and is not eligible to be advertised as a successful Meta repair attempt. A future genuine Meta attempt would need a fair, preferably undisclosed source case and full-system validation to establish added value.

## Safety/authority

- No imported upstream package or its install scripts were executed.
- No model output is executed. `trial/model_request.py` only creates an offline, owner-reviewable prompt digest.
- Do not run untrusted patches with this Python excerpt evaluator: it `exec`s code, and its shims are **not a security sandbox**. Only the pinned upstream snippets and our locally reviewed reference/control variants were run here.
- Any real Meta inference, overage, public-source license, GitHub publication, external issue/PR comment or contest submission requires separate approval.
- Preserve the `upstream/LICENSE` notice in any derivative release containing source excerpts.
