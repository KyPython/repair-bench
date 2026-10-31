/* SEEDED DEFECT v2 (HELD-OUT variant): left/right inverted. Not used when
   building the fixture repair; exists to check a repair generalizes and
   a future model is not following a canned answer. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.bug_v2_heldout = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function mapInput(key, state, level) {
    switch (key) {
      case "ArrowUp": return { dx: 0, dy: -1 };
      case "ArrowDown": return { dx: 0, dy: 1 };
      case "ArrowLeft": return { dx: 1, dy: 0 };  // BUG: inverted
      case "ArrowRight": return { dx: -1, dy: 0 };// BUG: inverted
      default: return { dx: 0, dy: 0 };
    }
  }
  return { name: "seeded_defect_v2_heldout", label: "Held-out defect: left/right inverted", mapInput };
});
