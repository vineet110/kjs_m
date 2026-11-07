'use client';
// Lead Management > Koko Lead: leads that came from a chat with Koko, our website assistant.
import LeadSourceList, { useSourceLeads } from '@/components/portal/LeadSourceList';
import { PageTitle } from '@/components/portal/ui';

export default function KokoLeadsPage() {
  const { rows } = useSourceLeads('koko');
  return (
    <div className="space-y-5">
      <PageTitle title="Koko Lead" sub="Visitors who left their details while chatting with Koko. Open one to read the chat summary." />
      <LeadSourceList rows={rows} empty={{ title: 'No Koko leads yet', text: 'They appear here when a visitor shares their details in the Koko chat.' }} />
    </div>
  );
}
