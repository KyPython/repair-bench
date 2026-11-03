#!/usr/bin/env python3
"""Compose the sanitized replay artifact from observed trial evidence only.

Inputs are the attempt directory (reservation/transport summary), a sandbox
evaluation report, and the operator audit record. Every value in the output
comes from one of those artifacts; nothing is inferred or invented. The
composed document must pass the same sanitizer the demo server uses before
it is written. Refuses to overwrite an existing artifact.

The direct patch text and proposal statements are the model's publishable
work product and are replayed inertly; raw response bytes, headers and
credentials never leave the private directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "submission"))
import source_trial_receipt as receipt

TRIAL = ROOT / "source-repair" / "trial"
BRANCHES = ("upstream", "reference", "cosmetic", "stoponly", "toolsonly")
LIMIT = 2_000_000
TRANSPORT_MAP = {"response_validated_unexecuted": "completed",
                 "rejected": "rejected", "uncertain": "uncertain"}
CANDIDATE_MAP = {"accepted": "accepted", "failed": "failed",
                 "rejected": "rejected", "reviewed": "not_run",
                 "missing": "unavailable"}


class ComposeError(ValueError):
    pass


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ComposeError("Regular non-symlink input required: " + path.name)
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise ComposeError("Oversized input: " + path.name)
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise ComposeError("Invalid JSON input: " + path.name) from exc
    if type(doc) is not dict:
        raise ComposeError("Invalid input object: " + path.name)
    return doc


def _read_text(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ComposeError("Regular non-symlink input required: " + path.name)
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise ComposeError("Oversized input: " + path.name)
    try:
        return raw.decode("utf-8")
    except UnicodeError as exc:
        raise ComposeError("Input must be UTF-8: " + path.name) from exc


def _transport(attempt: Path, blockers: list[str]) -> dict:
    manifest_path = attempt / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        blockers.append("No direct transport reservation recorded")
        return {"status": "blocked"}
    manifest = _read_json(manifest_path)
    record: dict = {"status": "not_sent",
                    "requested_model": manifest.get("requested_model"),
                    "reserved_at_utc": manifest.get("reserved_utc"),
                    "request_sha256": manifest.get("request_sha256")}
    summary_path = attempt / "transport.json"
    if not summary_path.exists():
        if (attempt / "send.claim").exists():
            record["status"] = "blocked"
            blockers.append("Direct transport denied before any network attempt")
        else:
            blockers.append("Direct transport reservation has not been sent")
        return record
    summary = _read_json(summary_path)
    record["status"] = TRANSPORT_MAP.get(summary.get("status", ""), "failed")
    for key in ("returned_model", "response_id", "provider_request_id",
                "finish_reason", "sent_utc", "received_utc", "usage",
                "response_sha256", "patch_sha256"):
        if key in summary:
            record[{"sent_utc": "sent_at_utc",
                    "received_utc": "received_at_utc"}.get(key, key)] = summary[key]
    if record["status"] == "uncertain":
        blockers.append("Direct transport outcome uncertain; no retry permitted")
    elif record["status"] in ("failed", "rejected"):
        blockers.append("Direct transport rejected: " + str(summary.get("error", "unknown")))
    return record


def _scope(value: dict | None) -> dict | None:
    if value is None:
        return None
    if type(value) is not dict:
        raise ComposeError("Invalid scope record")
    result: dict = {}
    if "approved" in value:
        result["approved"] = value["approved"]
    if "status" in value:
        result["status"] = value["status"]
    for key in ("reasons", "review", "reason"):
        if key in value:
            reasons = value[key] if type(value[key]) is list else [value[key]]
            result.setdefault("reasons", []).extend(reasons)
    return result or None


def _operator_candidate(sandbox: dict | None, blockers: list[str]) -> dict:
    try:
        patch = _read_text(ROOT / "source-repair" / "model_attempt_01" / "MODEL_PATCH.diff")
    except ComposeError:
        blockers.append("Operator-supplied patch bytes unavailable")
        return {"status": "unavailable",
                "provenance": "Operator-supplied candidate was not found."}
    entry = (sandbox or {}).get("candidates", {}).get("operator_supplied", {})
    status = CANDIDATE_MAP.get(entry.get("status", ""), "unavailable")
    if entry.get("patch_sha256") and entry["patch_sha256"] != hashlib.sha256(patch.encode()).hexdigest():
        raise ComposeError("Operator patch fingerprint mismatch")
    return {"status": status,
            "provenance": "Supplied files preserved byte-for-byte; "
                          "sandbox outcome shown when independently observed.",
            "patch": patch,
            "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
            "protocol": entry.get("protocol"), "supplemental": entry.get("supplemental"),
            "scope": _scope(entry.get("scope"))}


def _direct_candidate(attempt: Path, transport: dict, sandbox: dict | None,
                      blockers: list[str]) -> dict:
    entry = (sandbox or {}).get("candidates", {}).get("direct_meta", {})
    status = CANDIDATE_MAP.get(entry.get("status", ""), "unavailable")
    record: dict = {"status": status,
                    "provenance": "Direct Meta transport; executed only in "
                                  "the isolated sandbox after scope review.",
                    "patch": None, "patch_sha256": None,
                    "protocol": entry.get("protocol"),
                    "supplemental": entry.get("supplemental"),
                    "scope": _scope(entry.get("scope"))}
    if transport["status"] != "completed":
        blockers.append("No validated direct response to evaluate")
        return record
    private = attempt.parent / ".private" / attempt.name
    try:
        patch = _read_text(private / "MODEL_PATCH.diff")
        proposal = _read_json(private / "proposal.json")
    except ComposeError:
        blockers.append("Validated direct response is unavailable for replay")
        record["status"] = "failed"
        return record
    if transport.get("patch_sha256") != hashlib.sha256(patch.encode()).hexdigest():
        raise ComposeError("Direct patch fingerprint mismatch")
    record["patch"] = patch
    record["patch_sha256"] = hashlib.sha256(patch.encode()).hexdigest()
    if type(proposal.get("diagnosis")) is str and type(proposal.get("risks")) is list \
            and type(proposal.get("tests_to_run")) is list:
        record["model_statements"] = {"diagnosis": proposal["diagnosis"],
                                      "risks": proposal["risks"],
                                      "tests_to_run": proposal["tests_to_run"]}
    return record


def compose(attempt_dir: Path = TRIAL / "direct_meta_01",
            sandbox_report: Path | None = None,
            audit_path: Path = TRIAL / "OPERATOR_ATTEMPT_AUDIT.json") -> dict:
    blockers: list[str] = []
    transport = _transport(attempt_dir, blockers)
    sandbox: dict | None = None
    if sandbox_report is not None:
        sandbox = _read_json(sandbox_report)
        blockers.extend("Sandbox: " + item for item in sandbox.get("blockers", []))
    else:
        blockers.append("No sandbox evaluation report supplied")
    comparisons: dict = {}
    for branch in BRANCHES:
        row = (sandbox or {}).get("comparisons", {}).get(branch)
        if type(row) is dict and (row.get("protocol") or row.get("supplemental")):
            comparisons[branch] = {"protocol": row.get("protocol"),
                                   "supplemental": row.get("supplemental")}
    candidates = {"operator_supplied": _operator_candidate(sandbox, blockers),
                  "direct_meta": _direct_candidate(attempt_dir, transport, sandbox, blockers)}
    try:
        audit = _read_json(audit_path)
        claims, limitations = audit.get("claims", []), audit.get("limitations", [])
    except ComposeError:
        claims, limitations = [], ["Operator audit record unavailable"]
    observations = ["Transport status: " + str(transport["status"])]
    if sandbox is not None:
        observations.append("Sandbox status: " + str(sandbox.get("status")))
        observations.append("Comparators reproduced: " + str(sandbox.get("comparators_reproduced")))
        image = sandbox.get("image", {})
        if type(image) is dict and image.get("id"):
            observations.append("Sandbox image: " + str(image["id"]))
        probe = sandbox.get("probe", {})
        if type(probe) is dict and type(probe.get("data")) is dict:
            observations.append("Isolation probe passed: " + str(probe["data"].get("isolated")))
    for name, candidate in candidates.items():
        observations.append(name + " candidate status: " + candidate["status"])
    status = "blocked" if sandbox is None or sandbox.get("status") == "blocked" else (
        "completed" if sandbox.get("status") == "completed" else "failed")
    doc = {"schema_version": 1, "status": status, "blockers": blockers,
           "transport": transport, "comparisons": comparisons,
           "candidates": candidates,
           "audit": {"claims": claims, "limitations": limitations},
           "validation": {"observations": observations}}
    return receipt.sanitize(doc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, default=TRIAL / "direct_meta_01")
    parser.add_argument("--sandbox", type=Path)
    parser.add_argument("--audit", type=Path, default=TRIAL / "OPERATOR_ATTEMPT_AUDIT.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        parser.error("Refusing to replace an existing artifact")
    try:
        doc = compose(args.attempt, args.sandbox, args.audit)
    except (ComposeError, ValueError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)[:200]}))
        return 2
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": doc["status"], "transport": doc["transport"]["status"],
                      "candidates": {k: v["status"] for k, v in doc["candidates"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
