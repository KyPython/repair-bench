/* IMMUTABLE (integrity-hashed). Level definitions: original toy worlds.
   Deep-frozen so a patch cannot tamper with task/walls/goal at runtime. */
(function (root, factory) {
  if (typeof module !== "undefined") module.exports = factory();
  else root.RBWorld = factory();
})(typeof self !== "undefined" ? self : this, function () {
  function deepFreeze(o) {
    Object.freeze(o);
    for (const v of Object.values(o)) {
      if (v && typeof v === "object" && !Object.isFrozen(v)) deepFreeze(v);
    }
    return o;
  }
  const LEVELS = {
    level1: {
      name: "level1",
      width: 10,
      height: 8,
      start: { x: 1, y: 3 },
      goal: { x: 8, y: 3 },
      // Vertical barrier at x=5, single gap at y=7.
      walls: [0, 1, 2, 3, 4, 5, 6].map(y => ({ x: 5, y }))
    },
    level2: {
      name: "level2",
      width: 10,
      height: 8,
      start: { x: 8, y: 6 },
      goal: { x: 3, y: 1 },
      // Horizontal barrier at y=4, single gap at x=1.
      walls: [2, 3, 4, 5, 6, 7, 8, 9].map(x => ({ x, y: 4 }))
    }
  };
  return { LEVELS: deepFreeze(LEVELS) };
});
