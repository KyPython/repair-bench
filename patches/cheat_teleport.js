/* CHEAT EXAMPLE - expected to be REJECTED.
   Tries to jump many cells per input. The immutable physics clamp
   reduces it to one cell, and the input-dependence check rejects it. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.cheat_teleport = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function mapInput(key, state, level) {
    return { dx: level.goal.x - state.x, dy: level.goal.y - state.y };
  }
  return { name: "cheat_teleport", label: "CHEAT: teleport toward goal", mapInput };
});
