# Verifiable Meta source repair specification

Written before implementation on 2026-11-03. Governing requirements are the
user-supplied execution plan (the execution brief available in this context)
and unchanged `source-repair/trial/PROTOCOL.json`. No separate execution-brief
file was found. The existing attempt's freeze is historical evidence, not
independently verified chronology.

## Acceptance criteria

1. Preserve the existing 84-check baseline and all preexisting tests, oracles,
   seals, upstream excerpts, reference/control patches, results/evidence,
   `model_attempt_01`, and `FREEZE_MODEL_ATTEMPT_01.md` byte for byte. A separate
   hash inventory records those protected bytes. Work locally from PR #1 head;
   no push, publication, waiver, submission, or other upload.
2. Audit the supplied attempt without attributing its authorship, billing,
   freeze chronology, or historical evaluator claims to direct observations.
3. A new exclusive `source-repair/trial/direct_meta_01` reservation freezes
   exact request bytes, problem, full upstream revision
   `386e09942510e93de2db6d108f24f62f65eecbdc`, source/evaluator/protocol hashes,
   permitted edits and acceptance rules before transport. Fsync files and
   directory. Duplicate attempts cannot send; uncertain outcomes cannot retry.
4. Send only public upstream excerpts and all frozen behavioral requirements,
   including incomplete-call suppression. Exclude existing candidates,
   reference/control patches and supplemental tests. Request JSON containing
   diagnosis, an actual unified diff, risks and suggested tests; standard
   `muse-spark-1.3`, n=1, medium reasoning, 8192 completion tokens, no tools,
   no streaming, store=false. Use the documented Chat Completions endpoint.
5. Credential transport cannot import, apply or execute candidate code. Deny
   transport unless credentials and independently verified provider-enforced
   prevention of paid overage are available. A flag, local assertion, token
   limit or inferred credit balance is insufficient. Never resend failures or
   uncertain outcomes; disable retries, redirects and credential-bearing logs.
6. Retain private exact response/request bytes, hashes, timestamps, identity,
   IDs, finish reason, usage with nested counters and exact patch. Export only
   allowlisted sanitized metadata. Malformed, truncated and mismatched results
   are preserved and rejected. No private response fields or secrets in demo.
7. Validate a strict unified diff for the three excerpt filenames only;
   reject traversal, renames, binary changes, symlinks, extra top-level code,
   interface changes and evaluator access. Preserve rejected bytes unchanged.
   Review side effects before any execution. Keep collector behavior intact.
8. Evaluate only in disposable network-disabled containers: no credentials,
   checkout or Docker socket mount; read-only inputs/root, explicit clean env,
   unprivileged user, dropped capabilities, resource/time/output limits.
   Benign probes must establish isolation before execution. Use unchanged
   `run()` and `metamorphic.run()`, never their evidence-overwriting CLI.
9. Evaluate supplied and direct candidates separately. Under the same
   configuration reproduce comparator scores 4/9, 9/9, 5/9, 4/9, 4/9. Acceptance
   requires nine frozen checks plus scope. Report the 18 supplemental checks
   separately. Retain observations, failures, exit codes, image digest,
   configuration and source hashes; unavailable prerequisites are blockers.
10. Add only a fixed read-only `/source-repair/model-trial.json` route. Replay
    direct transport, independent sandbox, model statements and supplied
    historical records distinctly; display real scores/usage/IDs/patch hash
    only when present. Patch text must be inert. Support success, failure,
    missing and invalid evidence. No inference/source execution HTTP endpoint.
11. Fix the Menu/Dialog preview iframe title. Keep synthetic tasks described
    as predetermined choices. Update claims only to match observed evidence.
12. Run baseline checks in disposable copies, separate new transport/scope/
    replay tests, JavaScript syntax checks and protected hash verification.
    Distinguish actual HTTP browser verification from restricted replay.

## Amendment 2026-11-03 — owner-authorized billing prerequisite change

Finding: Meta's help center (fetched 2026-11-03,
https://dev.meta.ai/help/billing/spend-limit-alert) states the Model API
"doesn't currently offer a spending limit that places a hard cap on usage";
spend limits are email alerts and billing is in arrears on a card. No
provider-enforced prevention of paid overage exists to verify, so criterion
5 as written can never pass and would block the live trial permanently.

Owner decision: accept the bounded single-call cost risk. The frozen
request is 9,227 bytes; the call is n=1, max 8,192 completion tokens, no
tools, no streaming, no retries, no resends — roughly 11k tokens maximum
for the single attempt. Replacement gate: transport proceeds only with an
owner-authored `billing_authorization.json` in the attempt directory whose
exact request SHA-256, scope string and risk-acceptance flag verify.
A missing, malformed or mismatched file still denies transport. All other
criteria are unchanged. The pre-amendment reservation (request
`f122a2a0…`, never sent) was cleared and re-frozen after this edit; the
re-reservation must reproduce the identical request hash to prove the
request bytes did not change.

## Shared replay evidence contract (v1)

`source-repair/model-trial.json` is a sanitized local artifact, never raw provider
data. Fields: `schema_version: 1`, `status` (`blocked`, `failed`, `completed`),
`blockers: [string]`, `transport` (status, requested_model, returned_model,
response_id, provider_request_id, finish_reason, usage, request_sha256,
response_sha256, patch_sha256; nullable values), `comparisons` (map of branch to
`{protocol: <run() result>, supplemental: <metamorphic.run() result>}`),
`candidates` (map `operator_supplied` and `direct_meta` to `{status, provenance,
patch, patch_sha256, protocol, supplemental, scope}`), `audit` (claims and
limitations), `validation` (observations). Missing outcomes remain null.
Sanitizers must reject malformed records rather than imply success.
