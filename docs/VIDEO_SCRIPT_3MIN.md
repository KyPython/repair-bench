# Repair Bench — 3-minute hackathon demo script (FINAL v2)

Target: authentic 3-minute YouTube demo for the Meta Global AI Developer Hackathon.
Deadline: November 4, 2026, 9:00 PM ET. Owner records, edits, uploads, and submits.
Spoken target: ~370 words at a calm pace, plus live-click pauses. Timecodes assume ~130 wpm.
Track/theme fit: Indie track (creativity, technical ambition, whether it works) —
Push the Frontier: a new capability for the age of AI-written code.
Notion mirror: child of Lamport Logic HQ — https://app.notion.com/p/Repair-Bench-3-minute-hackathon-demo-script-FINAL-40d8621e0a7a81b88cb1dbcb57da2152 (page 40d8621e-0a7a-81b8-8cb1-dbcb57da2152).

v2 changes (post-audit): Muse Spark named in the first 10 seconds; pipeline-framing line
added to the Meta beat; stakes line added to the live demo; game-world beat compressed to
one line; captions and pre-flight added to the checklist. Word count held flat.

## Teleprompter copy (spoken words only)

AI writes code now. Who checks it? I built Repair Bench with Meta's Muse Spark to answer
that: a bench that proves a fix by watching real Chromium behavior. If the browser doesn't
observe it, the fix is rejected, no matter how good the patch looks.

Repair Bench is a local, sealed verification demo. Two synthetic accessibility challenges,
a menu and a dialog, each with three trusted repair options. Unchanged code and cosmetic
ARIA-only tweaks get rejected. Only repairs that change real pointer, keyboard, and focus
behavior get accepted.

Watch the menu. Option one: unchanged code. Rejected. Option two: ARIA labels with no
behavior change. Rejected. That is the fix that would have shipped and failed real users,
and the bench caught it. Option three: the functional repair. Chromium observes real
keyboard and focus behavior, and it is accepted. Same story on the dialog. The oracle is
behavior, not appearance.

Same oracle in the game world: cheats rejected, fair play accepted.

Then we took it to real source: a published Inspect AI bug, issue 5971, pinned excerpts,
frozen tests. The original code scores 4 of 9. The reference repair scores 9 of 9. Three
partial controls score 5, 4, and 4. Varied-input checks agree: 9 of 18 before, 18 of 18
after. The demo server never calls Meta; every number replays from frozen evidence.

Here is our bounded Meta usage, stated plainly. On November 3rd we sent one frozen request
to Muse Spark. It returned a clean completion, and its patch failed scope review, because
its diff headers did not apply to the frozen excerpts. So it was never executed. A genuine
negative result, shown as one. That pipeline — frozen request, scope gate, isolated sandbox,
public replay — is the Meta integration, run end to end on a real API call. The same sandbox
run reproduced every comparator score and accepted the operator-supplied candidate 9 of 9.

Everything is public under MIT. Clone it, run it, and Chromium checks every claim.
Repair Bench: prove the fix. Thank you.

## Spoken script with visuals

### 0:00–0:20 — Hook: who checks the AI's code

VISUAL: Title card: "Repair Bench — Prove the Fix." Cut to the local demo homepage.

SAY:
"AI writes code now. Who checks it? I built Repair Bench with Meta's Muse Spark to answer that: a bench that proves a fix by watching real Chromium behavior. If the browser doesn't observe it, the fix is rejected, no matter how good the patch looks."

### 0:20–0:45 — What this is

VISUAL: Scroll the homepage slowly. Highlight: sealed, local, loopback-only server.

SAY:
"Repair Bench is a local, sealed verification demo. Two synthetic accessibility challenges, a menu and a dialog, each with three trusted repair options. Unchanged code and cosmetic ARIA-only tweaks get rejected. Only repairs that change real pointer, keyboard, and focus behavior get accepted."

### 0:45–1:35 — Live demo: rejected, rejected, accepted

VISUAL: Run the menu challenge live. Click each option; show the verdict after each.

SAY:
"Watch the menu. Option one: unchanged code. Rejected. Option two: ARIA labels with no behavior change. Rejected. That is the fix that would have shipped and failed real users, and the bench caught it. Option three: the functional repair. Chromium observes real keyboard and focus behavior, and it is accepted. Same story on the dialog. The oracle is behavior, not appearance."

VISUAL: Quick cut to the dialog challenge showing one ACCEPTED verdict. Then a two-second glance at the game world rejecting a cheat.

SAY (over the cuts):
"Same oracle in the game world: cheats rejected, fair play accepted."

### 1:35–2:15 — Real source, frozen evidence

VISUAL: Open `/source-repair`. Show the frozen protocol hash and the score table.

SAY:
"Then we took it to real source: a published Inspect AI bug, issue 5971, pinned excerpts, frozen tests. The original code scores 4 of 9. The reference repair scores 9 of 9. Three partial controls score 5, 4, and 4. Varied-input checks agree: 9 of 18 before, 18 of 18 after. The demo server never calls Meta; every number replays from frozen evidence."

### 2:15–2:45 — The honest Meta result

VISUAL: Show the direct-trial panel: request hash, model name, token count, REJECTED AT SCOPE REVIEW.

