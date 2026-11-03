// The order of the sidebar groups (My work, Admin, People, …), which each person can change by dragging.
// Plain functions on lists of group names, so they are easy to test (tests/lib.test.mjs).

/** `names` in the saved order. Names the saved order doesn't know (a group added later) go to the end,
 * in their default order. */
export function sortByOrder(names: string[], saved: string[], defaults: string[]): string[] {
  const at = (n: string) => {
    const i = saved.indexOf(n);
    return i === -1 ? saved.length + defaults.indexOf(n) : i;
  };
  return [...names].sort((a, b) => at(a) - at(b));
}

/** The new full order after moving group `g` to place `to` among the groups this person can see (`shown`,
 * in their current order). Groups they can't see keep their place after these, so another account in the
 * same browser doesn't lose its own order. */
export function moveGroup(shown: string[], saved: string[], defaults: string[], g: string, to: number): string[] {
  const seen = shown.filter((x) => x !== g);
  seen.splice(Math.max(0, Math.min(to, seen.length)), 0, g);
  const rest = [...saved, ...defaults].filter((x, i, all) => !seen.includes(x) && all.indexOf(x) === i);
  return [...seen, ...rest];
}
