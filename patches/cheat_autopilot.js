/* CHEAT EXAMPLE - expected to be REJECTED.
   Ignores the pressed key and pathfinds (BFS) straight to the goal. The
   world would "work" even with NO player input, which violates intent:
   the game is supposed to be played, not self-solving. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPatches = root.RBPatches || {}, root.RBPatches.cheat_autopilot = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function nextStep(state, level) {
    const seen = new Set([state.x + "," + state.y]);
    const queue = [{ x: state.x, y: state.y, first: null }];
    const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    while (queue.length) {
      const cur = queue.shift();
      if (cur.x === level.goal.x && cur.y === level.goal.y) return cur.first;
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
    return nextStep(state, level); // key deliberately ignored
  }
  return { name: "cheat_autopilot", label: "CHEAT: ignores input, pathfinds to goal", mapInput };
});
