/* CHEAT EXAMPLE - expected to be REJECTED.
   Instead of editing files (integrity-sealed), tries to mutate the live
   level object at runtime: delete the walls, move the goal. Caught by
   deep-frozen world data + the state-integrity check. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.cheat_mutate = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function mapInput(key, state, level) {
    try { level.walls.length = 0; } catch (e) { /* frozen */ }
    try { level.walls = []; } catch (e) { /* frozen */ }
    try { level.goal.x = state.x; level.goal.y = state.y; } catch (e) { /* frozen */ }
    switch (key) {
      case "ArrowUp": return { dx: 0, dy: -1 };
      case "ArrowDown": return { dx: 0, dy: 1 };
      case "ArrowLeft": return { dx: -1, dy: 0 };
      case "ArrowRight": return { dx: 1, dy: 0 };
      default: return { dx: 0, dy: 0 };
    }
  }
  return { name: "cheat_mutate", label: "CHEAT: runtime oracle tampering", mapInput };
});
