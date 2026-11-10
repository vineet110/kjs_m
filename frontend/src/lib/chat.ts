'use client';
// KJS Chat: types (mirror backend/app/services/chat_service.py), the live connection, and the sidebar's
// unread count. Plan and rules: docs/tempV.md, "KJS Chat".
import { useEffect, useRef, useState } from 'react';
import { api } from './api';

export type ChatKind = 'channel' | 'group' | 'dm';
export type ChatPerson = { id: number; name: string; role: 'owner' | 'member' };
export type ChatChannel = {
  id: number; kind: ChatKind; title: string; name: string; description: string; is_private: boolean;
  archived: boolean; my_role: 'owner' | 'member'; muted: boolean; member_count: number;
  dm_user: { id: number; name: string } | null; created_at: string;
  unread?: number; last_message_id?: number; // in the list only
  members?: ChatPerson[]; // in GET /chat/channels/{id} only
};
export type ChatMessage = {
  id: number; channel_id: number; sender_id: number; sender_name: string; body: string; mentions: number[];
  deleted: boolean; edited_at: string | null; created_at: string;
};
export type ChatPage = { messages: ChatMessage[]; has_more: boolean };
export type ChatEvent =
  | { type: 'hello'; user_id: number }
  | { type: 'ping' }
  | { type: 'message.new' | 'message.edited'; channel_id: number; message: ChatMessage }
  | { type: 'message.deleted'; channel_id: number; message_id: number }
  | { type: 'read'; channel_id: number; message_id: number }
  | { type: 'channel.changed'; channel_id: number };

export const BODY_MAX = 4000;

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** THE mention rule, used for showing, sending and editing (one rule, so they can't drift apart: PR #55
 *  review). A message split into plain text and "@Name" parts (still plain text: the page turns the parts
 *  into React elements, never HTML).
 *  1. Longest names first: "@Ram" never matches inside "@Ram Kumar".
 *  2. The name must end there: the next character can't be a letter, digit or mark, so "@Ramesh" is not
 *     "@Ram", and a Hindi vowel sign after a name ("@राम" + "ा") counts as part of the word.
 *  Two people with exactly the same name are both matched (accepted, docs/tempV.md). */
export function mentionParts(body: string, names: string[]): { text: string; mention: boolean }[] {
  const sorted = [...new Set(names)].filter(Boolean).sort((a, b) => b.length - a.length);
  if (!sorted.length) return [{ text: body, mention: false }];
  return body
    .split(new RegExp(`(@(?:${sorted.map(escapeRe).join('|')}))(?![\\p{L}\\p{N}\\p{M}])`, 'gu'))
    .map((text, i) => ({ text, mention: i % 2 === 1 }))
    .filter((p) => p.text !== '');
}

/** Who a message mentions: the people whose "@Name" mentionParts finds in it. */
export function mentionIds(body: string, people: { id: number; name: string }[]): number[] {
  const found = new Set(mentionParts(body, people.map((p) => p.name)).filter((p) => p.mention).map((p) => p.text.slice(1)));
  return people.filter((p) => found.has(p.name)).map((p) => p.id);
}

/** Where the live connection goes.
 *  1. NEXT_PUBLIC_CHAT_WS_URL, when set.
 *  2. Local dev (`next dev`): straight to the API on port 8000. Next's /api forwarding doesn't carry
 *     WebSockets reliably (plan, 10 Nov). The login cookie is for "localhost", so port 8000 gets it too.
 *  3. Otherwise the same site (production: nginx passes /api/v1/chat/ws on to the API). */
export function chatSocketUrl(): string {
  const set = process.env.NEXT_PUBLIC_CHAT_WS_URL;
  if (set) return set;
  const { protocol, hostname, host } = window.location;
  if (process.env.NODE_ENV === 'development') return `ws://${hostname}:8000/api/v1/chat/ws`;
  return `${protocol === 'https:' ? 'wss' : 'ws'}://${host}/api/v1/chat/ws`;
}

const LOGGED_OUT = 4401; // the API's "log in again" close code: don't reconnect

export type SocketState = 'connecting' | 'live' | 'offline' | 'logged_out';

/** One live connection while the chat page is open.
 *  onEvent: every event from the server. onConnect: called EVERY time the connection opens, the first time
 *  too, so the page can fetch what it missed: a message saved while the page was loading, or while the
 *  first attempt was failing, is never pushed (PR #55 review). Drops reconnect after 1, 2, 4… up to 30 s. */
export function useChatSocket(onEvent: (e: ChatEvent) => void, onConnect: () => void): SocketState {
  const [state, setState] = useState<SocketState>('connecting');
  const handlers = useRef({ onEvent, onConnect });
  handlers.current = { onEvent, onConnect }; // always the newest versions, without reconnecting

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let wait = 1000;
    let stopped = false;

    const open = () => {
      setState('connecting');
      ws = new WebSocket(chatSocketUrl());
      ws.onopen = () => {
        setState('live');
        wait = 1000;
        handlers.current.onConnect();
      };
      ws.onmessage = (m) => {
        try {
          handlers.current.onEvent(JSON.parse(m.data) as ChatEvent);
        } catch {} // a broken event is skipped; the next reload shows the truth
      };
      ws.onclose = (c) => {
        if (stopped) return;
        if (c.code === LOGGED_OUT) {
          setState('logged_out');
          return;
        }
        setState('offline');
        timer = setTimeout(open, wait);
        wait = Math.min(wait * 2, 30_000);
      };
    };
    open();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);
  return state;
}

// ---------- The sidebar's unread number ----------
const CHANGED = 'kjs:chat-unread';
/** The chat page calls this after reading, so the sidebar asks again at once. */
export const chatUnreadChanged = () => window.dispatchEvent(new Event(CHANGED));

/** Total unread chat messages (muted chats don't count). Asked on each page change, every minute, and
 *  right after chatUnreadChanged(). Only the newest answer counts. */
export function useChatUnread(pathname: string, enabled = true): number {
  const [n, setN] = useState(0);
  useEffect(() => {
    // Chat switched off for this person (config/modules.ini): don't ask, show no count
    if (!enabled) {
      setN(0);
      return;
    }
    let latest = 0;
    const ask = () => {
      const mine = ++latest;
      api<{ total: number }>('/chat/unread')
        .then((r) => mine === latest && setN(r.total))
        .catch(() => undefined); // no badge is fine
    };
    ask();
    const t = setInterval(ask, 60_000);
    window.addEventListener(CHANGED, ask);
    return () => {
      latest = -1;
      clearInterval(t);
      window.removeEventListener(CHANGED, ask);
    };
  }, [pathname, enabled]);
  return n;
}
