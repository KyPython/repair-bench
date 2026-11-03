# Local judge demo

Run from repository root: `python3 submission/server.py --port 8765` after installing `submission/requirements.txt` and Playwright Chromium. Browse `http://127.0.0.1:8765/`. This server binds loopback, executes only sealed trusted fixture alternatives, and makes no Meta API requests. Model receipts displayed through `RB_META_TRIAL_RECEIPT` are expressly operator-supplied and not independently provider-authenticated. A read-only `/source-repair/model-trial.json` route replays sanitized source-trial evidence; the server performs no model inference and exposes no code-execution endpoint.

Tests: `PYTHONPATH=submission python3 -m unittest discover -s submission -p 'test_*.py' -v`. For the world Chromium regression, a restricted-browser fallback is labeled replay and does not prove real HTTP CSP enforcement.
