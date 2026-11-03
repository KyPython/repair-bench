#!/usr/bin/env python3
"""One reserved public-source request; transport never loads candidate code.

The Meta spend limit is an alert, not enforced overage prevention:
https://dev.meta.ai/help/billing/spend-limit-alert (confirmed 2026-11-03:
"Meta Model API doesn't currently offer a spending limit that places a
hard cap on usage"). No provider-enforced prevention exists to verify.

Amendment 2026-11-03 (owner-authorized, see docs/META_SOURCE_REPAIR_SPEC.md):
the owner accepts the bounded single-call cost risk through an explicit
request-bound authorization file. A missing, malformed or mismatched file
still denies transport. No other gate changed: one attempt, no retries,
no redirects, no credential-bearing logs.

Raw provider bytes are private local evidence, never demo input. Output from
this module is an allowlist of observations, not provider authentication.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TRIAL = ROOT / "source-repair" / "trial"
DEFAULT_ATTEMPT = TRIAL / "direct_meta_01"
MODEL = "muse-spark-1.3"
ENDPOINT = "https://api.meta.ai/v1/chat/completions"
UPSTREAM_REVISION = "386e09942510e93de2db6d108f24f62f65eecbdc"
SOURCE_NAMES = ("convert_response.py", "responses_stop_details.py", "collect_stop_details.py")
MAX_RESPONSE_BYTES = 2_000_000
PROBLEM = (
    'A response interrupted by content filtering after beginning a tool call '
    'is converted to stop_reason="tool_calls" with no visible stop_details; '
    'a downstream agent could execute the partial call. Ordinary completed '
    'tool-call responses must continue to work. Stop reason, stop details and '
    'tool-call forwarding are separate control paths.'
)
PERMITTED_EDITS = {
    "files": list(SOURCE_NAMES),
    "constraints": [
        "Edit only the bodies of the three supplied function excerpts.",
        "Preserve function names, signatures, interfaces and unrelated behavior.",
        "Preserve shared collect_stop_details behavior for all providers.",
        "No extra files, imports, top-level execution, evaluator access, or fixture edits.",
        "No reference, control or preexisting candidate is part of this request.",
    ],
}
USAGE_KEYS = frozenset({
    "prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens",
    "prompt_tokens_details", "completion_tokens_details", "input_tokens_details", "output_tokens_details",
    "cached_tokens", "reasoning_tokens", "audio_tokens", "text_tokens", "image_tokens",
    "accepted_prediction_tokens", "rejected_prediction_tokens", "cache_read_input_tokens",
    "cache_creation_input_tokens", "num_tokens", "num_cached_tokens",
})


class TransportDenied(RuntimeError):
    """A fixed, non-secret reason code; never wrap raw provider exceptions."""


class ResponseRejected(ValueError):
    """A fixed reason code; raw bytes remain private."""


class TransportUncertain(RuntimeError):
    def __init__(self, partial: bytes = b""):
        super().__init__("uncertain_outcome_no_retry")
        self.partial = partial


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def _strict_json(raw: bytes | str) -> Any:
    def pairs(values):
        result = {}
        for name, value in values:
            if name in result:
                raise ValueError("duplicate_json_key")
            result[name] = value
        return result
    def invalid_constant(_value):
        raise ValueError("nonfinite_json_number")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _exclusive_write(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _append_event(attempt: Path, event: str, **safe: Any) -> None:
    # All callers pass static status codes and sanitized metadata only.
    fd = os.open(attempt / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "ab") as handle:
        handle.write(json_bytes({"event": event, "timestamp_utc": utc_now(), **safe}))
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(attempt)


def _public_inputs(repo_root: Path) -> tuple[dict, dict[str, str]]:
    inventory = json.loads((repo_root / "source-repair/trial/PROTECTED_SHA256.json").read_bytes())
    paths = ["source-repair/trial/PROTOCOL.json", "source-repair/trial/run_trial.py",
             "source-repair/trial/metamorphic.py"]
    paths += ["source-repair/upstream/" + name for name in SOURCE_NAMES]
    hashes = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_symlink() or digest(path.read_bytes()) != inventory.get(relative):
            raise TransportDenied("frozen_input_mismatch")
        hashes[relative] = digest(path.read_bytes())
    protocol = json.loads((repo_root / paths[0]).read_bytes())
    return protocol, hashes


def build_request(repo_root: Path = ROOT) -> dict:
    protocol, _ = _public_inputs(repo_root)
    public_requirements = {"rubric": protocol["rubric"], "cases": protocol["cases"]}
    source = "\n\n".join("### file: " + name + "\n" +
        (repo_root / "source-repair/upstream" / name).read_text() for name in SOURCE_NAMES)
    instructions = (
        "Propose one actual source patch for the public Inspect AI issue #5971. "
        "You have one completion, no tools, and no test execution. Do not claim tests ran. "
        "Return JSON only, with keys diagnosis (string), patch (a nonempty unified diff "
        "using exactly a/<filename> and b/<filename> for the supplied excerpt filenames), "
        "risks (array of strings), tests_to_run (array of strings). No code fences.\n\n"
        + PROBLEM + "\n\nPinned upstream revision: " + UPSTREAM_REVISION +
        "\n\nPermitted edits:\n" + json.dumps(PERMITTED_EDITS, sort_keys=True) +
        "\n\nAcceptance requires all nine frozen checks and permitted scope. Suppress "
        "tool calls on EVERY incomplete response, including max_output_tokens; retain "
        "max_tokens stop signaling, refusal text and ordinary complete tool calls. A "
        "content-filter stop must have nonempty explanatory details even without refusal "
        "text. The shared collector's unrelated behavior must remain intact. This "
        "incomplete-call suppression is a Repair Bench safety criterion, not a verified "
        "upstream maintainer requirement.\n\nAll frozen behavioral requirements:\n" +
        json.dumps(public_requirements, sort_keys=True, ensure_ascii=False) +
        "\n\nOriginal public source excerpts:\n" + source
    )
    return {"model": MODEL, "messages": [
        {"role": "developer", "content": "Return the requested JSON source-patch proposal only. No tools or execution."},
        {"role": "user", "content": instructions}],
        "n": 1, "reasoning_effort": "medium", "max_completion_tokens": 8192,
        "response_format": {"type": "json_object"}, "tools": [],
        "stream": False, "store": False}


def request_bytes(repo_root: Path = ROOT) -> bytes:
    return json_bytes(build_request(repo_root))


def reserve_attempt(attempt_dir: Path = DEFAULT_ATTEMPT, repo_root: Path = ROOT) -> dict:
    """Freeze public inputs once. Preparation never reads credentials or sends."""
    raw = request_bytes(repo_root)
    protocol, hashes = _public_inputs(repo_root)
    trial = repo_root / "source-repair/trial"
    if attempt_dir.parent.resolve() != trial.resolve() or attempt_dir.name != "direct_meta_01":
        raise TransportDenied("unexpected_attempt_path")
    attempt_dir.mkdir(mode=0o700)  # exclusive; a partial failed reservation is retained
    _fsync_directory(trial)
    try:
        _exclusive_write(trial / (".request-" + digest(raw) + ".reserved"), b"direct_meta_01\n")
        _exclusive_write(attempt_dir / "request.json", raw)
        spec_path = repo_root / "docs/META_SOURCE_REPAIR_SPEC.md"
        hashes["docs/META_SOURCE_REPAIR_SPEC.md"] = digest(spec_path.read_bytes())
        hashes["source-repair/trial/direct_transport.py"] = digest(Path(__file__).read_bytes())
        manifest = {
            "schema_version": 1, "attempt": "direct_meta_01", "status": "reserved_not_sent",
            "reserved_utc": utc_now(), "problem": PROBLEM, "upstream_revision": UPSTREAM_REVISION,
            "upstream_repository": protocol["upstream_repository"],
            "source_provenance": protocol["source_provenance"], "input_sha256": hashes,
            "permitted_edits": PERMITTED_EDITS, "acceptance": {
                "all_nine_frozen_checks_required": True, "scope_required": True,
                "rubric": protocol["rubric"], "cases": protocol["cases"],
                "supplemental_checks": "18 checks reported separately, not acceptance"},
            "request_sha256": digest(raw), "request_bytes": len(raw), "request_file": "request.json",
            "endpoint": ENDPOINT, "requested_model": MODEL, "model_mode": "standard",
            "automatic_retries": 0, "follow_redirects": False, "max_response_bytes": MAX_RESPONSE_BYTES,
            "no_resend": "Any send claim, failure, interruption or uncertain outcome consumes this reservation.",
            "billing_requirement": "Owner request-bound risk authorization (spec amendment 2026-11-03); provider offers no enforceable cap.",
            "billing_verifier_status": "billing_authorization.json with matching request_sha256 required; alerts-only provider limit documented",
        }
        _exclusive_write(attempt_dir / "manifest.json", json_bytes(manifest))
        _append_event(attempt_dir, "RESERVED", request_sha256=digest(raw), network_attempted=False)
        return manifest
    except BaseException:
        # Never remove even an incomplete reservation: it prevents accidental duplication.
        raise


def _verify_provider_credit_protection() -> bool:
    """The provider offers no enforceable cap (alerts only); always False.

    Kept as a documented provider fact. Per the owner-authorized 2026-11-03
    amendment, live transport instead requires the request-bound owner risk
    authorization below. Flags, alerts and token limits alone enable nothing.
    https://dev.meta.ai/help/billing/spend-limit-alert documents alerts only.
    """
    return False


AUTH_SCOPE = "direct_meta_01 single send, n=1, max_completion_tokens=8192, no retries"


def _verify_owner_billing_authorization(attempt_dir: Path) -> bool:
    """True only for the owner's exact-request risk acceptance on file."""
    try:
        auth_path = attempt_dir / "billing_authorization.json"
        if auth_path.is_symlink():
            return False
        auth = _strict_json(auth_path.read_bytes())
        manifest = json.loads((attempt_dir / "manifest.json").read_bytes())
    except (OSError, ValueError):
        return False
    if type(auth) is not dict or set(auth) != {
            "schema_version", "scope", "request_sha256",
            "owner_accepts_bounded_cost_risk", "authorized_utc"}:
        return False
    return (auth["schema_version"] == 1
            and auth["scope"] == AUTH_SCOPE
            and auth["request_sha256"] == manifest.get("request_sha256")
            and auth["owner_accepts_bounded_cost_risk"] is True
            and type(auth["authorized_utc"]) is str
            and len(auth["authorized_utc"]) <= 64)


