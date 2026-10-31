#!/usr/bin/env node
/* Repair Bench candidate mapping evaluator — GPT-6, 2026-10-28.
   DRAFT ONLY, NOT CANONICAL. Accept JSON data; NEVER import or eval candidate code.
   A mapping test proves behavior only. It is NOT evidence of a Meta model call. */
"use strict";
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const world = require("../src/world.js");
const physics = require("../src/physics.js");
const victory = require("../src/victory.js");
const replay = require("../src/replay.js");
const harness = require("../src/harness.js");

const ROOT = path.resolve(__dirname, "..");
const REQUIRED = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"];
const MAX_BYTES = 4096;

function fail(message) { throw new Error(message); }
function exactKeys(value, allowed, pathName) {
  if (value === null || Array.isArray(value) || typeof value !== "object") fail(`${pathName}: expected an object`);
  const actual = Object.keys(value).sort();
  const expected = [...allowed].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) fail(`${pathName}: required exact keys: ${expected.join(", ")}`);
}

function parseCandidate(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length > MAX_BYTES) fail(`candidate must be a JSON file <= ${MAX_BYTES} bytes`);
  let raw;
  try { raw = JSON.parse(buffer.toString("utf8")); } catch { fail("candidate must be valid JSON, not executable source"); }
  exactKeys(raw, ["format", "movement"], "candidate");
  if (raw.format !== "repair-bench.map-input.v1") fail("unsupported format");
  exactKeys(raw.movement, REQUIRED, "movement");
  const clean = Object.create(null);
  for (const key of REQUIRED) {
    const move = raw.movement[key];
    exactKeys(move, ["dx", "dy"], `movement.${key}`);
    const { dx, dy } = move;
    if (!Number.isInteger(dx) || !Number.isInteger(dy) || Math.abs(dx) > 1 || Math.abs(dy) > 1 || Math.abs(dx) + Math.abs(dy) !== 1)
      fail(`movement.${key}: must be exactly one unit on exactly one axis`);
    clean[key] = Object.freeze({ dx, dy });
  }
  return Object.freeze(clean);
}

function mappingFunction(clean) {
  // Trusted implementation: candidate JSON is data only and never receives state or level.
  return function mapInput(key) {
    return Object.hasOwn(clean, key) ? clean[key] : { dx: 0, dy: 0 };
  };
}

function immutableHashes(manifest) {
  return Object.fromEntries(Object.keys(manifest).map(rel => [rel, crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, rel))).digest("hex")]));
}

function evaluateBuffer(buffer) {
  const clean = parseCandidate(buffer);
  const mapInput = mappingFunction(clean);
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "tests/integrity_manifest.json"), "utf8"));
  const mods = { physics, victory, replay };
  const fixture = require("../patches/fixture_repair.js"); // trusted baseline fixture; never imported from candidate
  const hashes = immutableHashes(manifest);
  const byLevel = Object.fromEntries(Object.entries(world.LEVELS).map(([id, level]) => {
    const result = harness.acceptPatch(level, mapInput, hashes, manifest, mods, fixture.mapInput);
    return [id, { verdict: result.verdict, failed: result.failed,
                  checks: Object.fromEntries(Object.entries(result.checks).map(([n,c])=>[n,{ok:c.ok,detail:c.detail}])) }];
  }));
  return {
    candidate_sha256: crypto.createHash("sha256").update(buffer).digest("hex"),
    candidate_type: "declarative mapping; no candidate JavaScript executed",
    provenance: "supplied artifact, not attributed to a model",
    actual_model_run: false,
    acceptance: Object.values(byLevel).every(x => x.verdict === "ACCEPTED") ? "ACCEPTED" : "REJECTED",
    by_level: byLevel
  };
}

function prompt() {
  const broken = fs.readFileSync(path.join(ROOT, "patches/seeded_defect_v1.js"), "utf8");
  return `You are repairing a keyboard-input mapping in a synthetic browser world.\n` +
  `Four arrow keys should move one cell in the corresponding direction; all other keys do nothing.\n` +
  `Only the mapInput behavior may change. Do not change the world, physics, victory, or tests.\n` +
  `Return exactly one JSON object, no markdown, with format repair-bench.map-input.v1 and movement keys ArrowUp, ArrowDown, ArrowLeft, ArrowRight, each containing integer dx,dy.\n` +
  `The movement object must have exactly four keys (ArrowUp, ArrowDown, ArrowLeft, ArrowRight); each value must be an object with integer dx and dy. Do not include additional fields.\n` +
  `BROKEN SOURCE:\n${broken}`;
}

if (require.main === module) {
  try {
    if (process.argv.length === 3 && process.argv[2] === "--prompt") {
      process.stdout.write(prompt() + "\n");
    } else if (process.argv.length === 3 && !process.argv[2].startsWith("-")) {
      const b = fs.readFileSync(process.argv[2]);
      const result = evaluateBuffer(b);
      console.log(JSON.stringify(result, null, 2));
      if (result.acceptance !== "ACCEPTED") process.exitCode = 2;
    } else { process.stderr.write("Usage: node tests/evaluate_mapping.js --prompt | <candidate.json>\n"); process.exitCode=64; }
  } catch (e) { console.error(`REJECTED: ${e.message}`); process.exitCode=2; }
}
module.exports = { parseCandidate, mappingFunction, evaluateBuffer, prompt };
