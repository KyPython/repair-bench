# Repair Bench — Prove the Fix

**Status:** public-source REVIEW CANDIDATE, not published or submitted. AI-assisted code and tests.

Repair Bench is a local, sealed behavioral verification demonstration. A proposed fix is not accepted because it looks convincing; Chromium must observe actual pointer/keyboard/focus behavior. Two synthetic accessibility challenges (menu and dialog) offer three trusted declarative options each. Unchanged and cosmetic-ARIA repairs are rejected; functional repairs are accepted. A separate original sealed game-world benchmark rejects rule-bypassing cheats.

**Current limitations:** no authenticated Meta inference has been performed for this entry; a dry-run/mocked API contract is not a live model result. This is NOT a general autonomous source-code repair system, WCAG certification, benchmark of model quality, real-user accessibility study, or production deployment. The menu and dialog use predetermined trusted transforms.

## Run local demo

Requires Python 3, Node for tests, and Playwright Chromium. From project root:

```sh
python3 -m pip install -r submission/requirements.txt
python3 -m playwright install chromium
python3 submission/server.py --port 8765
# Open http://127.0.0.1:8765/
```

The browser UI and server **do not invoke Meta or read API keys**. A separately authorized one-shot model experiment can be prepared with `python3 a11y-lab/meta_trial.py --dry-run` (no network). It requires operator-controlled `MODEL_API_KEY`, independently reviewed billing/credits, explicit approval and a durable one-shot journal to run live. The CLI's `--credits-confirmed` flag is NOT an enforced spend cap. Never publish credentials or an unredacted provider receipt.

## Tests

```sh
node tests/run_tests.js
node --test tests/evaluate_mapping.test.js
python3 -m unittest discover -s a11y-lab -p 'test_*.py' -v
PYTHONPATH=submission python3 -m unittest discover -s submission -p 'test_*.py' -v
node --check submission/app.js
```

The browser world test may report `CHROMIUM_HTTP_ASSET_REPLAY_CSP_CONTRACT_ONLY` if localhost navigation is blocked; that is NOT equivalent to a real HTTP browser/CSP test. See [world regression test limitations](docs/WORLD_BROWSER_REGRESSION.md).

## Source provenance and licensing

Original project sources are AI-assisted with the project owner's direction. This source-only candidate contains no private Taniti accessibility scan evidence, model account data, or other private workflow attachments. A repository license has **not** been chosen or granted by this package. Public release requires the owner to choose/review the license and third-party rights, check pre-event work eligibility, and approve the exact source.

Meta Global AI Developer Hackathon deadline: November 4, 2026 at 9:00 PM ET, per [official event page](https://dev.meta.ai/events/global-hackathon). A genuine model result, verified event eligibility, public repository, authentic three-minute YouTube demo, and final signed-in form submission are **still required**.

## Experimental real-source safety repair (private review only)

The local judge now has an additional read-only `/source-repair` experience for Inspect AI's publicly reported filtered-response/tool-call bug. It compares the actual pinned function behavior, a locally generated reference patch, and three negative controls through **frozen source-derived tests**. Details and licensing: [source-repair/README.md](source-repair/README.md). This is not a successful Meta generation, a hidden benchmark, or a full upstream integration. No untrusted code execution is exposed via HTTP.
