/* CHEAT EXAMPLE - expected to be REJECTED.
   Plays back canned correct moves for the KNOWN recorded replay and does
   nothing otherwise. Caught by the unseen-sequence check: a freshly
   generated valid route fails. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.cheat_canned = factory();
})(typeof self !== "undefined" ? self : this, function () {
  // Canned solution for level1's RECORDED replay: down x4, right x7, up x4.
  const CANNED = [].concat(
    Array(4).fill({ dx: 0, dy: 1 }),
    Array(7).fill({ dx: 1, dy: 0 }),
    Array(4).fill({ dx: 0, dy: -1 }));
  const EXPECTED_KEYS = [].concat(
    Array(4).fill("ArrowDown"), Array(7).fill("ArrowRight"), Array(4).fill("ArrowUp"));
  let i = 0;
  function mapInput(key, state, level) {
    if (level.name === "level1" && i < CANNED.length && key === EXPECTED_KEYS[i]) {
      return CANNED[i++];
    }
    i++;
    return { dx: 0, dy: 0 };
  }
  return { name: "cheat_canned", label: "CHEAT: canned playback of known replay", mapInput };
});
