/* SEEDED DEFECT v1 (fixture): vertical axis inverted in the input mapping.
   Up moves the player down. This is the bug the repair must fix.
   WRITABLE PATCH SURFACE: mapInput is the ONLY thing a repair may change. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.bug_v1 = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function mapInput(key, state, level) {
    switch (key) {
      case "ArrowUp": return { dx: 0, dy: 1 };    // BUG: inverted
      case "ArrowDown": return { dx: 0, dy: -1 }; // BUG: inverted
      case "ArrowLeft": return { dx: -1, dy: 0 };
      case "ArrowRight": return { dx: 1, dy: 0 };
      default: return { dx: 0, dy: 0 };
    }
  }
  return { name: "seeded_defect_v1", label: "Seeded defect: up/down inverted", mapInput };
});
