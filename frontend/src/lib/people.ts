// Finding a colleague by typing part of their name or employee code (PersonPicker).

export type Person = { id: number; name: string; employee_code?: string };

const MAX_SHOWN = 8;

/** People whose name or employee code contains the text (any case), best matches first: those that start
 *  with it, then the rest; then A to Z. Exported for tests. */
export function matchPeople(people: Person[], text: string, max = MAX_SHOWN): Person[] {
  const q = text.trim().toLowerCase();
  if (!q) return people.slice(0, max);
  const hits = people.filter((p) => p.name.toLowerCase().includes(q) || (p.employee_code ?? '').toLowerCase().includes(q));
  const starts = (p: Person) => p.name.toLowerCase().startsWith(q) || (p.employee_code ?? '').toLowerCase().startsWith(q);
  return hits.sort((a, b) => Number(starts(b)) - Number(starts(a)) || a.name.localeCompare(b.name)).slice(0, max);
}

/** Enter in the picker: the highlighted match, or null when nothing was highlighted yet (then Enter just closes
 *  the list and submits the form; it never quietly picks the first colleague). Exported for tests. */
export function enterPick(at: number, matches: Person[]): Person | null {
  return at >= 0 && at < matches.length ? matches[at] : null;
}
