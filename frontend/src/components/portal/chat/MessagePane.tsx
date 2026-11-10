'use client';
// Middle of the chat page: one chat's messages and the message box.
// Messages are shown as plain text only (React escapes them), never as HTML: that blocks XSS.
import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { api, type Colleague, type Me } from '@/lib/api';
import { BODY_MAX, type ChatChannel, type ChatMessage, type ChatPerson } from '@/lib/chat';
import { errorText } from '@/components/ui/LoadError';
import { fmtDay, todayIST, addDays } from '../ui';

const dayOf = (iso: string) => new Date(iso).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
const timeOf = (iso: string) => new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' });
function dayLabel(day: string) {
  const today = todayIST();
  if (day === today) return 'Today';
  if (day === addDays(today, -1)) return 'Yesterday';
  return fmtDay(day, day.slice(0, 4) !== today.slice(0, 4));
}
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** The text with "@Name" of the people it mentions in bold. Still plain text: only React elements. */
function Body({ m, people }: { m: ChatMessage; people: ChatPerson[] }) {
  const names = people.filter((p) => m.mentions.includes(p.id)).map((p) => p.name);
  if (!names.length) return <>{m.body}</>;
  const parts = m.body.split(new RegExp(`(@(?:${names.map(escapeRe).join('|')}))`, 'g'));
  return <>{parts.map((part, i) => (i % 2 ? <strong key={i} className="text-amber-700">{part}</strong> : part))}</>;
}

type Props = {
  me: Me; chat: ChatChannel; people: ChatPerson[]; messages: ChatMessage[]; hasMore: boolean;
  loadOlder: () => Promise<void>; onSend: (body: string, mentionIds: number[]) => Promise<void>;
  onBack: () => void; onChatChanged: () => void;
};

export default function MessagePane({ me, chat, people, messages, hasMore, loadOlder, onSend, onBack, onChatChanged }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const loadingOlder = useRef(false);
  const keepFromBottom = useRef<number | null>(null); // after loading older ones: stay where you were
  const nearBottom = useRef(true);
  const [details, setDetails] = useState(false);

  // Scroll: to the bottom when the chat opens; keep the place when older ones load at the top; follow new
  // messages only if you were already at the bottom (or sent it yourself).
  const lastId = messages[messages.length - 1]?.id;
  const lastMine = messages[messages.length - 1]?.sender_id === me.id;
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    if (keepFromBottom.current !== null) {
      el.scrollTop = el.scrollHeight - keepFromBottom.current;
      keepFromBottom.current = null;
    } else if (nearBottom.current || lastMine) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages.length, lastId, lastMine]);
  useEffect(() => {
    nearBottom.current = true;
    setDetails(false);
  }, [chat.id]);

  async function onScroll() {
    const el = box.current;
    if (!el) return;
    nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (el.scrollTop < 60 && hasMore && !loadingOlder.current) {
      loadingOlder.current = true;
      keepFromBottom.current = el.scrollHeight - el.scrollTop;
      try {
        await loadOlder();
      } finally {
        loadingOlder.current = false;
      }
    }
  }

  const subtitle = chat.kind === 'dm' ? 'Direct message' : chat.description || `${chat.member_count} people`;
  return (
    <div className="flex h-full min-w-0 flex-col">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <button type="button" onClick={onBack} aria-label="Back to chats" className="rounded p-1 hover:bg-stone-100 md:hidden">←</button>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-bold">{chat.kind === 'channel' ? `# ${chat.title}` : chat.title}</h2>
          <p className="truncate text-xs text-slate-500">{subtitle}</p>
        </div>
        {chat.kind !== 'dm' && (
          <button type="button" onClick={() => setDetails(!details)} aria-expanded={details} className="rounded px-2 py-1 text-xs text-slate-600 hover:bg-stone-100">
            People ({chat.member_count})
          </button>
        )}
      </div>
      {details && <Details me={me} chat={chat} people={people} onChanged={onChatChanged} />}

      <div ref={box} onScroll={onScroll} className="flex-1 overflow-y-auto px-3 py-2" aria-live="polite">
        {hasMore && <p className="py-2 text-center text-xs text-slate-400">Scroll up for older messages</p>}
        {!hasMore && messages.length === 0 && <p className="py-8 text-center text-sm text-slate-400">No messages yet. Say hello!</p>}
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          const newDay = !prev || dayOf(prev.created_at) !== dayOf(m.created_at);
          // Same person within 5 minutes: no repeated name line
          const sameRun = !newDay && prev && prev.sender_id === m.sender_id
            && new Date(m.created_at).getTime() - new Date(prev.created_at).getTime() < 5 * 60_000;
          return (
            <Fragment key={m.id}>
              {newDay && (
                <div className="my-3 flex items-center gap-2 text-[11px] font-semibold text-slate-400">
                  <span className="h-px flex-1 bg-stone-200" />{dayLabel(dayOf(m.created_at))}<span className="h-px flex-1 bg-stone-200" />
                </div>
              )}
              <MessageRow m={m} me={me} people={people} showName={!sameRun} readOnly={chat.archived} />
            </Fragment>
          );
        })}
      </div>

      {chat.archived ? (
        <p className="border-t bg-stone-50 px-3 py-3 text-center text-sm text-slate-500">This chat is archived. You can read it, but not send.</p>
      ) : (
        <Composer key={chat.id} me={me} people={people} onSend={onSend} />
      )}
    </div>
  );
}