def prerequisite_blockers(attempt_dir: Path = DEFAULT_ATTEMPT) -> list[str]:
    blockers = []
    key = os.environ.get("MODEL_API_KEY", "")
    if not key:
        blockers.append("MODEL_API_KEY is not configured")
    elif not key.isascii() or not key.isprintable() or any(c.isspace() for c in key):
        blockers.append("MODEL_API_KEY has an invalid transport format")
    if not _verify_owner_billing_authorization(attempt_dir):
        blockers.append("Owner billing-risk authorization for this exact request is missing or invalid")
    return blockers


def _identifier(value: Any, secrets: tuple[str, ...]) -> str | None:
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,160}", value):
        return None
    if any(secret and secret in value for secret in secrets):
        return None
    return value


def _usage(value: Any, depth: int = 0) -> dict | None:
    if type(value) is not dict or depth > 2:
        return None
    result = {}
    for name, counter in value.items():
        if name not in USAGE_KEYS:
            continue
        if type(counter) is int and 0 <= counter <= 10**12:
            result[name] = counter
        elif type(counter) is dict:
            nested = _usage(counter, depth + 1)
            if nested is not None:
                result[name] = nested
    return result


def _contains_secret(value: Any, secrets: tuple[str, ...]) -> bool:
    if type(value) is str:
        return any(secret and secret in value for secret in secrets)
    if type(value) is list:
        return any(_contains_secret(item, secrets) for item in value)
    if type(value) is dict:
        return any(_contains_secret(name, secrets) or _contains_secret(item, secrets)
                   for name, item in value.items())
    return False