SAY:
"Here is our bounded Meta usage, stated plainly. On November 3rd we sent one frozen request to Muse Spark. It returned a clean completion, and its patch failed scope review, because its diff headers did not apply to the frozen excerpts. So it was never executed. A genuine negative result, shown as one. That pipeline — frozen request, scope gate, isolated sandbox, public replay — is the Meta integration, run end to end on a real API call. The same sandbox run reproduced every comparator score and accepted the operator-supplied candidate 9 of 9."

### 2:45–3:00 — Close: run it yourself

VISUAL: Show the repo URL and the run commands. End card: repo link plus
"Indie track — Push the Frontier".

SAY:
"Everything is public under MIT. Clone it, run it, and Chromium checks every claim. Repair Bench: prove the fix. Thank you."

## Pre-flight (run before recording, on the recording machine)

```sh
cd /Users/ky/repair-bench
node tests/run_tests.js                    # expect 16 passed, 0 failed
node --test tests/evaluate_mapping.test.js # expect pass 11, fail 0
python3 -m unittest discover -s a11y-lab -p 'test_*.py'  # expect 37 OK (needs Playwright Chromium)
PYTHONPATH=submission python3 -m unittest discover -s submission -p 'test_*.py' -v  # expect 22 OK
node --check submission/app.js
PYTHONPATH=submission python3 submission/server.py --port 8765  # then open http://127.0.0.1:8765/
```

Fallback: if the live server misbehaves on camera, cut to the frozen evidence instead —
`source-repair/model-trial.json` (transport receipt, scores) and `tests/run_evidence.json`.
Do not fake a live verdict; narrate the replay as a replay.

## Recording checklist

1. Run the full pre-flight above; do not record on a red suite.
2. Fresh terminal, repo root, server on port 8765, homepage loaded before recording.
3. Record at 1080p, browser window only, no API keys or private tabs visible.
4. Do the menu clicks live; do not splice verdicts. One continuous take for 0:45–1:35 if possible.
5. Keyboard-check the demo page once (Tab through the menu and dialog). An accessibility
   project must not ship a mouse-only demo.
6. On `/source-repair`, pause two full seconds on the score table so it is readable.
7. On the trial panel, read the scope-rejection line exactly as shown. Do not paraphrase it into a success.
8. Slate the date (November 2026) and keep the video unlisted or public per the contest rules.
9. Publish WITH captions (YouTube auto-captions, reviewed and corrected). Non-negotiable
   for this entry: the project is about real usability, and at least one judge will notice.

## Claim-to-source audit (do not say more than this)

- "Built with Muse Spark": one live `muse-spark-1.3` call Nov 3 2026 with provider
  receipt in `source-repair/model-trial.json` (response `chatcmpl-01a1a2a2-…`, clean stop,
  6,791 tokens), plus AI-assisted authoring throughout. The video states the call's
  negative outcome plainly; the claim is usage plus pipeline, not a successful repair.
- Pipeline framing (freeze, scope gate, sandbox, replay): `docs/META_SOURCE_REPAIR_SPEC.md`
  criteria 3–10; `source-repair/trial/direct_meta_01/` (request, transport, sandbox report).
- Sealed behavioral verification, menu/dialog, three options each: README.md lines 5–6.
- Unchanged and cosmetic rejected, functional accepted: README.md line 6.
- Stakes line ("would have shipped and failed real users"): interpretation of the ARIA-only
  false-green rejection. Accurate as commentary; it is not a claim about a real product.
- Game-world cheat rejection: README.md line 6, index.html oracle.
- Loopback server, no Meta calls, no keys: submission/README.md, README.md line 20.
- Inspect AI issue 5971, snapshot 386e099, frozen protocol hash: source-repair/README.md lines 5, 26.
- Scores 4/9, 9/9, 5/9, 4/9, 4/9 and 9/18 vs 18/18: source-repair/README.md line 26.
- Scope-review rejection ("diff headers did not apply"): `source-repair/model-trial.json`
  candidates.direct_meta.scope (status rejected, "Hunk context mismatch"); never executed;
  operator candidate 9/9 with scope approved. Source-repair/README.md lines 48–62.
- In-CLI proposal 9/9 and 18/18 exists but provider identity not independently authenticated:
  README.md line 7, source-repair/README.md lines 34–46. Not claimed in this script.
- World test HTTP navigation vs restricted replay fallback: docs/WORLD_BROWSER_REGRESSION.md.
  Not demoed live; omitted rather than risk overclaim.
- Public MIT since Oct 31 2026, upstream notice kept: README.md line 36.
- Deadline Nov 4 2026 9 PM ET, eligibility/waiver/demo/form owner-controlled, organizers judge
  model-use requirement: README.md line 38.
- Track/theme fit (Indie; Push the Frontier): framing against the published event page
  (dev.meta.ai/events/global-hackathon); final track selection is the owner's in the form.
- Evidence-first, no-overclaim posture: Notion System Truth Map, Evaluation Registry,
  Oct 21 evaluation report.

## Open loops for the owner

- Run pre-flight on the recording machine (the agent's sandbox cannot bind ports or run
  Chromium, so the live demo is unverified tonight — see audit notes).
- Record, edit (DaVinci Resolve), caption, upload to YouTube.
- Complete signed-in eligibility and waiver review plus final form submission.
- Optional: commit this script doc to the repo before the deadline so the public tree
  matches the submission story.
