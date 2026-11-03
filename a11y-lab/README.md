# Repair Bench: keyboard-accessibility false-green case
**Prototype review extension — GPT-6 — 2026-10-28. Not a new project or canonical release.**

## Research question
Can independent browser behavior checks reject a *plausible but ineffective* accessibility repair? The test case is a synthetic menu with a mouse-only click target. W3C WCAG 2.2 SC 2.1.1 describes the keyboard-access requirement; this is **not a WCAG conformance suite**.

This extends the existing Repair Bench software-verification demonstration with a *second domain*. It does not claim invention of automated accessibility repair: Deque Axe Accessibility, GitHub's experimental accessibility agent, Evinced Autopilot, and public open-source tools already have repair/verify loops. We do not compete as a generic accessibility agent.

## Safe design
- The candidate is only a 2-field JSON choice from `noop`, `aria_only`, or `native_button`.
- Only a trusted, deterministic HTML transformation touches a specific fixture element; the model never writes/executes code, shell commands, or verifier tests.
- The source fixture is SHA-256 sealed and checked before evaluation.
- `aria_only` is a purposeful false-green: focusable and labeled to look fixed, but Enter still fails.
- A headless Chromium browser checks initial closed state, pointer open/close, keyboard Tab, Enter, Space, focus recovery, semantic HTML, and an accessible visible name. The oracle remains outside the prompt.
- This tests one synthetic case with one browser. It does not establish usability with assistive technology, complete WCAG compliance, model repair skill, safety of arbitrary source code, or production readiness.

## Run (offline; requires Python Playwright and installed Chromium)
```sh
python3 -m unittest discover -s a11y-lab -p 'test_*.py' -v
node tests/run_tests.js
node --test tests/evaluate_mapping.test.js
python3 a11y-lab/meta_model.py --dry-run
```
Example candidate (create only for local evaluation; NOT a model result):
```json
{"schema":"repair-bench.a11y-proposal.v1","repair":"native_button"}
```
Evaluate a file containing that JSON with `python3 a11y-lab/evaluate.py /path/to/candidate.json`.
View the source-only prompt with `python3 a11y-lab/evaluate.py --prompt`.

**Meta adapter:** `python3 a11y-lab/meta_model.py --dry-run` prints a request for `muse-spark-1.3` without network or billing. Live invocation is deliberately off by default and requires the explicit `--live --i-approve-billable-inference` flags and a locally set `MODEL_API_KEY`, in addition to separately checking consent/available billing limits; no live calls were executed while building this extension. Live output is deliberately NOT automatically installed or scored. Manual evidence handling is required.

Official sources: https://dev.meta.ai/events/global-hackathon ; https://dev.meta.ai/docs/cookbook/quickstart-chat-completions ; https://www.w3.org/WAI/WCAG22/Understanding/keyboard .

## 2026-10-28 addendum — single-call evidence runner (GPT-6, review draft)

`meta_trial.py` is a **separate one-call integration** with Meta's current Chat Completions contract. It does NOT run without a locally configured `MODEL_API_KEY` **and** three deliberate CLI switches. The `--credits-confirmed` switch is a **human assertion, not a programmatic credit-balance check**. Only use it after verifying billing and permitted spend directly in the Meta dashboard. Do not share credentials in chat.

Run these offline tests on an appropriate machine first (Python Playwright and Chromium required; if Playwright cannot locate a browser, run `python3 -m playwright install chromium`):

```sh
python3 -m unittest discover -s a11y-lab -p 'test_*.py' -v
node --test tests/evaluate_mapping.test.js
node tests/run_tests.js
python3 a11y-lab/meta_trial.py --dry-run
```

The following is an **example for later use** only, after credits and billing are confirmed and the owner explicitly authorizes a single potentially billable request. It has NOT been executed during this review:

```sh
# On the owner's own machine, in repair-bench/, with MODEL_API_KEY already set privately:
python3 a11y-lab/meta_trial.py --live --credits-confirmed --approve-one-call a11y-lab/trials/muse-spark-first-live.json
```

Before calling Meta, the script checks the sealed fixture and ensures the headless-browser oracle rejects the baseline and accepts the known-safe fixture. If successful, the script makes **exactly one API call**, rejects missing/mismatched model identity and unfinished output, accepts only the two-field JSON candidate, runs the local browser oracle, and writes a new, non-overwriting receipt with model, response ID, usage when available, timestamps, prompt hash, candidate, and per-check results. A real model failure is reported as FAIL; network/model errors are UNKNOWN. The runner executes no model-supplied code. It is **not** an autonomous patch-generation benchmark, screen-reader test or full accessibility compliance assessment. This environment had **no configured API key or verified credit balance**, so no live trial was run here.

Model API reference: https://dev.meta.ai/docs/cookbook/quickstart-chat-completions and https://dev.meta.ai/help/billing/api-bill
