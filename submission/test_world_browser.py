"""Actual Chromium execution of the original sealed world served by the local HTTP app.

Browser-level navigation is attempted first. In restricted CI environments where
navigation returns ERR_BLOCKED_BY_ADMINISTRATOR, the same HTTP-served world and
scripts are loaded into Chromium through set_content. This fallback verifies JS
initialization, canvas drawing, and anti-cheat acceptance but cannot itself
prove that the browser processed an HTTP CSP header. A separate server contract
test asserts the exact CSP and every external same-origin import.

Observation uses CDP-level APIs only (locators, text matching, screenshots):
the asserted policy forbids 'unsafe-eval', so page.evaluate and
wait_for_function string predicates cannot run inside the page.
"""
from __future__ import annotations
import hashlib
import http.client
import json
import re
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import os
from PIL import Image
from playwright.sync_api import sync_playwright, Error as PlaywrightError

from server import Handler

SRC_PATTERN = re.compile(r'<script src="([^"<>]+)"></script>')
REQUIRED_SCRIPTS = (
    'src/world.js', 'src/physics.js', 'src/victory.js', 'src/replay.js',
    'src/harness.js', 'patches/seeded_defect_v1.js',
    'patches/fixture_repair.js', 'patches/cheat_autopilot.js'
)


def count_nonuniform_png_pixels(raw: bytes) -> int:
    """Pixels differing from the top-left pixel.

    A blank canvas renders a uniform fill, so any drawn grid, wall, goal or
    player raises this count.
    """
    with Image.open(BytesIO(raw)) as img:
        pixels = list(img.convert('RGB').getdata())
    baseline = pixels[0]
    return sum(1 for pixel in pixels if pixel != baseline)


class WorldBrowserRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()
        cls.port = cls.srv.server_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.th.join(timeout=5)

    def http(self, path):
        con = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        con.request('GET', path)
        res = con.getresponse()
        data = res.read()
        result = (res.status, dict(res.getheaders()), data)
        con.close()
        return result

    def test_world_csp_serves_all_trusted_scripts_without_weakening_fixtures(self):
        status, headers, body = self.http('/world')
        self.assertEqual(status, 200)
        policy = headers['Content-Security-Policy']
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn("connect-src 'self'", policy)
        self.assertIn("default-src 'none'", policy)
        self.assertIn("base-uri 'none'", policy)
        self.assertNotIn('unsafe-eval', policy)
        self.assertNotIn('https:', policy)
        srcs = SRC_PATTERN.findall(body.decode())
        self.assertEqual(tuple(srcs), REQUIRED_SCRIPTS)
        for src in srcs:
            code, _, data = self.http('/' + src)
            self.assertEqual(code, 200, src)
            self.assertGreater(len(data), 15, src)
        self.assertEqual(self.http('/tests/integrity_manifest.json')[0], 200)
        # Untrusted standalone fixture remains inline-script-only.
        _, fixture_headers, _ = self.http('/api/fixture?repair=noop')
        fixture_policy = fixture_headers['Content-Security-Policy']
        self.assertIn("script-src 'unsafe-inline'", fixture_policy)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", fixture_policy)

    def test_world_canvas_and_replay_run_in_chromium(self):
        status, headers, raw = self.http('/world')
        self.assertEqual(status, 200)
        html = raw.decode()
        scripts = SRC_PATTERN.findall(html)
        errors = []
        with sync_playwright() as p:
            configured = os.environ.get('RB_CHROMIUM')
            binary = configured or ('/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None)
            browser = p.chromium.launch(headless=True, **({'executable_path': binary} if binary else {}))
            try:
                page = browser.new_page(viewport={'width': 1200, 'height': 850})
                page.on('pageerror', lambda err: errors.append(str(err)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                try:
                    response = page.goto(f'http://127.0.0.1:{self.port}/world', wait_until='load', timeout=15000)
                    self.assertEqual(response.status, 200)
                    mode = 'HTTP_NAVIGATION'
                except PlaywrightError as exc:
                    if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(exc):
                        raise
                    # CI's browser administrator forbids navigation even to localhost.
                    # Use unmodified HTTP-served JS and HTML in actual Chromium.
                    # This mode is NOT evidence of real HTTP CSP enforcement.
                    mode = 'CHROMIUM_HTTP_ASSET_REPLAY_CSP_CONTRACT_ONLY'
                    assets = {}
                    for src in set(scripts + ['tests/integrity_manifest.json'] +
                                   list(json.loads(self.http('/tests/integrity_manifest.json')[2]))):
                        asset_status, _, asset = self.http('/' + src)
                        self.assertEqual(asset_status, 200, src)
                        assets[src] = asset.decode()
                    # fetch and digest only replace browser transport and unavailable
                    # WebCrypto on about:blank; they do not replace oracle logic.
                    # Injected via CDP before page scripts run, so the page CSP
                    # (which forbids unsafe-eval) does not block installation.
                    page.expose_function('__rb_browser_digest', lambda text: list(hashlib.sha256(text.encode()).digest()))
                    page.add_init_script('''const __rb_assets = ''' + json.dumps(assets) + '''; {
                      window.fetch = async (path) => {
                        if (!(__rb_assets.hasOwnProperty(path))) throw Error('asset blocked:' + path);
                        return new Response(__rb_assets[path], {status:200});
                      };
                      Object.defineProperty(crypto, 'subtle', {value: {
                        digest: async (_algo, bytes) => new Uint8Array(await window.__rb_browser_digest(new TextDecoder().decode(bytes))).buffer
                      }, configurable:true});
                    }''')
                    # Inline exact trusted scripts in source order, preserving the
                    # original world JS unchanged and executing it inside Chromium.
                    html = SRC_PATTERN.sub(lambda match: '<script>\n' +
                                           assets[match.group(1)].replace('</script', '<\\/script') +
                                           '\n</script>', html)
                    policy = headers['Content-Security-Policy'].replace("; frame-ancestors 'self'", '')
                    html = html.replace('</head>',
                        '<meta http-equiv="Content-Security-Policy" content="' + policy + '"></head>', 1)
                    page.set_content(html, wait_until='load', timeout=15000)
                canvas = page.locator('#cv')
                log = page.locator('#log')
                canvas.wait_for(timeout=5000)
                self.assertEqual([canvas.get_attribute('width'), canvas.get_attribute('height')], ['600', '480'])
                # Manifest fetch plus first draw complete once the canvas is
                # non-uniform; poll screenshots since in-page reads are CSP-blocked.
                deadline = time.monotonic() + 10
                drawn_pixels = 0
                while time.monotonic() < deadline:
                    drawn_pixels = count_nonuniform_png_pixels(canvas.screenshot(timeout=5000))
                    if drawn_pixels > 100:
                        break
                    time.sleep(0.25)
                self.assertGreater(drawn_pixels, 100,
                                   'canvas never rendered a non-uniform world scene')
                page.locator('#b2').click()
                page.get_by_text('Cheat rejected as designed').wait_for(timeout=8000)
                self.assertIn('Verdict: REJECTED', log.inner_text())
                page.locator('#b3').click()
                page.get_by_text('Fixture accepted').wait_for(timeout=8000)
                self.assertIn('Verdict: ACCEPTED', log.inner_text())
                self.assertFalse(errors, f'Browser exceptions/console errors ({mode}): {errors[:5]}')
                if os.environ.get('RB_WORLD_SCREENSHOT'):
                    page.screenshot(path=os.environ['RB_WORLD_SCREENSHOT'], full_page=True)
                print(f'WORLD_BROWSER_MODE={mode}; scripts={len(scripts)}; canvas=rendered; cheat=REJECTED; repair=ACCEPTED')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