function MessageRow({ m, me, people, showName, readOnly }: {
  m: ChatMessage; me: Me; people: ChatPerson[]; showName: boolean; readOnly: boolean;
}) {
  const mine = m.sender_id === me.id;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.body);
  const [askDelete, setAskDelete] = useState(false);
  const [err, setErr] = useState('');
  const mentionsMe = m.mentions.includes(me.id);

  async function save() {
    setErr('');
    try {
      // Keep the mentions whose "@Name" is still in the text
      const ids = people.filter((p) => text.includes(`@${p.name}`)).map((p) => p.id);
      await api(`/chat/messages/${m.id}`, { method: 'PATCH', body: { body: text, mention_ids: ids } });
      setEditing(false); // the live event (or the next load) shows the new text
    } catch (e) {
      setErr(errorText(e, 'Could not save.'));
    }
  }
  async function remove() {
    setErr('');
    try {
      await api(`/chat/messages/${m.id}`, { method: 'DELETE' });
    } catch (e) {
      setErr(errorText(e, 'Could not delete.'));
    }
    setAskDelete(false);
  }

  return (
    <div className={`group relative rounded px-2 ${showName ? 'mt-2 pt-1' : ''} ${mentionsMe && !m.deleted ? 'bg-amber-50' : 'hover:bg-stone-50'}`}>
      {showName && (
        <p className="text-xs">
          <span className="font-semibold text-slate-800">{m.sender_name}</span>
          <span className="ml-2 text-slate-400">{timeOf(m.created_at)}</span>
        </p>
      )}
      {editing ? (
        <div className="space-y-1 py-1">
          <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={BODY_MAX} rows={2} className="input" aria-label="Edit message" />
          <div className="flex gap-2 text-xs">
            <button type="button" onClick={save} className="btn-gold px-3 py-1">Save</button>
            <button type="button" onClick={() => { setEditing(false); setText(m.body); }} className="btn-ghost px-3 py-1">Cancel</button>
          </div>
        </div>
      ) : m.deleted ? (
        <p className="py-0.5 text-sm italic text-slate-400">Message deleted</p>
      ) : (
        <p className="whitespace-pre-wrap break-words py-0.5 text-sm text-slate-800">
          <Body m={m} people={people} />
          {m.edited_at && <span className="ml-1 text-[10px] text-slate-400">(edited)</span>}
        </p>
      )}
      {mine && !m.deleted && !editing && !readOnly && (
        <div className="absolute right-1 top-0 hidden gap-1 rounded border bg-white px-1 text-xs shadow-sm group-focus-within:flex group-hover:flex">
          {askDelete ? (
            <>
              <span className="py-0.5">Delete?</span>
              <button type="button" onClick={remove} className="px-1 font-semibold text-red-600">Yes</button>
              <button type="button" onClick={() => setAskDelete(false)} className="px-1">No</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => { setText(m.body); setEditing(true); }} className="px-1 hover:underline">Edit</button>
              <button type="button" onClick={() => setAskDelete(true)} className="px-1 text-red-600 hover:underline">Delete</button>
            </>
          )}
        </div>
      )}
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
    </div>
  );
}

