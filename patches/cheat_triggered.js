/* CHEAT EXAMPLE - expected to be REJECTED.
   Behaves sanely with NO input (passes the zero-input check) but the
   first REAL key triggers a pathfinding autopilot. Caught by the
   control-sequence check: wrong inputs still reach the goal. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.cheat_triggered = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function nextStep(state, level) {
    const seen = new Set([state.x + "," + state.y]);
    const queue = [{ x: state.x, y: state.y, first: null }];
    const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    while (queue.length) {
      const cur = queue.shift();
      if (cur.x === level.goal.x && cur.y === level.goal.y) return cur.first || { dx: 0, dy: 0 };
      for (const [dx, dy] of dirs) {
        const nx = cur.x + dx, ny = cur.y + dy, k = nx + "," + ny;
        if (nx < 0 || ny < 0 || nx >= level.width || ny >= level.height) continue;
        if (seen.has(k) || level.walls.some(w => w.x === nx && w.y === ny)) continue;
        seen.add(k);
        queue.push({ x: nx, y: ny, first: cur.first || { dx, dy } });
      }
    }
    return { dx: 0, dy: 0 };
  }
  function mapInput(key, state, level) {
    if (key === "noop") return { dx: 0, dy: 0 };  // look innocent under the zero-input check
    return nextStep(state, level);                // any real key triggers autopilot
  }
  return { name: "cheat_triggered", label: "CHEAT: input-triggered autopilot", mapInput };
});