def sanitized_response(raw: bytes, secret_values: tuple[str, ...] = ()) -> dict:
    out = {"response_sha256": digest(raw), "response_bytes": len(raw), "returned_model": None,
           "response_id": None, "finish_reason": None, "usage": None, "patch_sha256": None}
    try:
        doc = _strict_json(raw)
        if type(doc) is not dict:
            return out
        out["returned_model"] = _identifier(doc.get("model"), secret_values)
        out["response_id"] = _identifier(doc.get("id"), secret_values)
        out["usage"] = _usage(doc.get("usage"))
        choices = doc.get("choices")
        if type(choices) is list and len(choices) == 1 and type(choices[0]) is dict:
            finish = choices[0].get("finish_reason")
            if finish in ("stop", "length", "tool_calls", "content_filter"):
                out["finish_reason"] = finish
    except (ValueError, UnicodeDecodeError, RecursionError):
        pass
    return out


def parse_provider_response(raw: bytes, secret_values: tuple[str, ...] = ()) -> tuple[dict, dict]:
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ResponseRejected("response_exceeds_bound")
    if any(secret and secret.encode() in raw for secret in secret_values):
        raise ResponseRejected("secret_reflection")
    try:
        doc = _strict_json(raw)
        if type(doc) is not dict:
            raise ResponseRejected("invalid_envelope")
        if _contains_secret(doc, secret_values):
            raise ResponseRejected("secret_reflection")
        if doc.get("model") != MODEL:
            raise ResponseRejected("model_identity_mismatch")
        if not _identifier(doc.get("id"), secret_values):
            raise ResponseRejected("response_id_missing_or_invalid")
        choices = doc.get("choices")
        if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
            raise ResponseRejected("expected_one_completion")
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            raise ResponseRejected("truncated_or_nonstop_completion")
        message = choice.get("message")
        if type(message) is not dict or message.get("role") != "assistant" or message.get("tool_calls"):
            raise ResponseRejected("unexpected_assistant_message")
        if type(message.get("content")) is not str:
            raise ResponseRejected("missing_content")
        proposal = _strict_json(message["content"])
        if _contains_secret(proposal, secret_values):
            raise ResponseRejected("secret_reflection")
        if type(proposal) is not dict or set(proposal) != {"diagnosis", "patch", "risks", "tests_to_run"}:
            raise ResponseRejected("proposal_schema_invalid")
        if not all(type(proposal[k]) is str and proposal[k].strip() for k in ("diagnosis", "patch")):
            raise ResponseRejected("proposal_text_invalid")
        if not all(type(proposal[k]) is list and all(type(v) is str for v in proposal[k]) for k in ("risks", "tests_to_run")):
            raise ResponseRejected("proposal_lists_invalid")
        if not proposal["patch"].startswith(("--- a/", "diff --git a/")):
            raise ResponseRejected("patch_not_unified_diff")
        summary = sanitized_response(raw, secret_values)
        summary["patch_sha256"] = digest(proposal["patch"].encode())
        return proposal, summary
    except ResponseRejected:
        raise
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ResponseRejected("malformed_json") from None


