#!/usr/bin/env python3
"""Local, non-billable judge demo. Trusted fixture only; model-supplied code is never executed.

This server binds to loopback, does not use credentials, and provides no model endpoint.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import threading

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'a11y-lab'))
from evaluate import SCHEMA, OPTIONS, apply_plan, evaluate_bytes, source
from model_receipt import load_receipt
from source_trial_receipt import load_source_trial
from dialog import OPTIONS as DIALOG_OPTIONS, SCHEMA as DIALOG_SCHEMA, apply_plan as apply_dialog, evaluate_bytes as evaluate_dialog, source as dialog_source

MAX_REQUEST = 512
AUDIT_LOCK = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    server_version = 'RepairBench/1.0'

    def reply(self, status: int, data: bytes, mime: str = 'application/json; charset=utf-8', fixture: bool = False, world: bool = False):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        if not fixture:
            self.send_header('X-Frame-Options', 'SAMEORIGIN')
        if world:
            # The unchanged original world imports eight same-origin scripts AND runs
            # trusted inline demo setup; its hash-check also fetches local assets.
            # Do not reuse the standalone untrusted fixture CSP here.
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
        elif fixture:
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
        else:
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def reply_json(self, status: int, obj):
        self.reply(status, json.dumps(obj, sort_keys=True, separators=(',', ':')).encode())

    def do_GET(self):
        uri = urlparse(self.path)
        if uri.path == '/source-repair/model-trial.json':
            return self.reply_json(200, load_source_trial())
        static = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/styles.css': ('styles.css', 'text/css; charset=utf-8')}
        if uri.path in static:
            filename, mime = static[uri.path]
            return self.reply(200, (STATIC / filename).read_bytes(), mime)
        source_demo = {
            '/source-repair': ('index.html', 'text/html; charset=utf-8'),
            '/source-repair/app.js': ('app.js', 'text/javascript; charset=utf-8'),
            '/source-repair/styles.css': ('styles.css', 'text/css; charset=utf-8'),
            '/source-repair/results.json': ('results.json', 'application/json; charset=utf-8'),
        }
        if uri.path in source_demo:
            filename, mime = source_demo[uri.path]
            return self.reply(200, (ROOT / 'source-repair' / filename).read_bytes(), mime)
        if uri.path == '/world':
            # An original, separately sealed world demonstration; browser UI is fixture-only.
            return self.reply(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8', world=True)
        # Explicitly allowed static source files for the original game-world demo.
        allowed_world = ('src/world.js','src/physics.js','src/victory.js','src/replay.js','src/harness.js',
                         'patches/seeded_defect_v1.js','patches/fixture_repair.js','patches/cheat_autopilot.js',
                         'tests/integrity_manifest.json')
        if uri.path.lstrip('/') in allowed_world:
            relative = uri.path.lstrip('/')
            mime = 'application/json; charset=utf-8' if relative.endswith('.json') else 'text/javascript; charset=utf-8'
            return self.reply(200, (ROOT / relative).read_bytes(), mime)
        if uri.path == '/api/status':
            try:
                src = source()
                from hashlib import sha256
                return self.reply_json(200, {'service':'repair-bench.local.v1','source_sha256':sha256(src.encode()).hexdigest(),'oracle':'Chromium via Playwright','billing':'none','meta_status':load_receipt()['status'],'provider_calls_from_ui':False,'scope':'Two sealed browser tasks, three declarative choices per task','benchmarks':['menu','dialog'],'dialog_source_sha256':sha256(dialog_source().encode()).hexdigest(),'ready':True})
            except Exception:
                return self.reply_json(503, {'ready':False,'error':'Sealed source unavailable; fail closed'})
        if uri.path == '/api/model-receipt':
            # Read-only operator supplied metadata. No browser-controlled path,
            # no Meta API call and no secret access. Not provider-authenticated.
            return self.reply_json(200, load_receipt())
        if uri.path == '/api/fixture':
            query = parse_qs(uri.query)
            task = query.get('task',['menu'])
            if len(task)!=1 or task[0] not in {'menu','dialog'}:
                return self.reply_json(400,{'error':'Unsupported challenge'})
            option = query.get('repair',['noop'])
            allowed=OPTIONS if task[0]=='menu' else DIALOG_OPTIONS
            if len(option)!=1 or option[0] not in allowed:
                return self.reply_json(400,{'error':'Unsupported fixture variant'})
            try:
                html = apply_plan(source(),option[0]) if task[0]=='menu' else apply_dialog(dialog_source(),option[0])
                return self.reply(200, html.encode(),'text/html; charset=utf-8',fixture=True)
            except Exception:
                return self.reply_json(503, {'error':'Sealed fixture unavailable'})
        return self.reply_json(404,{'error':'Unknown endpoint'})

    def do_POST(self):
        if urlparse(self.path).path != '/api/evaluate':
            return self.reply_json(404, {'error':'Unknown endpoint'})
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:
            return self.reply_json(403,{'error':'Local origin required'})
        if self.headers.get('Content-Type','').split(';',1)[0].strip() != 'application/json':
            return self.reply_json(415,{'error':'JSON only'})
        try:
            size = int(self.headers.get('Content-Length','-1'))
        except ValueError:
            size = -1
        if size < 1 or size > MAX_REQUEST:
            return self.reply_json(413, {'error':'Request exceeds limit or has no length'})
        data = self.rfile.read(size)
        if not AUDIT_LOCK.acquire(blocking=False):
            return self.reply_json(429, {'error':'Oracle busy; retry after current audit'})
        try:
            proposal = json.loads(data)
            if type(proposal) is not dict:
                raise ValueError('Candidate must be JSON object')
            task=proposal.pop('task','menu')
            if task=='menu':
                result=evaluate_bytes(json.dumps(proposal,separators=(',',':')).encode())
                result['task']='menu'
            elif task=='dialog':
                result=evaluate_dialog(json.dumps(proposal,separators=(',',':')).encode())
            else:
                raise ValueError('Unknown benchmark task')
            # The evaluator's inference flag is false because this is not a Meta call.
            result['run_provenance'] = 'LOCAL_CHROMIUM_OFFLINE'
            return self.reply_json(200,result)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.reply_json(422, {'error':'Invalid candidate','reason':str(exc)[:160]})
        except Exception:
            return self.reply_json(503, {'error':'Independent browser oracle unavailable'})
        finally:
            AUDIT_LOCK.release()

    def log_message(self, format, *args):
        # No request body, credentials, or external endpoints are logged.
        sys.stderr.write('RepairBench ' + (format % args) + '\n')


def main():
    parser = argparse.ArgumentParser(description='Local Repair Bench judge demo — no paid API calls')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('Port must be 0–65535')
    # Fail before launch if sealed fixture is invalid.
    source()
    dialog_source()
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'REPAIR_BENCH_URL=http://127.0.0.1:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
