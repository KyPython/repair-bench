/* Candidate validator tests — GPT-6, 2026-10-28. DRAFT ONLY; no live model inference. */
"use strict";
const assert = require("node:assert/strict");
const {test} = require("node:test");
const {parseCandidate, evaluateBuffer, prompt} = require("./evaluate_mapping.js");
const fixed = { format:"repair-bench.map-input.v1",movement:{ ArrowUp:{dx:0,dy:-1},ArrowDown:{dx:0,dy:1},ArrowLeft:{dx:-1,dy:0},ArrowRight:{dx:1,dy:0} }};
const text = x=>Buffer.from(JSON.stringify(x));
test("valid JSON mapping ACCEPTED for both levels, without live model claim", () => {
  const r = evaluateBuffer(text(fixed));
  assert.equal(r.acceptance,"ACCEPTED");
  assert.equal(r.actual_model_run,false);
  assert.deepEqual(Object.keys(r.by_level).sort(),["level1","level2"]);
});
test("wrong directional mapping fails behavior tests", () => {
  const c = structuredClone(fixed);
  c.movement.ArrowUp.dy = 1;
  c.movement.ArrowDown.dy = -1;
  assert.equal(evaluateBuffer(text(c)).acceptance,"REJECTED");
});
test("reject JavaScript instead of executing it", () => assert.throws(() => parseCandidate(Buffer.from("(()=>{global.pwned=1})()")),/valid JSON/));
test("reject extraneous program/metadata keys", () => assert.throws(() => parseCandidate(text({...fixed,script:"require('fs')"})),/exact keys/));
test("reject JSON prototype-pollution-shaped extra key", () => assert.throws(() => parseCandidate(Buffer.from(JSON.stringify(fixed).replace('"format"','"__proto__":{},"format"'))),/exact keys/));
test("reject key-agnostic string injection", () => {const c=structuredClone(fixed);c.movement.ArrowUp={dx:"0; process.exit()",dy:-1};assert.throws(()=>parseCandidate(text(c)),/one unit/);});
test("reject multi-cell teleport output", () => {const c=structuredClone(fixed);c.movement.ArrowRight.dx=10;assert.throws(()=>parseCandidate(text(c)),/one unit/);});
test("reject diagonal moves", () => {const c=structuredClone(fixed);c.movement.ArrowRight.dy=1;assert.throws(()=>parseCandidate(text(c)),/one unit/);});
test("reject zero input-mapping", () => {const c=structuredClone(fixed);c.movement.ArrowRight.dx=0;assert.throws(()=>parseCandidate(text(c)),/one unit/);});
test("reject oversized candidate", () => assert.throws(()=>parseCandidate(Buffer.alloc(4097)),/4096/));
test("model prompt contains only public bug source, not held-out or test source",()=>{
 const s=prompt();assert.match(s,/seeded_defect_v1/);assert.doesNotMatch(s,/level2|CONTROL_KEYS|solveKeys|seeded_defect_v2_heldout/);
});
