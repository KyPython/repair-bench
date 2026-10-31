/* IMMUTABLE (integrity-hashed). Deterministic recorded keyboard replays.
   The SAME inputs are run before and after any repair. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBReplay = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const REPLAYS = {
    // level1: down x4, right x7, up x4  (1,3)->(1,7)->(8,7)->(8,3)
    level1: [].concat(
      Array(4).fill("ArrowDown"),
      Array(7).fill("ArrowRight"),
      Array(4).fill("ArrowUp")),
    // level2: left x7, up x5, right x2  (8,6)->(1,6)->(1,1)->(3,1)
    level2: [].concat(
      Array(7).fill("ArrowLeft"),
      Array(5).fill("ArrowUp"),
      Array(2).fill("ArrowRight"))
  };

  function runReplay(level, mapInput, keys, physics, victory) {
    let state = { x: level.start.x, y: level.start.y };
    const path = [Object.assign({}, state)];
    let clamped = 0, blockedCount = 0;
    for (const key of keys) {
      state = physics.step(state, key, mapInput, level);
      if (state.clamped) clamped++;
      if (state.blocked) blockedCount++;
      path.push({ x: state.x, y: state.y });
    }
    return {
      end: { x: state.x, y: state.y },
      path,
      clamped,
      blocked: blockedCount,
      victory: victory.isVictory(state, level)
    };
  }

  return { REPLAYS, runReplay };
});
