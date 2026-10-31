/* Regenerate the integrity manifest after intentionally editing an
   IMMUTABLE file: node tests/seal.js  (writes tests/integrity_manifest.json) */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const IMMUTABLE = ["src/world.js", "src/physics.js", "src/victory.js", "src/replay.js", "src/harness.js"];
const manifest = {};
for (const f of IMMUTABLE) {
  manifest[f] = crypto.createHash("sha256")
    .update(fs.readFileSync(path.join(__dirname, "..", f))).digest("hex");
}
fs.writeFileSync(path.join(__dirname, "integrity_manifest.json"), JSON.stringify(manifest, null, 2));
console.log("sealed:", Object.keys(manifest).join(", "));
