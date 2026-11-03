# Original world runtime — CSP regression

The original sealed `index.html` imports eight local JavaScript assets. A previous `submission/server.py` reused the standalone fixture CSP (`script-src 'unsafe-inline'`), blocking all eight imports and producing a blank canvas despite HTTP 200 responses.

The trusted **`/world` response only** now uses `script-src 'self' 'unsafe-inline'` (the original world has both external and inline scripts) and `connect-src 'self'` (the original world fetches its integrity manifest and source files). It still uses `default-src 'none'`, forbids remote scripts and evaluation, and retains other origin restrictions. Untrusted `/api/fixture` previews have their separate, stricter inline-only CSP.

`submission/test_world_browser.py` verifies the actual HTTP header and all eight script asset responses, **then launches headless Chromium**. It attempts navigation to the live `/world` endpoint and checks a nonblank canvas, the initialized `RBWorld` global, and REJECTED/ACCEPTED results from the original unchanged cheat/repair buttons.

In browser environments forbidding localhost navigation (`ERR_BLOCKED_BY_ADMINISTRATOR`), the test *explicitly* falls back to executing the actual HTTP-served HTML and scripts in Chromium via `set_content`, with a test-only fetch/digest bridge. The fallback verifies behavior and the separate HTTP CSP contract but **is not proof of HTTP CSP enforcement in the browser**. It reports its mode on stdout; the desired release-evidence mode on a normal CI runner is `HTTP_NAVIGATION`.

Verified 2026-11-03 in `HTTP_NAVIGATION` mode on the owner's machine (`RB_CHROMIUM` pointing at system Chrome, since Playwright's bundled Chromium 120 crashes on this macOS release): 8 scripts, canvas rendered, cheat REJECTED, repair ACCEPTED. Test observation uses CDP-level APIs only (locators, text matching, screenshots, init scripts), because the asserted policy forbids `unsafe-eval` and in-page `evaluate` strings cannot run under it.

Run it with:

```sh
PYTHONPATH=submission python3 -m unittest submission.test_world_browser -v
```

This is test-only infrastructure; no sealed original world HTML, physics or oracle source was modified for the fix.
