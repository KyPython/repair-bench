# Direct Meta attempt 02 — runbook and outcome record

Status: COMPLETED 2026-11-03 as a second negative result (see Outcome below).
Attempt 01 is consumed and preserved byte for byte; nothing here resends it.

## Why attempt 01 failed, and what 02 would change

Attempt 01 (`source-repair/trial/direct_meta_01/`) returned a clean `muse-spark-1.3`
completion whose patch failed scope review ("Hunk context mismatch"): its diff hunk
headers did not apply to the frozen excerpts, so it was never executed. The failure
was in diff formatting, not in the diagnosis.

Attempt 02 is NOT a resend. A resend of the same request bytes is forbidden by
`docs/META_SOURCE_REPAIR_SPEC.md` criterion 5. Attempt 02 would be a NEW reservation
with NEW request bytes containing tightened diff-format instructions (exact
`--- a/<file>` / `+++ b/<file>` headers, hunk context quoted verbatim from the
supplied excerpts, no renaming, no extra files), a new request SHA-256, and a new
owner billing authorization bound to that SHA.

## Recommendation

Sequence this AFTER the video is recorded, captioned, uploaded, and the form is
submitted. Rationale: the current evidence (one real API call with provider receipt,
honest negative result, full pipeline replay) already supports the entry's Meta story,
and the video is the deadline-critical artifact. Attempt 02 is optional upside with
real time cost: a second negative changes nothing, and a success needs full sandbox
evaluation plus evidence composition tonight. If the video is done with hours to spare,
run this. Otherwise decline it.

## Hard requirements (all must hold or transport denies)

1. Owner shell (not the agent sandbox) with `MODEL_API_KEY` configured. The agent
   must never see, log, or persist the key.
2. Spec amendment: the owner approves extending `docs/META_SOURCE_REPAIR_SPEC.md`
   to a second exclusive reservation (`direct_meta_02`), same model, n=1, 8192
   completion tokens, no tools, no streaming, no retries, no resends. Draft text:
   "Amendment 2026-11-03 (second attempt): one further exclusive reservation
   `direct_meta_02` with newly frozen request bytes is authorized under criteria
   3-10 unchanged. Attempt 01 evidence stays byte-identical. No third attempt
   without a new amendment."
3. Harness parameterization: `source-repair/trial/direct_transport.py` currently
   hardcodes `direct_meta_01` in `reserve_attempt`, `send_reserved`, and `AUTH_SCOPE`.
   A 02 attempt needs a parameterized copy (new module, e.g. `direct_transport_02.py`;
   do NOT edit the 01 module, which is hashed in 01's manifest). The new module must
   enforce the identical gates with `direct_meta_02` scope.
4. Owner-authored `billing_authorization.json` in `direct_meta_02/`, schema-identical
   to 01's, with scope `direct_meta_02 single send, n=1, max_completion_tokens=8192,
   no retries`, the NEW request SHA-256, `owner_accepts_bounded_cost_risk: true`, and
   an `authorized_utc` timestamp. The agent may display the required SHA; the owner
   writes the file.
5. Protected bytes untouched: `PROTOCOL.json`, upstream excerpts, `run_trial.py`,
   `metamorphic.py`, all of `direct_meta_01/`, `model_attempt_01/`, results/evidence.
   Verify with the protected-hash check before and after.

## Execution sequence (owner shell)

```sh
cd /Users/ky/repair-bench
# 0. Baseline green first (RB_CHROMIUM set, all suites pass).
# 1. Freeze the new request (no network, no credentials read):
python3 source-repair/trial/direct_transport_02.py --prepare
#    Expected request SHA-256 (computed 2026-11-03 from frozen inputs; the
#    printed manifest must match exactly or STOP — inputs changed):
#    56cf4bd2d391acd3419314ec7211d6b86bf09646e558e3c8d29f8b37fa87227f
# 2. Owner hand-writes source-repair/trial/direct_meta_02/billing_authorization.json:
#    {"schema_version": 1,
#     "scope": "direct_meta_02 single send, n=1, max_completion_tokens=8192, no retries",
#     "request_sha256": "<sha from step 1>",
#     "owner_accepts_bounded_cost_risk": true,
#     "authorized_utc": "<now, ISO-8601, max 64 chars>"}
# 3. Preflight (must report ready, zero blockers):
python3 source-repair/trial/direct_transport_02.py --preflight
# 4. Single send (consumes the reservation whatever happens; no retry):
python3 source-repair/trial/direct_transport_02.py --send
# 5. Scope review, then disposable-container sandbox eval only if scope passes.
# 6. Compose sanitized evidence into model-trial.json candidates.direct_meta_02;
#    keep candidates.direct_meta (01) unchanged. Replay both distinctly.
# 7. Re-run the full suite; confirm the video's claims still match (update the
#    script's Meta beat ONLY to what the evidence shows, honest either way).
```

Cost bound: same shape as 01 — one call, ~11k tokens maximum. Provider offers no
enforceable cap (alerts only); the bound is the frozen request plus owner risk
acceptance, as in 01.

## Outcome (recorded 2026-11-03)

Second negative result. The frozen request (`56cf4bd2…`, 9,786 bytes) was sent to
`muse-spark-1.3` at 21:22:31 UTC; the provider returned HTTP 200, response
`chatcmpl-01a1a34b-841f-76ee-b62b-85bd52867aa1`, clean stop, 7,962 tokens total
(2,027 prompt, 5,935 completion incl. 5,499 reasoning). The validated proposal's
patch (784 bytes, `aefbd9ff…`) failed scope review with the same reason as 01 —
hunk context mismatch — despite the tightened format instructions, and was never
executed. No sandbox run was launched per the runbook's scope-gate sequencing; no
retry is permitted. Evidence: `source-repair/trial/direct_meta_02/` (request,
manifest, billing authorization, send claim, transport summary, events,
`scope_review.json`); raw provider bytes in gitignored `trial/.private/`.
Attempt 01's directory is byte-identical. The video states both attempts as
bounded usage with two genuine negative results.

## Outcome handling (pre-registered)

- Scope rejection or sandbox failure: record as a second negative result. The video's
  framing already holds; add one line ("a second attempt with tightened format
  instructions was likewise rejected at <stage>") only with evidence in hand.
  (This branch fired; the video's Meta beat now covers both attempts.)
- 9/9 acceptance: genuine positive result on a non-holdout case (contamination and
  no-superiority boundaries from source-repair/README.md still apply). Update the
  video's Meta beat before recording, or re-record that beat.
- Uncertain transport outcome: no retry, per criterion 5. Record and stop.
