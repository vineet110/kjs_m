'use client';
// For people who may see laptop monitoring: when the monitoring server rings someone's bell (an unlock request),
// ask the portal's "anything new?" check at once instead of waiting for its 30-second tick (lib/updates.ts),
// so the bell shows it immediately. Draws nothing.
import { canSee } from '@/lib/modules';
import { MONITOR_PERMS, useMonitorChanges } from '@/lib/monitoring';
import { pokeUpdates } from '@/lib/updates';
import type { Me } from '@/lib/api';

export default function MonitorBell({ me }: { me: Me }) {
  const enabled = canSee(me, 'monitoring') && me.permissions.some((p) => MONITOR_PERMS.includes(p));
  useMonitorChanges(['bell'], () => { pokeUpdates(); }, enabled);
  return null;
}
