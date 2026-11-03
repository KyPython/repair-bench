# Submission pack — copy, paste, submit

Companion to `VIDEO_SCRIPT_3MIN.md`. Fill the two `[bracketed]` values after upload,
then work the checklist top to bottom. Deadline: November 4, 2026, 9:00 PM ET.

## YouTube upload

Title:

```text
Repair Bench — Prove the Fix (Meta Global AI Developer Hackathon)
```

Description:

```text
AI writes code now. Who checks it? Repair Bench is a sealed verification bench:
a proposed fix is accepted only when Chromium observes the fixed behavior —
keyboard, pointer, focus — live on camera.

- Synthetic menu + dialog challenges: cosmetic fixes rejected, functional repairs accepted
- Sealed game world: teleport and autopilot cheats rejected
- Real source: Inspect AI issue #5971, frozen 4/9 → 9/9 with controls
- Bounded Meta usage, stated plainly: two live Muse Spark calls, both returned
  clean completions whose patches failed scope review and were never executed

Repo (MIT): https://github.com/KyPython/repair-bench
Run it: PYTHONPATH=submission python3 submission/server.py --port 8765
Track: Indie — Push the Frontier

Chapters:
0:00 Who checks the AI's code
0:20 What Repair Bench is
0:45 Live demo: rejected, rejected, accepted
1:35 Real source, frozen evidence
2:15 The honest Meta result
2:45 Run it yourself
```

Tags: `meta hackathon, muse spark, ai code repair, accessibility, playwright, chromium, inspect ai, verifiable ai`

Visibility: unlisted or public per the contest rules. Publish WITH corrected captions.

## Hackathon form (paste-ready)

- Project title: `Repair Bench — Prove the Fix`
- Tagline: `A sealed bench that verifies AI code repairs by observing real Chromium behavior. Rejected unless the browser sees the fix.`
- Track: `Indie developer`
- Theme: `Push the Frontier`
- Meta tech used: `Muse Spark 1.3 via Meta Model API (two live calls with provider receipts, Nov 3 2026), plus AI-assisted authoring throughout`
- Repo: `https://github.com/KyPython/repair-bench`
- Demo video: `[YouTube URL after upload]`

Description (long):

```text
Repair Bench is a local, sealed behavioral verification demo for the age of
AI-written code. Two synthetic accessibility challenges (menu, dialog) offer
three trusted repair options each: unchanged and cosmetic-ARIA repairs are
rejected on camera while functional repairs are accepted, as observed by a real
Chromium oracle — never graded from the patch text. A sealed game-world
benchmark rejects rule-bypassing cheats the same way. A real-source extension
replays Inspect AI issue #5971 against pinned excerpts and frozen tests
(4/9 before, 9/9 after, with partial controls at 5/9, 4/9, 4/9).

Bounded Meta usage, fully receipted: two frozen requests to Muse Spark 1.3
returned clean completions whose patches failed scope review (hunk context
mismatch) and were never executed — two genuine negative results shown as such.
The freeze → scope-gate → isolated-sandbox → public-replay pipeline ran end to
end on real API calls; the same sandbox run reproduced every comparator score
and accepted the operator-supplied candidate 9/9.
```

## Pre-submit checklist

- [ ] `git push` current — public tree matches the recorded demo
- [ ] Video uploaded with corrected captions, visibility per rules
- [ ] Video URL pasted into the form draft above
- [ ] Signed-in eligibility and waiver review complete
- [ ] Form submitted before Nov 4, 9:00 PM ET (submit early; portals clog)
- [ ] After submitting: confirm the confirmation (screenshot it)
