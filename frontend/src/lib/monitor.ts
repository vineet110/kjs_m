'use client';
// Screen sharing and screenshots while checked in (monitoring, Phase B).
//
// Why a plain module and not React state: the admin and employee pages each have their own portal frame, so
// moving between them rebuilds the frame. The screen-share stream must outlive that, so it lives here, once
// per browser tab. A full page reload still ends it (browsers never let a page keep sharing across a reload):
// the portal then shows "Share your screen again", and the server records the gap.
//
// The server decides everything that matters (checked in? on a break? too soon?). This file only captures a
// frame every `screenshot_minutes` and sends it. Later (Phase D) the browser extension can do the capturing
// instead, and survives reloads; the upload route is the same.
import { api, upload, type MonitorState } from './api';

export type ShareStatus = 'off' | 'sharing' | 'stopped' | 'refused' | 'phone' | 'unsupported';

let stream: MediaStream | null = null;
let track: MediaStreamTrack | null = null;
let timer: ReturnType<typeof setInterval> | null = null;
let status: ShareStatus = 'off';
let settings: MonitorState['config'] | null = null;
const listeners = new Set<() => void>();

const emit = () => listeners.forEach((fn) => fn());
export const getStatus = () => status;
/** Tell the monitoring bar to ask the server again (after check-in, check-out or a break). */
export const attendanceChanged = () => window.dispatchEvent(new Event('kjs:attendance-changed'));
export function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
function setStatus(s: ShareStatus) {
  status = s;
  emit();
}

export function isPhone(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator as Navigator & { userAgentData?: { mobile?: boolean } };
  return ua.userAgentData?.mobile ?? /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
}

const canShare = () => typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getDisplayMedia;

/** After a successful check-in (same click): record the device, then ask to share the entire screen. */
export async function onCheckedIn() {
  const phone = isPhone();
  api('/monitor/device', { method: 'POST', body: { device: phone ? 'phone' : 'laptop' } }).catch(() => {});
  if (phone) return setStatus('phone');
  await startSharing();
}

/** After check-out: stop quietly (the server ignores sharing events while checked out anyway). */
export function onCheckedOut() {
  stopQuietly();
  setStatus('off');
}

/** Ask the browser to share. Needs a click (browsers refuse otherwise): call it from a button. */
export async function startSharing(): Promise<void> {
  if (isPhone()) return setStatus('phone');
  if (!canShare()) return setStatus('unsupported');
  if (track?.readyState === 'live') return setStatus('sharing');
  let s: MediaStream;
  try {
    s = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: 'monitor' } as MediaTrackConstraints, audio: false });
  } catch {
    // Cancelled, or "Block". The portal still works; admins are told.
    api('/monitor/share', { method: 'POST', body: { state: 'refused' } }).catch(() => {});
    return setStatus('refused');
  }
  const t = s.getVideoTracks()[0];
  if (t.getSettings().displaySurface && t.getSettings().displaySurface !== 'monitor') {
    // A tab or a window was picked: only the entire screen shows everything
    s.getTracks().forEach((x) => x.stop());
    throw new Error('Please choose "Entire screen", not a tab or a window.');
  }
  stream = s;
  track = t;
  track.onended = () => { // "Stop sharing" in the browser bar, or the screen went away
    cleanup();
    api('/monitor/share', { method: 'POST', body: { state: 'stopped' } }).catch(() => {});
    setStatus('stopped');
  };
  setStatus('sharing');
  await api('/monitor/share', { method: 'POST', body: { state: 'started' } }).catch(() => {});
  schedule();
  setTimeout(() => void capture(), 5000); // a first one soon, then every screenshot_minutes
}

/** Called with each /monitor/state answer: keeps the timer in step with config/monitoring.ini. */
export function applyState(state: MonitorState) {
  const changed = settings?.screenshot_minutes !== state.config.screenshot_minutes;
  settings = state.config;
  if (!state.checked_in && track) onCheckedOut(); // checked out in another tab
  if (changed && track) schedule();
}

function schedule() {
  if (timer) clearInterval(timer);
  const minutes = settings?.screenshot_minutes ?? 15;
  timer = setInterval(() => void capture(), minutes * 60 * 1000);
}

function cleanup() {
  if (timer) clearInterval(timer);
  timer = null;
  stream = null;
  track = null;
}

function stopQuietly() {
  if (track) {
    track.onended = null;
    track.stop();
  }
  cleanup();
}

async function frame(): Promise<HTMLCanvasElement> {
  const c = document.createElement('canvas');
  const draw = (src: CanvasImageSource, w: number, h: number) => {
    const scale = Math.min(1, 1920 / w); // big screens are scaled down: smaller files, text still readable
    c.width = Math.round(w * scale);
    c.height = Math.round(h * scale);
    c.getContext('2d')!.drawImage(src, 0, 0, c.width, c.height);
  };
  type Grabber = { grabFrame(): Promise<ImageBitmap> };
  const IC = (window as unknown as { ImageCapture?: new (t: MediaStreamTrack) => Grabber }).ImageCapture;
  if (IC && track) { // works in a background tab in Chrome and Edge
    const bmp = await new IC(track).grabFrame();
    draw(bmp, bmp.width, bmp.height);
    bmp.close();
    return c;
  }
  const v = document.createElement('video');
  v.muted = true;
  v.srcObject = stream;
  await v.play();
  draw(v, v.videoWidth, v.videoHeight);
  v.srcObject = null;
  return c;
}

const toJpeg = (c: HTMLCanvasElement, q: number) =>
  new Promise<Blob | null>((resolve) => c.toBlob(resolve, 'image/jpeg', q));

async function capture() {
  if (!track || track.readyState !== 'live') return;
  try {
    const c = await frame();
    const maxBytes = (settings?.max_screenshot_kb ?? 600) * 1024;
    let q = (settings?.image_quality ?? 60) / 100;
    let blob = await toJpeg(c, q);
    while (blob && blob.size > maxBytes && q > 0.2) { // too big: lower the quality until it fits
      q -= 0.15;
      blob = await toJpeg(c, q);
    }
    if (!blob) return;
    const form = new FormData();
    form.append('file', blob, 'screen.jpg');
    await upload('/monitor/screenshot', form);
  } catch {
    // On a break, too soon, checked out, or offline: the server said no or couldn't be reached. Next time.
  }
}
