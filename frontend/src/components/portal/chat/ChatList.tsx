'use client';
// Left column of the chat page: channels, then direct messages and group chats, each with its unread count.
import type { ChatChannel } from '@/lib/chat';
import { Icon } from '../icons';

function Row({ c, active, onSelect }: { c: ChatChannel; active: boolean; onSelect: (id: number) => void }) {
  const unread = c.unread ?? 0;
  const mark = c.kind === 'channel' ? '#' : c.kind === 'group' ? '👥' : '';
  return (
    <button
      type="button"
      onClick={() => onSelect(c.id)}
      aria-current={active ? 'true' : undefined}
      className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm ${active ? 'bg-gold/15 font-semibold text-slate-900' : 'text-slate-700 hover:bg-stone-100'} ${c.archived ? 'opacity-60' : ''}`}
    >
      <span aria-hidden className="w-5 shrink-0 text-center text-slate-400">{mark}</span>
      <span className={`flex-1 truncate ${unread > 0 && !c.muted ? 'font-semibold text-slate-900' : ''}`}>{c.title}</span>
      {c.archived && <span className="text-[10px] text-slate-400">archived</span>}
      {unread > 0 && (
        <span className={`min-w-[20px] rounded-full px-1.5 text-center text-[11px] font-bold leading-5 ${c.muted ? 'bg-stone-200 text-slate-600' : 'bg-red-600 text-white'}`}>
          {unread > 99 ? '99+' : unread}
          <span className="sr-only"> unread</span>
        </span>
      )}
    </button>
  );
}

export default function ChatList({ chats, activeId, onSelect, onNew }: {
  chats: ChatChannel[]; activeId: number | null; onSelect: (id: number) => void; onNew: () => void;
}) {
  const channels = chats.filter((c) => c.kind === 'channel');
  const people = chats.filter((c) => c.kind !== 'channel');
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <h1 className="text-sm font-bold">Chat</h1>
        <button type="button" onClick={onNew} aria-label="New chat or channel" title="New chat or channel" className="rounded p-1 hover:bg-stone-100">
          <Icon name="plus" className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-2">
        <section>
          <h2 className="px-2 pb-1 text-[11px] font-bold uppercase tracking-widest text-slate-400">Channels</h2>
          {channels.length === 0 && <p className="px-2 text-xs text-slate-400">No channels yet.</p>}
          {channels.map((c) => <Row key={c.id} c={c} active={c.id === activeId} onSelect={onSelect} />)}
        </section>
        <section>
          <h2 className="px-2 pb-1 text-[11px] font-bold uppercase tracking-widest text-slate-400">Direct messages</h2>
          {people.length === 0 && <p className="px-2 text-xs text-slate-400">No chats yet. Press + to start one.</p>}
          {people.map((c) => <Row key={c.id} c={c} active={c.id === activeId} onSelect={onSelect} />)}
        </section>
      </div>
    </div>
  );
}