def _exchange(raw: bytes, key: str) -> tuple[int, dict, bytes]:
    """Direct TLS connection: no proxy inheritance, redirects, SDK retries or tools."""
    connection = http.client.HTTPSConnection("api.meta.ai", timeout=120, context=ssl.create_default_context())
    received = bytearray()
    try:
        connection.request("POST", "/v1/chat/completions", body=raw, headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json",
            "Accept": "application/json", "Accept-Encoding": "identity"})
        response = connection.getresponse()
        while len(received) <= MAX_RESPONSE_BYTES:
            chunk = response.read(min(65536, MAX_RESPONSE_BYTES + 1 - len(received)))
            if not chunk:
                break
            received.extend(chunk)
        headers = dict(response.getheaders())
        length = response.getheader("Content-Length")
        if length is not None and len(received) <= MAX_RESPONSE_BYTES and int(length) != len(received):
            raise TransportUncertain(bytes(received))
        return response.status, headers, bytes(received)
    except TransportUncertain:
        raise
    except http.client.IncompleteRead as exc:
        received.extend(exc.partial)
        raise TransportUncertain(bytes(received)) from None
    except Exception:
        raise TransportUncertain(bytes(received)) from None
    finally:
        connection.close()


def send_reserved(attempt_dir: Path = DEFAULT_ATTEMPT, repo_root: Path = ROOT) -> dict:
    """Consumes a send claim once, including a denial. Never retries any outcome."""
    trial = repo_root / "source-repair/trial"
    if attempt_dir.parent.resolve() != trial.resolve() or attempt_dir.name != "direct_meta_01":
        raise TransportDenied("unexpected_attempt_path")
    if attempt_dir.is_symlink():
        raise TransportDenied("symlink_attempt")
    _exclusive_write(attempt_dir / "send.claim", json_bytes({"claimed_utc": utc_now()}))
    blockers = prerequisite_blockers(attempt_dir)
    if blockers:
        _append_event(attempt_dir, "DENIED", network_attempted=False, blockers=blockers)
        raise TransportDenied("prerequisites_unavailable_no_transport")
    raw = (attempt_dir / "request.json").read_bytes()
    manifest = json.loads((attempt_dir / "manifest.json").read_bytes())
    if raw != request_bytes(repo_root) or digest(raw) != manifest.get("request_sha256"):
        _append_event(attempt_dir, "DENIED", network_attempted=False, reason="request_mismatch")
        raise TransportDenied("request_mismatch")
    for relative, expected in manifest["input_sha256"].items():
        path = repo_root / relative
        if path.is_symlink() or digest(path.read_bytes()) != expected:
            _append_event(attempt_dir, "DENIED", network_attempted=False, reason="frozen_input_mismatch")
            raise TransportDenied("frozen_input_mismatch")
    private_parent = trial / ".private"
    private_parent.mkdir(mode=0o700, exist_ok=True)
    if private_parent.is_symlink():
        raise TransportDenied("symlink_private_directory")
    os.chmod(private_parent, 0o700)
    ignore = private_parent / ".gitignore"
    if not ignore.exists():
        _exclusive_write(ignore, b"*\n!.gitignore\n")
    private = private_parent / "direct_meta_01"
    private.mkdir(mode=0o700)
    _fsync_directory(private_parent)
    _exclusive_write(private / "request.bin", raw)
    key = os.environ["MODEL_API_KEY"]
    secrets = (key,)
    sent = utc_now()
    _append_event(attempt_dir, "NETWORK_ATTEMPTED", network_attempted=True, request_sha256=digest(raw))
    try:
        status, headers, received = _exchange(raw, key)
    except TransportUncertain as exc:
        _exclusive_write(private / "response.bin", exc.partial)
        summary = {"status": "uncertain", "network_attempted": True, "requested_model": MODEL,
                   "sent_utc": sent, "finished_utc": utc_now(), "request_sha256": digest(raw),
                   "response_sha256": digest(exc.partial), "response_bytes": len(exc.partial),
                   "error": "uncertain_outcome_no_retry"}
        _exclusive_write(attempt_dir / "transport.json", json_bytes(summary))
        _append_event(attempt_dir, "UNKNOWN_NO_RETRY", **summary)
        return summary
    _exclusive_write(private / "response.bin", received)
    _exclusive_write(private / "response_headers.json", json_bytes(headers))
    summary = {"status": "rejected", "network_attempted": True, "requested_model": MODEL,
               "sent_utc": sent, "received_utc": utc_now(), "request_sha256": digest(raw),
               "http_status": status, **sanitized_response(received, secrets)}
    lowered = {k.lower(): v for k, v in headers.items()}
    summary["provider_request_id"] = _identifier(lowered.get("x-request-id", lowered.get("request-id")), secrets)
    try:
        if status != 200:
            raise ResponseRejected("http_error_or_redirect_no_retry")
        proposal, metadata = parse_provider_response(received, secrets)
        summary.update(metadata)
        _exclusive_write(private / "proposal.json", json_bytes(proposal))
        _exclusive_write(private / "MODEL_PATCH.diff", proposal["patch"].encode())
        summary["status"] = "response_validated_unexecuted"
    except ResponseRejected as exc:
        summary["error"] = str(exc)
    _exclusive_write(attempt_dir / "transport.json", json_bytes(summary))
    _append_event(attempt_dir, "RESPONSE_RECORDED_NO_RETRY", **summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preflight", "send"], nargs="?")
    # Accept --prepare/--preflight/--send as documented aliases.
    import sys
    args = sys.argv[1:]
    if args in (["--preflight"], ["preflight"]):
        blockers = prerequisite_blockers()
        print(json.dumps({"status": "ready" if not blockers else "blocked",
                          "network_attempted": False, "blockers": blockers}, indent=2))
        return 0 if not blockers else 2
    try:
        if args in (["--prepare"], ["prepare"]):
            manifest = reserve_attempt()
            print(json.dumps({"status": "reserved_not_sent", "network_attempted": False,
                              "request_sha256": manifest["request_sha256"],
                              "blockers": prerequisite_blockers()}, indent=2))
            return 0
        if args in (["--send"], ["send"]):
            print(json.dumps(send_reserved(), indent=2))
            return 0
        parser.print_help()
        return 64
    except (TransportDenied, FileExistsError, OSError, ValueError):
        # No exception messages: filesystem paths, credentials or server text may be private.
        print(json.dumps({"status": "denied", "detail": "Reservation or prerequisites invalid; preserve evidence and do not resend."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
