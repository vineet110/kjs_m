'use client';
// KJS Chat (our own Teams): channels, group chats and direct messages, live.
// 1. Everything is saved in the database; the live connection only pushes changes (lib/chat.ts).
// 2. After a dropped connection it fetches what it missed (after=<last id>), plus the newest 50 again so
//    edits and deletes made meanwhile show. (Older ones than that update on the next reload: accepted.)
// 3. ?c=<id> opens a chat (links in @mention notifications use it).
// Plan and rules: docs/tempV.md, "KJS Chat".
import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useMe } from '@/components/portal/PortalShell';
import ChatList from '@/components/portal/chat/ChatList';
import MessagePane from '@/components/portal/chat/MessagePane';
import NewChat from '@/components/portal/chat/NewChat';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';
import { api, ApiFailure } from '@/lib/api';
import { useOnUpdate } from '@/lib/updates';
import {
  chatUnreadChanged, useChatSocket,
  type ChatChannel, type ChatEvent, type ChatMessage, type ChatPage, type ChatPerson,
} from '@/lib/chat';

/** Replace by id, only if it's on screen. For edits and deletes: an edit of an older message that isn't
 *  loaded must not be added (it would jump to the top and break "load older": PR #55 review). */
function replace(list: ChatMessage[], m: ChatMessage): ChatMessage[] {
  return list.some((x) => x.id === m.id) ? list.map((x) => (x.id === m.id ? m : x)) : list;
}

/** Add or replace by id, oldest first (the same message can come from our POST and the live event).
 *  For NEW messages only; edits use replace(). */
function upsert(list: ChatMessage[], m: ChatMessage): ChatMessage[] {
  const i = list.findIndex((x) => x.id === m.id);
  if (i >= 0) return list.map((x) => (x.id === m.id ? m : x));
  return [...list, m].sort((a, b) => a.id - b.id);
}
const visible = () => document.visibilityState === 'visible';
const REFRESH_MS = 500;

