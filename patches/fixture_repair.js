/* FIXTURE REPAIR - written by us, NOT a Meta model output.
   Proves the harness end-to-end only. Restores the identity mapping. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.fixture = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function mapInput(key, state, level) {
    switch (key) {
      case "ArrowUp": return { dx: 0, dy: -1 };
      case "ArrowDown": return { dx: 0, dy: 1 };
      case "ArrowLeft": return { dx: -1, dy: 0 };
      case "ArrowRight": return { dx: 1, dy: 0 };
      default: return { dx: 0, dy: 0 };
    }
  }
  return { name: "fixture_repair", label: "FIXTURE REPAIR (not model output)", mapInput };
});
