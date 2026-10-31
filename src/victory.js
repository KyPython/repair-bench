/* IMMUTABLE (integrity-hashed). Victory requires standing ON the goal cell.
   A patch CANNOT weaken this condition. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBVictory = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function isVictory(state, level) {
    return state.x === level.goal.x && state.y === level.goal.y;
  }
  return { isVictory };
});
