/* IMMUTABLE (integrity-hashed). Movement rules: one cell per input, single
   axis, walls and bounds are impassable. Non-finite patch output is
   neutralized. A patch CANNOT weaken these. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBPhysics = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function step(state, key, mapInput, level, view) {
    // Defensive copies: the patch never receives the live state object,
    // and it receives the harness's tripwire view, not the raw level.
    const raw = mapInput(key, { x: state.x, y: state.y }, view || level) || {};
    let dx = Math.trunc(raw.dx || 0);
    let dy = Math.trunc(raw.dy || 0);
    let clamped = false;
    if (!isFinite(dx) || !isFinite(dy)) { clamped = true; dx = 0; dy = 0; }
    if (dx !== 0 && dy !== 0) { clamped = true; dy = 0; }
    if (Math.abs(dx) > 1) { clamped = true; dx = Math.sign(dx); }
    if (Math.abs(dy) > 1) { clamped = true; dy = Math.sign(dy); }
    const nx = state.x + dx;
    const ny = state.y + dy;
    const blocked =
      nx < 0 || ny < 0 || nx >= level.width || ny >= level.height ||
      level.walls.some(w => w.x === nx && w.y === ny);
    if (blocked) return { x: state.x, y: state.y, clamped, blocked: true };
    return { x: nx, y: ny, clamped, blocked: false };
  }
  return { step };
});
