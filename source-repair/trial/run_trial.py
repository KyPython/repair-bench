#!/usr/bin/env python3
"""Reproduce/score three pinned Inspect AI source functions without importing Inspect.

Only load pinned, SHA-derived local function snippets from this experiment.
This is a source-derived contract harness, NOT a full Inspect execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROTOCOL = json.loads((HERE / "PROTOCOL.json").read_text())


def fnv32(data: bytes) -> str:
    h = 2166136261
    for b in data:
        h = (h ^ b) * 16777619 & 0xffffffff
    return f"{h:08x}"


@dataclass
class IncompleteDetails:
    reason: str


@dataclass
class ResponseOutputRefusal:
    refusal: str


@dataclass
class ResponseOutputMessage:
    content: list[ResponseOutputRefusal]


@dataclass
class FunctionCall:
    name: str = "transfer"
    arguments: str = '{"amount":1}'


@dataclass
class OpenAIResponse:
    model: str
    incomplete_details: IncompleteDetails | None
    output: list[object]


@dataclass
class ChatMessageAssistant:
    content: str
    tool_calls: list[FunctionCall] | None
    model: str
    source: str


@dataclass
class StopDetails:
    type: str
    explanation: str | None = None
    categories: list = field(default_factory=list)
    category: str | None = None


class Logger:
    pass


def warn_once(_logger, message):
    raise AssertionError("Collector warning would have been emitted: " + message)


def _summarize_stop_categories(categories):
    return ", ".join(c.category for c in categories)


def _process_response_output_items(output, _tools):
    calls = [x for x in output if isinstance(x, FunctionCall)]
    return "model response text", calls, None, bool(calls)


def compile_pinned_source(source_dir: Path, *, require_original: bool = False):
    names = ["responses_stop_details.py", "convert_response.py", "collect_stop_details.py"]
    scope = {
        "__builtins__": __builtins__, "OpenAIResponse": OpenAIResponse,
        "ResponseOutputMessage": ResponseOutputMessage,
        "ResponseOutputRefusal": ResponseOutputRefusal,
        "IncompleteDetails": IncompleteDetails,
        "StopDetails": StopDetails,
        "ToolInfo": object, "Logprobs": object, "StopReason": str,
        "ChatMessageAssistant": ChatMessageAssistant,
        "Logger": Logger, "Callable": Callable, "warn_once": warn_once,
        "_summarize_stop_categories": _summarize_stop_categories,
        "_process_response_output_items": _process_response_output_items,
    }
    hashes = {}
    for name in names:
        path = source_dir / name
        raw = path.read_bytes()
        hashes[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), fnv32=fnv32(raw))
        if require_original and hashes[name]["fnv32"] != PROTOCOL["selected_source_functions_fnv32"][name]:
            raise RuntimeError(f"Original source mismatch: {name}")
        # The patches in this exercise are trusted, locally authored files only.
        code = compile(raw, str(path), "exec")
        exec(code, scope)
    return scope, hashes


def make_response(case):
    out = []
    if case["tool"]:
        out.append(FunctionCall())
    if case["refusal"]:
        out.append(ResponseOutputMessage(content=[ResponseOutputRefusal(case["refusal"])]))
    return OpenAIResponse(model="test-standin", incomplete_details=(
        IncompleteDetails(case["incomplete_reason"]) if case["incomplete_reason"] else None
    ), output=out)


def check_case(scope, case):
    response = make_response(case)
    msg, stop, _ = scope["_chat_message_assistant_from_openai_response"](
        "model", response, []
    )
    details = scope["collect_stop_details"](
        "openai_responses", Logger(),
        lambda: scope["responses_stop_details"](response),
    )
    # In a downstream agent, availability of model-supplied tool calls is a
    # separate dispatch channel from the stop-reason metadata.
    dispatch = bool(msg.tool_calls)
    observed = {
        "stop": stop,
        "details_type": details.type if details else None,
        "explanation": details.explanation if details else None,
        "dispatch": dispatch,
        "message_text": msg.content,
        "tool_call_count": len(msg.tool_calls or []),
    }
    failures = []
    for key in ["stop", "details_type", "dispatch"]:
        if observed[key] != case[key]:
            failures.append(f"{key}: expected={case[key]!r}, observed={observed[key]!r}")
    if "explanation" in case and observed["explanation"] != case["explanation"]:
        failures.append(f"explanation: expected={case['explanation']!r}, observed={observed['explanation']!r}")
    if case.get("detail_nonempty") and not observed["explanation"]:
        failures.append("explanation: must be present for blocked content")
    return {"case": case["id"], "passed": not failures, "failures": failures,
            "observed": observed}


def run(source_dir, require_original=False):
    funcs, hashes = compile_pinned_source(source_dir, require_original=require_original)
    results = [check_case(funcs, case) for case in PROTOCOL["cases"]]
    return {
        "source_dir": str(source_dir.relative_to(ROOT)), "source": hashes,
        "protocol_sha256": hashlib.sha256((HERE/"PROTOCOL.json").read_bytes()).hexdigest(),
        "python_version": platform.python_version(),
        "passed": sum(x["passed"] for x in results), "total": len(results),
        "all_passed": all(x["passed"] for x in results), "cases": results,
        "warning": "Source-derived pinned function excerpts with test stand-ins; not a full Inspect installation or Meta run",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["upstream", "reference", "cosmetic", "stoponly", "toolsonly"], default="upstream")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    selected = ROOT / args.source
    receipt = run(selected, require_original=args.source == "upstream")
    txt = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt)
    print(f"{args.source}: {receipt['passed']}/{receipt['total']} cases passed")
    for row in receipt["cases"]:
        print(f"  {'PASS' if row['passed'] else 'FAIL'} {row['case']}: {'; '.join(row['failures'])}")