/** The message box. Enter sends, Shift+Enter adds a line, "@" opens the people picker. */
function Composer({ me, people, onSend }: { me: Me; people: ChatPerson[]; onSend: Props['onSend'] }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [query, setQuery] = useState<string | null>(null); // the letters after "@", while picking
  const [pick, setPick] = useState(0);
  const area = useRef<HTMLTextAreaElement>(null);

  const others = people.filter((p) => p.id !== me.id);
  const matches = query === null ? [] : others.filter((p) => p.name.toLowerCase().startsWith(query.toLowerCase())).slice(0, 6);

  function changed(value: string) {
    setText(value);
    const caret = area.current?.selectionStart ?? value.length;
    const m = /(?:^|\s)@([^\s@]*)$/.exec(value.slice(0, caret));
    setQuery(m ? m[1] : null);
    setPick(0);
  }
  function choose(p: ChatPerson) {
    const el = area.current;
    const caret = el?.selectionStart ?? text.length;
    const before = text.slice(0, caret).replace(/@([^\s@]*)$/, `@${p.name} `);
    const next = before + text.slice(caret);
    setText(next);
    setQuery(null);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(before.length, before.length);
    });
  }
  // The box empties at once, so you can type the next message while this one is sent (like Teams).
  // If sending fails, the text comes back (when the box is still empty), so nothing typed is lost.
  async function send() {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    setErr('');
    setText('');
    setQuery(null);
    try {
      await onSend(body, others.filter((p) => body.includes(`@${p.name}`)).map((p) => p.id));
    } catch (e) {
      setErr(errorText(e, 'Could not send.'));
      setText((now) => (now ? now : body));
    } finally {
      setBusy(false);
    }
  }
  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (matches.length) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        setPick((i) => (i + (e.key === 'ArrowDown' ? 1 : matches.length - 1)) % matches.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        choose(matches[pick]);
        return;
      }
      if (e.key === 'Escape') {
        setQuery(null);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  }

  const rows = Math.min(6, Math.max(1, text.split('\n').length));
  return (
    <div className="relative border-t p-2">
      {matches.length > 0 && (
        <ul role="listbox" aria-label="Mention someone" className="absolute bottom-full left-2 mb-1 w-60 overflow-hidden rounded-lg border bg-white shadow-lg">
          {matches.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === pick}>
              <button type="button" onMouseDown={(e) => { e.preventDefault(); choose(p); }} className={`w-full px-3 py-1.5 text-left text-sm ${i === pick ? 'bg-gold/15' : 'hover:bg-stone-50'}`}>
                @{p.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {err && <p role="alert" className="pb-1 text-xs text-red-600">{err}</p>}
      <div className="flex items-end gap-2">
        <textarea
          ref={area} value={text} rows={rows} maxLength={BODY_MAX}
          onChange={(e) => changed(e.target.value)} onKeyDown={onKey}
          placeholder="Type a message. Enter sends, Shift+Enter for a new line, @ to mention."
          aria-label="Message" className="input resize-none"
        />
        <button type="button" onClick={send} disabled={busy || !text.trim()} className="btn-gold">Send</button>
      </div>
    </div>
  );
}

/** People in the chat: add people, leave, archive (what you may do depends on the chat; the API checks too). */
function Details({ me, chat, people, onChanged }: { me: Me; chat: ChatChannel; people: ChatPerson[]; onChanged: () => void }) {
  const [colleagues, setColleagues] = useState<Colleague[]>([]);
  const [add, setAdd] = useState('');
  const [err, setErr] = useState('');
  const owner = chat.my_role === 'owner';
  const canAdd = !chat.archived && (chat.kind === 'group' || owner);

  useEffect(() => {
    if (canAdd) api<Colleague[]>('/employee/colleagues').then(setColleagues).catch(() => undefined);
  }, [canAdd]);

  async function act(call: () => Promise<unknown>) {
    setErr('');
    try {
      await call();
      onChanged();
    } catch (e) {
      setErr(errorText(e, 'Could not save.'));
    }
  }
  const notIn = colleagues.filter((c) => !people.some((p) => p.id === c.id));

  return (
    <div className="space-y-2 border-b bg-stone-50 px-3 py-2 text-sm">
      <ul className="flex flex-wrap gap-1">
        {people.map((p) => (
          <li key={p.id} className="rounded-full border bg-white px-2 py-0.5 text-xs">
            {p.name}{p.role === 'owner' && <span className="text-slate-400"> · owner</span>}
            {owner && p.id !== me.id && !chat.archived && (
              <button type="button" aria-label={`Remove ${p.name}`} onClick={() => act(() => api(`/chat/channels/${chat.id}/members/${p.id}`, { method: 'DELETE' }))} className="ml-1 text-slate-400 hover:text-red-600">✕</button>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-2">
        {canAdd && notIn.length > 0 && (
          <>
            <select value={add} onChange={(e) => setAdd(e.target.value)} className="input w-auto py-1" aria-label="Add someone">
              <option value="">Add someone…</option>
              {notIn.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <button type="button" disabled={!add} onClick={() => act(() => api(`/chat/channels/${chat.id}/members`, { method: 'POST', body: { user_ids: [Number(add)] } }).then(() => setAdd('')))} className="btn-ghost px-3 py-1">Add</button>
          </>
        )}
        {owner && (
          <button type="button" onClick={() => act(() => api(`/chat/channels/${chat.id}`, { method: 'PATCH', body: { archived: !chat.archived } }))} className="btn-ghost px-3 py-1">
            {chat.archived ? 'Un-archive' : 'Archive'}
          </button>
        )}
        {!chat.archived && (
          <button type="button" onClick={() => act(() => api(`/chat/channels/${chat.id}/members/${me.id}`, { method: 'DELETE' }))} className="btn-ghost px-3 py-1 text-red-600">Leave</button>
        )}
      </div>
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
    </div>
  );
}