function ChatPageInner() {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const activeId = Number(params.get('c')) || null;

  const [chats, setChats] = useState<ChatChannel[] | null>(null);
  const [chatsErr, setChatsErr] = useState<unknown>(null);
  const [active, setActive] = useState<ChatChannel | null>(null);
  const [people, setPeople] = useState<ChatPerson[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [openErr, setOpenErr] = useState<unknown>(null);
  const [newChat, setNewChat] = useState(false);

  // The newest values, for the live-event handler (it is set up once)
  const activeRef = useRef<number | null>(null);
  activeRef.current = activeId;
  const chatsRef = useRef<ChatChannel[] | null>(null);
  chatsRef.current = chats;
  const lastIdRef = useRef(0);
  lastIdRef.current = messages[messages.length - 1]?.id ?? 0;
  const readUpTo = useRef<Record<number, number>>({}); // what we already told the server we read
  const opening = useRef(0); // only the newest chat opened counts

  const loadChats = useCallback(() => {
    setChatsErr(null);
    api<ChatChannel[]>('/chat/channels').then(setChats).catch(setChatsErr);
  }, []);
  useEffect(() => loadChats(), [loadChats]);

  // Each re-count scans all my chats on the server, and events can come in bursts: at most one list reload
  // and one sidebar re-count every REFRESH_MS (PR #55 review).
  const timers = useRef<{ chats?: ReturnType<typeof setTimeout>; unread?: ReturnType<typeof setTimeout> }>({});
  const soon = useCallback((which: 'chats' | 'unread') => {
    if (timers.current[which]) return; // one is already on its way
    timers.current[which] = setTimeout(() => {
      timers.current[which] = undefined;
      if (which === 'chats') loadChats();
      else chatUnreadChanged();
    }, REFRESH_MS);
  }, [loadChats]);
  useEffect(() => {
    const t = timers.current;
    return () => { clearTimeout(t.chats); clearTimeout(t.unread); };
  }, []);

  const loadDetails = useCallback(async (id: number) => {
    const c = await api<ChatChannel>(`/chat/channels/${id}`);
    if (activeRef.current !== id) return;
    setActive(c);
    setPeople(c.members ?? []);
  }, []);

  // Open the chat in the URL
  useEffect(() => {
    const n = ++opening.current;
    setActive(null);
    setMessages([]);
    setHasMore(false);
    setOpenErr(null);
    if (!activeId) return;
    Promise.all([api<ChatChannel>(`/chat/channels/${activeId}`), api<ChatPage>(`/chat/channels/${activeId}/messages`)])
      .then(([c, page]) => {
        if (n !== opening.current) return;
        setActive(c);
        setPeople(c.members ?? []);
        // Merge, don't replace: a live message may have arrived while this page was loading (PR #55 review)
        setMessages((list) => page.messages.reduce(upsert, list.filter((x) => x.channel_id === activeId)));
        setHasMore(page.has_more);
      })
      .catch((e) => n === opening.current && setOpenErr(e));
  }, [activeId]);

  const select = useCallback((id: number | null) => {
    router.replace(id ? `${pathname}?c=${id}` : pathname);
  }, [router, pathname]);

  // Mark read: when the open chat shows a message we haven't reported yet, and the tab is in front
  const markRead = useCallback(() => {
    const id = activeRef.current;
    const last = lastIdRef.current;
    if (!id || !last || !visible() || (readUpTo.current[id] ?? 0) >= last) return;
    readUpTo.current[id] = last;
    setChats((cs) => cs?.map((c) => (c.id === id ? { ...c, unread: 0 } : c)) ?? cs);
    api(`/chat/channels/${id}/read`, { method: 'POST', body: { message_id: last } })
      .then(() => soon('unread'))
      .catch(() => { readUpTo.current[id] = 0; }); // try again next time
  }, [soon]);
  useEffect(markRead, [markRead, activeId, messages.length, active]);
  useEffect(() => {
    document.addEventListener('visibilitychange', markRead);
    return () => document.removeEventListener('visibilitychange', markRead);
  }, [markRead]);

  // Live events
  const onEvent = useCallback((e: ChatEvent) => {
    switch (e.type) {
      case 'message.new': {
        const m = e.message;
        const here = e.channel_id === activeRef.current;
        if (here) setMessages((list) => upsert(list, m));
        if (!chatsRef.current?.some((c) => c.id === e.channel_id)) {
          soon('chats'); // a chat I was just added to
        } else {
          const unseen = m.sender_id !== me.id && !(here && visible());
          setChats((cs) => cs?.map((c) => (c.id === e.channel_id
            ? { ...c, last_message_id: m.id, unread: (c.unread ?? 0) + (unseen ? 1 : 0) } : c)) ?? cs);
        }
        if (m.sender_id !== me.id) soon('unread');
        break;
      }
      case 'message.edited':
        if (e.channel_id === activeRef.current) setMessages((list) => replace(list, e.message));
        break;
      case 'message.deleted':
        if (e.channel_id === activeRef.current) {
          setMessages((list) => list.map((x) => (x.id === e.message_id ? { ...x, deleted: true, body: '', mentions: [] } : x)));
        }
        soon('chats'); // a deleted unread message no longer counts
        soon('unread');
        break;
      case 'read': // read in one of my tabs
        // This tab already knows (it did the reading itself, or heard it already): nothing to do.
        // Another tab of mine read further: update the counts here too.
        if ((readUpTo.current[e.channel_id] ?? 0) >= e.message_id) break;
        readUpTo.current[e.channel_id] = e.message_id;
        soon('chats');
        soon('unread');
        break;
      case 'channel.changed':
        soon('chats');
        if (e.channel_id === activeRef.current) {
          loadDetails(e.channel_id).catch((err) => {
            if (err instanceof ApiFailure && err.status === 404) select(null); // I left or was removed
          });
        }
        break;
    }
  }, [me.id, soon, loadDetails, select]);

  // Every time the connection opens (the first time too): fetch what may have been missed
  const onConnect = useCallback(() => {
    soon('chats');
    const id = activeRef.current;
    if (!id) return;
    const last = lastIdRef.current;
    // 1. New messages since the last one we have. Skipped while the chat is still loading (last = 0):
    //    "after 0" would fetch the OLDEST 100. 2. The newest 50 again: edits and deletes made while the
    //    connection was down only show this way (their live events were lost).
    Promise.all([
      last ? api<ChatPage>(`/chat/channels/${id}/messages?after=${last}&limit=100`) : Promise.resolve(null),
      api<ChatPage>(`/chat/channels/${id}/messages`),
    ])
      .then(([missed, newest]) => {
        if (activeRef.current !== id) return;
        if (!missed) {
          setMessages((list) => newest.messages.reduce(upsert, list.filter((x) => x.channel_id === id)));
          return;
        }
        if (missed.has_more) {
          // Missed more than 100: start again from the newest page (scrolling up loads the rest)
          setMessages(newest.messages);
          setHasMore(newest.has_more);
          return;
        }
        setMessages((list) => [...missed.messages, ...newest.messages].reduce(upsert, list));
      })
      .catch(() => undefined);
  }, [soon]);

  const socket = useChatSocket(onEvent, onConnect);
  // Without a live connection (on Vercel, until server push), the portal's 30-second check notices new
  // messages: when the newest message in my chats changes (muted chats too; my own reads don't move it),
  // catch up the same way as after a reconnect.
  useOnUpdate(me.id, (u) => u.chat_last, onConnect);

  const loadOlder = useCallback(async () => {
    const id = activeRef.current;
    const first = messages[0]?.id;
    if (!id || !first) return;
    const page = await api<ChatPage>(`/chat/channels/${id}/messages?before=${first}`);
    if (activeRef.current !== id) return;
    setMessages((list) => [...page.messages, ...list]);
    setHasMore(page.has_more);
  }, [messages]);

  const send = useCallback(async (body: string, mentionIds: number[]) => {
    const id = activeRef.current;
    if (!id) return;
    const m = await api<ChatMessage>(`/chat/channels/${id}/messages`, { method: 'POST', body: { body, mention_ids: mentionIds } });
    if (activeRef.current === id) setMessages((list) => upsert(list, m));
    setChats((cs) => cs?.map((c) => (c.id === id ? { ...c, last_message_id: m.id } : c)) ?? cs);
  }, []);

  // My own edit or delete, once the server confirmed it: shown at once, without waiting for the live
  // event (which may not come if the connection is down).
  const changed = useCallback((m: ChatMessage) => {
    if (m.channel_id === activeRef.current) setMessages((list) => replace(list, m));
  }, []);

  // The same functions on every redraw, so the dialog doesn't set itself up again on each live event
  const closeNewChat = useCallback(() => setNewChat(false), []);
  const newChatDone = useCallback((c: ChatChannel) => { setNewChat(false); loadChats(); select(c.id); }, [loadChats, select]);

  if (chatsErr) return <LoadError error={chatsErr} onRetry={loadChats} />;
  if (chats === null) return <Loading />;

  return (
    // Fills the screen under the portal header (2.75rem) and the page padding (1rem / 2rem each side)
    <div className="card flex h-[calc(100dvh-2.75rem-2rem)] overflow-hidden md:h-[calc(100dvh-2.75rem-4rem)]">
      <aside className={`w-full shrink-0 border-r md:block md:w-64 ${activeId ? 'hidden' : 'block'}`}>
        <ChatList chats={chats} activeId={activeId} onSelect={select} onNew={() => setNewChat(true)} />
      </aside>
      <section className={`min-w-0 flex-1 flex-col ${activeId ? 'flex' : 'hidden md:flex'}`}>
        {socket === 'offline' && <p role="status" className="bg-amber-50 px-3 py-1 text-center text-xs text-amber-800">Reconnecting… messages you send are still saved.</p>}
        {socket === 'logged_out' && <p role="alert" className="bg-red-50 px-3 py-1 text-center text-xs text-red-700">You have been logged out. Reload the page to log in again.</p>}
        {!activeId && <p className="m-auto p-6 text-center text-sm text-slate-400">Pick a chat on the left, or press + to start one.</p>}
        {activeId && !!openErr && (
          <div className="m-auto p-6 text-center text-sm">
            <p className="text-slate-600">{openErr instanceof ApiFailure && openErr.status === 404 ? 'This chat was not found, or you are not in it.' : 'Could not open this chat.'}</p>
            <button type="button" onClick={() => select(null)} className="btn-ghost mt-3">Back to chats</button>
          </div>
        )}
        {activeId && !openErr && !active && <Loading />}
        {active && (
          <MessagePane
            me={me} chat={active} people={people} messages={messages} hasMore={hasMore}
            loadOlder={loadOlder} onSend={send} onChanged={changed} onBack={() => select(null)}
            onChatChanged={() => { loadChats(); loadDetails(active.id).catch(() => select(null)); }}
          />
        )}
      </section>
      {newChat && (
        <NewChat meId={me.id} onClose={closeNewChat} onDone={newChatDone} />
      )}
    </div>
  );
}

export default function ChatPage() {
  // useSearchParams needs a Suspense boundary (Next 16: otherwise the whole page renders on the client only)
  return (
    <Suspense fallback={<Loading />}>
      <ChatPageInner />
    </Suspense>
  );
}
