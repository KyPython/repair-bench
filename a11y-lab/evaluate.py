#!/usr/bin/env python3
"""Repair Bench cross-domain behavioral verifier — GPT-6, 2026-10-28.
Candidate is a declarative choice; NO candidate-supplied code is executed.
The browser executes only locally trusted fixture JavaScript, not model code.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAX_BYTES = 2048
SCHEMA = "repair-bench.a11y-proposal.v1"
OPTIONS = ("noop", "aria_only", "native_button")
ORIGINAL_TAG = '<div id="open-menu" data-repair-target="menu-trigger" aria-expanded="false" aria-controls="panel">Open menu</div>'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source() -> str:
    data = (HERE / 'mouse_only.html').read_bytes()
    seal = json.loads((HERE / 'fixture_seal.json').read_text(encoding='utf-8'))
    if digest(data) != seal.get('a11y-lab/mouse_only.html'):
        raise ValueError('SEAL_FAIL: baseline fixture changed; refuse to evaluate')
    src = data.decode('utf-8')
    if src.count(ORIGINAL_TAG) != 1:
        raise ValueError('BASELINE_FAIL: unexpected repair target')
    return src


def parse_proposal(data: bytes) -> dict[str, str]:
    if len(data) > MAX_BYTES:
        raise ValueError('candidate exceeds 2048 byte limit')
    try:
        proposal = json.loads(data)
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError('candidate must be JSON, not executable code') from e
    if type(proposal) is not dict or set(proposal) != {'schema', 'repair'}:
        raise ValueError('candidate must contain exactly schema and repair')
    if proposal['schema'] != SCHEMA or type(proposal['repair']) is not str or proposal['repair'] not in OPTIONS:
        raise ValueError('unsupported candidate schema or repair')
    return proposal


def apply_plan(src: str, repair: str) -> str:
    if src.count(ORIGINAL_TAG) != 1:
        raise ValueError('unexpected baseline')
    replacement = {
        'noop': ORIGINAL_TAG,
        # Deliberately false-green: focusable and named, still click-only.
        'aria_only': ORIGINAL_TAG.replace('<div ', '<div role="button" tabindex="0" ', 1),
        # Native button keyboard behavior without AI-written script execution.
        'native_button': ORIGINAL_TAG.replace('<div ', '<button type="button" ', 1).replace('</div>', '</button>'),
    }[repair]
    return src.replace(ORIGINAL_TAG, replacement, 1)


def browser_checks(html: str) -> dict[str, bool]:
    # Trust boundary: no arbitrary model code enters this fixture.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # Honor an explicit browser path; prefer system Chromium on Linux; otherwise use Playwright's browser.
        configured = os.environ.get('RB_CHROMIUM')
        browser_path = configured or ('/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None)
        launch_args = {'headless': True}
        if browser_path:
            launch_args['executable_path'] = browser_path
        browser = p.chromium.launch(**launch_args)
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            checks = {}
            checks['initially_closed'] = not page.locator('#panel').is_visible()
            checks['mouse_opens'] = (page.locator('#open-menu').click() is None and page.locator('#panel').is_visible())
            page.locator('#close-menu').click()
            checks['mouse_closes'] = not page.locator('#panel').is_visible()
            page.set_content(html, wait_until="load")
            page.keyboard.press('Tab')
            checks['keyboard_reaches_trigger'] = page.evaluate('document.activeElement?.id') == 'open-menu'
            page.keyboard.press('Enter')
            checks['enter_activates'] = page.locator('#panel').is_visible()
            if checks['enter_activates']:
                page.locator('#close-menu').click()
                checks['focus_restored'] = page.evaluate('document.activeElement?.id') == 'open-menu'
                page.keyboard.press('Space')
                checks['space_activates'] = page.locator('#panel').is_visible()
            else:
                checks['focus_restored'] = False
                checks['space_activates'] = False
            checks['semantic_button'] = page.locator('#open-menu').evaluate('(el) => el.tagName === "BUTTON"')
            checks['accessible_name'] = page.locator('#open-menu').inner_text().strip() == 'Open menu'
            return checks
        finally:
            browser.close()


def evaluate_bytes(data: bytes) -> dict[str, Any]:
    proposal = parse_proposal(data)
    src = source()
    html = apply_plan(src, proposal['repair'])
    checks = browser_checks(html)
    return {
        'kind': 'Repair Bench controlled behavioral benchmark',
        'author': 'GPT-6 2026-10-28',
        'candidate_sha256': digest(data),
        'fixture_sha256': digest(src.encode('utf-8')),
        'repair_type': proposal['repair'],
        'real_model_inference': False,
        'candidate_code_execution': False,
        'acceptance': 'ACCEPTED' if all(checks.values()) else 'REJECTED',
        'checks': checks,
        'limitations': 'Single synthetic component and browser; no axe scan, screen-reader test, WCAG certification or real model performance claim.',
    }


def prompt() -> str:
    return ("You are selecting one constrained repair for a tiny synthetic web menu. "
            "The mouse works, but keyboard users cannot open it. Preserve mouse behavior, "
            "make Tab/Enter/Space work, and use correct native HTML semantics. "
            "Return exactly JSON with keys schema (repair-bench.a11y-proposal.v1) "
            "and repair (one of noop, aria_only, native_button). "
            "Do not add fields, markdown, or code. Here is the original source:\n" + source())


def main(argv: list[str]) -> int:
    if argv == ['--prompt']:
        print(prompt()); return 0
    if len(argv) != 1 or argv[0].startswith('-'):
        print('Usage: python a11y-lab/evaluate.py --prompt | candidate.json', file=sys.stderr)
        return 64
    try:
        data = Path(argv[0]).read_bytes()
        output = evaluate_bytes(data)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if output['acceptance'] == 'ACCEPTED' else 2
    except Exception as exc:
        print(f'REJECTED: {type(exc).__name__}: {str(exc)[:240]}',file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
