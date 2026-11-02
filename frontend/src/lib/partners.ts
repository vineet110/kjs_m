// Partner types: the saved value (what the API accepts and the database keeps) and the label people see.
// "broker" is shown as "Referral partner" (UI step 4); the saved value stays, so older applications still match.
// The backend keeps the same list in content_service.PARTNER_LABELS.
export const PARTNER_TYPES = [
  ['agent', 'Sales agent'],
  ['broker', 'Referral partner'],
  ['forwarder', 'Freight forwarder'],
  ['distributor', 'Distributor'],
  ['other', 'Other'],
] as const;

/** One of the saved values above (a typo is a type error). */
export type PartnerType = (typeof PARTNER_TYPES)[number][0];

/** The label for a saved partner type; an unknown value is shown as it is, never blank. */
export function partnerLabel(value: string): string {
  return PARTNER_TYPES.find(([v]) => v === value)?.[1] ?? value;
}
