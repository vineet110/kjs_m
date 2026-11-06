'use client';
// Complete Zoho People Attendance Screen:
// List View (Timeline Graphic Bar), Tabular View, Calendar View, Overtime View, Regularization, Reports, Shifts.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { addDays, fmtDay, Msg, Pill, todayIST } from '@/components/portal/ui';
import { api, ApiFailure, type Holiday, type LeaveRequest, type MonthView, type Regularization, type Shift, type Today, type Week } from '@/lib/api';
import Loading from '@/components/ui/Loading';

type ActiveNav = 'list' | 'tabular' | 'calendar' | 'overtime' | 'leaves' | 'regularization' | 'reports' | 'shifts';

function getMondayIST(isoDate?: string) {
  const base = isoDate || todayIST();
  const [y, m, d] = base.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const dayOfWeek = dt.getUTCDay(); // 0 is Sun, 1 is Mon...
  const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  return addDays(base, diffToMonday);
}

export default function AttendancePage() {
  const [activeNav, setActiveNav] = useState<ActiveNav>('list');
  const [todayData, setTodayData] = useState<Today | null>(null);
  const [liveClock, setLiveClock] = useState('');
  const [notes, setNotes] = useState('');
  const [breakStatus, setBreakStatus] = useState<string | null>(null);
  const [breakTimer, setBreakTimer] = useState(0);
  const [showBreakMenu, setShowBreakMenu] = useState(false);

  // Date range navigation (Week / Month) - Always aligned to Monday in IST
  const [weekStart, setWeekStart] = useState(() => getMondayIST());

  const [curMonth, setCurMonth] = useState(() => {
    const d = new Date();
    return { year: d.getFullYear(), month: d.getMonth() + 1 };
  });

  // Data states
  const [weekData, setWeekData] = useState<Week | null>(null);
  const [monthData, setMonthData] = useState<MonthView | null>(null);
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [regs, setRegs] = useState<Regularization[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);

  // Modals
  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [showRegModal, setShowRegModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Live second-by-second clock in IST
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setLiveClock(
        now.toLocaleTimeString('en-US', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }).toLowerCase()
      );
    };
    updateClock();
    const t = setInterval(updateClock, 1000);
    return () => clearInterval(t);
  }, []);

  // Break timer
  useEffect(() => {
    if (!breakStatus) return;
    const t = setInterval(() => setBreakTimer((c) => c + 1), 1000);
    return () => clearInterval(t);
  }, [breakStatus]);

  const loadToday = useCallback(() => {
    api<Today>('/attendance/today').then(setTodayData).catch(() => {});
  }, []);

  const loadWorkspace = useCallback(() => {
    loadToday();
    api<Week>(`/attendance/week?start=${weekStart}`).then(setWeekData).catch(() => {});
    api<MonthView>(`/attendance/month?year=${curMonth.year}&month=${curMonth.month}`).then(setMonthData).catch(() => {});
    api<LeaveRequest[]>('/attendance/leaves').then(setLeaves).catch(() => {});
    api<Regularization[]>('/attendance/regularizations').then(setRegs).catch(() => {});
    api<Shift[]>('/attendance/shifts').then(setShifts).catch(() => {});
    api<Holiday[]>('/attendance/holidays').then(setHolidays).catch(() => {});
  }, [weekStart, curMonth, loadToday]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const isCheckedIn = Boolean(todayData?.is_checked_in ?? (todayData?.check_in && !todayData?.check_out));
  const isOnLeave = todayData?.status === 'leave';

  // Punch in / out - Employees can check-in and check-out multiple times throughout their shift
  async function handlePunch() {
    if (!todayData || isOnLeave) return;
    setBusy(true);
    setMsg(null);
    try {
      if (!isCheckedIn) {
        await api('/attendance/check-in', { method: 'POST' });
        setMsg({ ok: true, text: todayData.check_in ? 'Checked in again successfully!' : 'Checked in successfully!' });
      } else {
        await api('/attendance/check-out', { method: 'POST', body: { notes: notes.trim() || null } });
        setMsg({ ok: true, text: 'Checked out successfully!' });
        setNotes('');
        setBreakStatus(null);
      }
      loadWorkspace();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof ApiFailure ? e.message : 'Punch action failed.' });
    } finally {
      setBusy(false);
    }
  }

  // Week range string: "05-Jan-2026 - 11-Jan-2026"
  const weekRangeStr = useMemo(() => {
    const [y, m, d] = weekStart.split('-').map(Number);
    const sDate = new Date(Date.UTC(y, m - 1, d));
    const eDate = new Date(Date.UTC(y, m - 1, d + 6));
    const fmt = (dt: Date) =>
      `${String(dt.getUTCDate()).padStart(2, '0')}-${dt.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}-${dt.getUTCFullYear()}`;
    return `${fmt(sDate)} - ${fmt(eDate)}`;
  }, [weekStart]);

  function shiftWeek(days: number) {
    setWeekStart((cur) => addDays(cur, days));
  }

  // Live elapsed time for today if checked in: updates every second (e.g. "00:45:20 Hrs")
  const todayLiveElapsed = useMemo(() => {
    if (!isCheckedIn || !todayData) return null;
    let latestIn = todayData.check_in;
    if (todayData.punches && todayData.punches.length > 0) {
      const ins = todayData.punches.filter((p) => p.type === 'in');
      if (ins.length > 0) latestIn = ins[ins.length - 1].time;
    }
    if (!latestIn) return null;

    const parts = latestIn.split(':');
    const inH = Number(parts[0]) || 0;
    const inM = Number(parts[1]) || 0;
    const now = new Date();
    const istParts = now
      .toLocaleTimeString('en-US', { timeZone: 'Asia/Kolkata', hour12: false })
      .split(':');
    const curH = Number(istParts[0]) || 0;
    const curM = Number(istParts[1]) || 0;
    const curS = Number(istParts[2]) || 0;

    const totalCheckInSec = inH * 3600 + inM * 60;
    const totalCurSec = curH * 3600 + curM * 60 + curS;
    const activeSec = Math.max(0, totalCurSec - totalCheckInSec);

    // Sum completed punches if multiple sessions exist
    let priorSec = 0;
    if (todayData.punches && todayData.punches.length > 1) {
      let tempIn: number | null = null;
      for (const p of todayData.punches) {
        const [pH, pM] = p.time.split(':').map(Number);
        const pSec = (pH || 0) * 3600 + (pM || 0) * 60;
        if (p.type === 'in') {
          tempIn = pSec;
        } else if (p.type === 'out' && tempIn !== null) {
          priorSec += Math.max(0, pSec - tempIn);
          tempIn = null;
        }
      }
    }

    const totalSec = priorSec + activeSec;
    const elapsedH = Math.floor(totalSec / 3600);
    const elapsedM = Math.floor((totalSec % 3600) / 60);
    const elapsedS = totalSec % 60;
    return `${String(elapsedH).padStart(2, '0')}:${String(elapsedM).padStart(2, '0')}:${String(elapsedS).padStart(2, '0')} Hrs`;
  }, [isCheckedIn, todayData, liveClock]);

  async function handleApplyLeave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMsg(null);
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/attendance/leaves', {
        method: 'POST',
        body: {
          leave_type: f.leave_type,
          start_date: f.start_date,
          end_date: f.end_date,
          reason: f.reason,
          is_half_day: f.is_half_day === 'on',
          half_day_session: f.half_day_session || null,
        },
      });
      setMsg({ ok: true, text: 'Leave application submitted!' });
      setShowLeaveModal(false);
      loadWorkspace();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not submit leave.' });
    }
  }

  async function handleRegularize(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMsg(null);
    const form = e.currentTarget;
    const f = Object.fromEntries(new FormData(form)) as Record<string, string>;
    try {
      await api('/attendance/regularizations', {
        method: 'POST',
        body: { day: f.day, check_in: f.check_in, check_out: f.check_out || null, reason: f.reason },
      });
      setMsg({ ok: true, text: 'Missed punch request submitted!' });
      setShowRegModal(false);
      loadWorkspace();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiFailure ? err.message : 'Could not send request.' });
    }
  }


  return (
    <div className="flex h-full w-full bg-white select-none overflow-hidden">
      {/* 1. Left Zoho Sidebar (#1E2238) - Flush to Top and Bottom */}
      <aside className="w-56 shrink-0 bg-[#1E2238] text-slate-300 flex flex-col justify-between py-4 px-3 select-none h-full border-r border-[#151828]">
        <div className="space-y-5">
          {/* Views Group matching reference */}
          <div>
            <p className="px-3 py-1 text-sm font-semibold text-slate-200">Views</p>
            <div className="mt-1 space-y-0.5">
              {[
                { id: 'list', label: 'List View' },
                { id: 'tabular', label: 'Tabular View' },
                { id: 'calendar', label: 'Calendar View' },
                { id: 'overtime', label: 'Overtime View' },
              ].map((v) => (
                <button
                  key={v.id}
                  onClick={() => setActiveNav(v.id as ActiveNav)}
                  className={`w-full text-left px-3 py-2 rounded text-xs font-medium transition-colors ${
                    activeNav === v.id
                      ? 'bg-[#272D4D] text-[#4E89F8] font-semibold'
                      : 'text-slate-300 hover:bg-[#252A47] hover:text-white'
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>

          {/* Secondary Sections */}
          <div className="space-y-0.5 pt-2 border-t border-slate-700/30">
            {[
              { id: 'leaves', label: 'Leave Applications', badge: leaves.filter((l) => l.status === 'pending').length },
              { id: 'regularization', label: 'Regularization', badge: regs.filter((r) => r.status === 'pending').length },
              { id: 'reports', label: 'Reports' },
              { id: 'shifts', label: 'Shift Schedule' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setActiveNav(m.id as ActiveNav)}
                className={`w-full flex items-center justify-between text-left px-3 py-2 rounded text-xs font-medium transition-colors ${
                  activeNav === m.id
                    ? 'bg-[#272D4D] text-[#4E89F8] font-semibold'
                    : 'text-slate-300 hover:bg-[#252A47] hover:text-white'
                }`}
              >
                <span>{m.label}</span>
                {Boolean(m.badge) && (
                  <span className="rounded-full bg-amber-500 px-1.5 py-0.2 text-[10px] text-white font-bold">
                    {m.badge}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Clean Bottom Action */}
        <div className="pt-3 border-t border-slate-700/40">
          <button
            onClick={() => setShowLeaveModal(true)}
            className="w-full rounded bg-[#272D4D] hover:bg-[#343D68] text-white py-2 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
          >
            <span>+ Apply Leave</span>
          </button>
        </div>
      </aside>

      {/* 2. Main Workspace - Edge to Edge */}
      <main className="flex-1 flex flex-col h-full bg-white overflow-hidden">
        {/* Top Bar with Centered Date Range Navigator & View Quick Icons */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-2.5 bg-white shrink-0">
          <div className="w-24"></div>

          {/* Centered Date Range Navigator matching reference */}
          <div className="flex items-center rounded border border-slate-300 bg-white text-xs font-semibold text-slate-700 shadow-2xs">
            <button
              onClick={() => (activeNav === 'calendar' ? setCurMonth((c) => ({ ...c, month: Math.max(1, c.month - 1) })) : shiftWeek(-7))}
              className="px-3 py-1.5 hover:bg-slate-50 text-slate-600 transition-colors"
              title="Previous"
            >
              ❮
            </button>
            <div className="px-5 py-1.5 min-w-[14rem] text-center border-x border-slate-200 font-medium text-slate-800">
              {activeNav === 'calendar'
                ? monthData ? `${monthData.month_name} ${monthData.year}` : '…'
                : weekRangeStr}
            </div>
            <button
              onClick={() => (activeNav === 'calendar' ? setCurMonth((c) => ({ ...c, month: Math.min(12, c.month + 1) })) : shiftWeek(7))}
              className="px-3 py-1.5 hover:bg-slate-50 text-slate-600 transition-colors"
              title="Next"
            >
              ❯
            </button>
          </div>

          {/* Right View Quick Icons matching reference */}
          <div className="flex items-center gap-1 text-slate-500">
            <div className="flex items-center rounded border border-slate-300 overflow-hidden shadow-2xs">
              <button
                onClick={() => setActiveNav('list')}
                className={`px-2.5 py-1.5 text-xs transition-colors ${activeNav === 'list' ? 'bg-slate-200 text-slate-900 font-bold' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                title="List View"
              >
                ▦
              </button>
              <button
                onClick={() => setActiveNav('calendar')}
                className={`px-2.5 py-1.5 text-xs border-l border-slate-300 transition-colors ${activeNav === 'calendar' ? 'bg-slate-200 text-slate-900 font-bold' : 'bg-white text-slate-600 hover:bg-slate-50'}`}
                title="Calendar View"
              >
                📅
              </button>
            </div>
            <button
              onClick={() => setActiveNav('tabular')}
              className="px-2.5 py-1.5 rounded border border-slate-300 bg-white text-xs text-slate-600 hover:bg-slate-50 shadow-2xs font-bold"
              title="More Views / Tabular"
            >
              •••
            </button>
          </div>
        </div>

        {/* Action Strip (Notes, Shift Badge, Break, Big Punch Button with Live Clock) */}
        <div className="flex items-center gap-3.5 border-b border-slate-200 px-6 py-2.5 bg-white shrink-0">
          {/* Notes Input */}
          <div className="flex-1 max-w-sm">
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add notes for check-out"
              disabled={!isCheckedIn}
              className="w-full rounded border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-700 placeholder:text-slate-400 focus:border-slate-300 focus:outline-none"
            />
          </div>

          {/* Shift Box with Coral Border matching reference */}
          <div className="rounded border border-[#E06D53] bg-white px-5 py-1 text-center shadow-2xs min-w-[7.5rem]">
            <p className="text-xs font-semibold text-slate-800 leading-tight">
              {todayData?.shift_name?.replace(' Shift', '') || 'General'}
            </p>
            <p className="text-[10px] text-slate-500 font-mono leading-tight mt-0.5">
              [ {todayData?.shift ? todayData.shift.replace('–', ' - ') : '09:30 - 18:30'} ]
            </p>
          </div>

          {/* Break Dropdown matching reference */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowBreakMenu(!showBreakMenu)}
              className={`flex items-center gap-1.5 rounded border px-3.5 py-1.5 text-xs font-medium shadow-2xs transition-colors ${
                breakStatus
                  ? 'bg-amber-50 border-amber-300 text-amber-800'
                  : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              <span className="text-sm">⏱</span>
              <span>
                {breakStatus
                  ? `${breakStatus} (${Math.floor(breakTimer / 60)}:${String(breakTimer % 60).padStart(2, '0')})`
                  : 'Break'}
              </span>
              <span className="text-[9px] text-slate-400 ml-0.5">▼</span>
            </button>

            {showBreakMenu && (
              <div className="absolute right-0 mt-1 w-44 rounded border border-slate-200 bg-white py-1 shadow-lg z-20 text-xs">
                {breakStatus ? (
                  <button
                    onClick={() => {
                      setBreakStatus(null);
                      setBreakTimer(0);
                      setShowBreakMenu(false);
                    }}
                    className="w-full text-left px-3 py-1.5 text-rose-600 font-semibold hover:bg-rose-50"
                  >
                    ⏹ End Break
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        setBreakStatus('Tea Break');
                        setBreakTimer(0);
                        setShowBreakMenu(false);
                      }}
                      className="w-full text-left px-3 py-1.5 text-slate-700 hover:bg-slate-100"
                    >
                      ☕ Tea Break (15m)
                    </button>
                    <button
                      onClick={() => {
                        setBreakStatus('Lunch Break');
                        setBreakTimer(0);
                        setShowBreakMenu(false);
                      }}
                      className="w-full text-left px-3 py-1.5 text-slate-700 hover:bg-slate-100"
                    >
                      🍱 Lunch Break (45m)
                    </button>
                    <button
                      onClick={() => {
                        setBreakStatus('Break');
                        setBreakTimer(0);
                        setShowBreakMenu(false);
                      }}
                      className="w-full text-left px-3 py-1.5 text-slate-700 hover:bg-slate-100"
                    >
                      ⏸ Personal Break
                    </button>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Prominent Punch Button with Live Clock matching reference */}
          {isOnLeave ? (
            <div
              className="min-w-[10.5rem] flex items-center justify-center gap-2.5 rounded px-4 py-2 bg-sky-50 border border-sky-300 text-sky-800 shadow-2xs select-none"
              title="You are on approved leave today"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-100 border border-sky-300 text-sm">
                🏖️
              </span>
              <div className="text-left">
                <p className="text-xs font-bold leading-none">On Leave</p>
                <p className="text-[10px] text-sky-600 leading-tight mt-0.5">Approved</p>
              </div>
            </div>
          ) : (
            <button
              onClick={handlePunch}
              disabled={busy}
              className={`min-w-[10.5rem] flex items-center justify-center gap-2.5 rounded px-4 py-1.5 text-white shadow-2xs transition-all ${
                isCheckedIn
                  ? 'bg-[#E05A47] hover:bg-[#D4473E]' // Coral / Red for Check-out
                  : 'bg-[#27A862] hover:bg-[#218838]' // Emerald Green for Check-in
              }`}
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-white/80 text-sm">
                ⏱
              </span>
              <div className="text-left">
                <p className="text-xs font-bold leading-none">
                  {isCheckedIn ? 'Check-out' : todayData?.check_in ? 'Check-in again' : 'Check-in'}
                </p>
                <p className="text-[10px] font-mono opacity-90 leading-tight mt-0.5">
                  {liveClock || '12:00:00 pm'}
                </p>
              </div>
            </button>
          )}
        </div>

        {msg && <div className="px-6 pt-2 shrink-0"><Msg msg={msg} /></div>}

        {/* 3. Main Views Scrollable Area */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* VIEW 1: LIST VIEW (Pixel faithful to reference image) */}
          {activeNav === 'list' && (
            <div className="w-full space-y-1">
              {/* Table Column Headers */}
              <div className="flex items-center justify-between text-xs font-semibold text-slate-700 pb-2.5 border-b border-slate-200 px-2">
                <div className="w-20"></div>
                <div className="w-20 text-center">Check-in</div>
                <div className="relative flex-1">
                  <div className="absolute left-1/2 -translate-x-1/2 top-0 bottom-0 w-px" />
                </div>
                <div className="w-20 text-center">Check-out</div>
                <div className="w-24 text-right">Total Hours</div>
              </div>

              {/* Rows */}
              {!weekData ? (
                <div className="py-12"><Loading /></div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {weekData.days.map((d) => {
                    const [y, m, dayNum] = d.day.split('-').map(Number);
                    const dt = new Date(Date.UTC(y, m - 1, dayNum));
                    const dayName = dt.toLocaleString('en-US', { weekday: 'short', timeZone: 'UTC' });
                    const isToday = d.day === todayIST();
                    const label = isToday ? `Today,${String(dayNum).padStart(2, '0')}` : `${dayName},${String(dayNum).padStart(2, '0')}`;
                    const isSunday = dt.getUTCDay() === 0;

                    return (
                      <div
                        key={d.day}
                        className={`flex items-center justify-between py-4 px-2 hover:bg-slate-50/60 transition-colors ${
                          isToday ? 'bg-amber-50/25' : ''
                        }`}
                      >
                        {/* Day label */}
                        <div className="w-20 text-xs font-medium text-slate-800">
                          <span className={isToday ? 'font-bold text-slate-900' : ''}>{label}</span>
                        </div>

                        {/* Check-in time */}
                        <div className="w-20 text-center text-xs font-mono text-slate-600">
                          {d.check_in ? format12h(d.check_in) : '--'}
                        </div>

                        {/* Start markers (Two gray dots) */}
                        <div className="flex items-center gap-1 px-2 text-slate-300">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                        </div>

                        {/* Middle Timeline Graphic Bar with center line */}
                        <div className="relative flex-1 h-7 flex items-center px-1">
                          {/* Center 12:00 PM vertical guide */}
                          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-100" />

                          {isSunday ? (
                            <div className="w-full relative flex items-center justify-center">
                              <div className="w-full h-[1.5px] bg-[#ECC94B]" />
                              <span className="absolute rounded border border-[#ECC94B] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#B7791F]">
                                Weekend
                              </span>
                            </div>
                          ) : d.state === 'leave' ? (
                            <div className="w-full relative flex items-center justify-center">
                              <div className="w-full h-[1.5px] bg-sky-300" />
                              <span className="absolute rounded border border-sky-300 bg-white px-2.5 py-0.5 text-[10px] font-medium text-sky-800">
                                Leave
                              </span>
                            </div>
                          ) : d.state === 'holiday' ? (
                            <div className="w-full relative flex items-center justify-center">
                              <div className="w-full h-[1.5px] bg-violet-300" />
                              <span className="absolute rounded border border-violet-300 bg-white px-2.5 py-0.5 text-[10px] font-medium text-violet-800">
                                Holiday
                              </span>
                            </div>
                          ) : d.state === 'not_joined' ? (
                            <div className="w-full relative flex items-center justify-center">
                              <div className="w-full h-[1.5px] bg-slate-200" />
                              <span className="absolute rounded border border-slate-300 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-400">
                                Not Joined
                              </span>
                            </div>
                          ) : d.check_in ? (
                            <div className="w-full relative flex items-center">
                              {/* Background subtle line */}
                              <div className="w-full h-[1.5px] bg-slate-200" />
                              {/* Active/Worked timeline segment */}
                              <TimelineBar checkIn={d.check_in} checkOut={d.check_out} isToday={isToday} punches={d.punches} />
                            </div>
                          ) : (
                            <div className="w-full h-[1.5px] bg-slate-100" />
                          )}
                        </div>

                        {/* End markers (Two gray dots) */}
                        <div className="flex items-center gap-1 px-2 text-slate-300">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                        </div>

                        {/* Check-out time */}
                        <div className="w-20 text-center text-xs font-mono text-slate-600">
                          {d.check_out ? format12h(d.check_out) : '--'}
                        </div>

                        {/* Total hours (with live ticking seconds for Today while clocked in!) */}
                        <div className="w-24 text-right text-xs font-mono font-bold text-slate-900">
                          {isToday && isCheckedIn
                            ? todayLiveElapsed || '00:00:00 Hrs'
                            : d.hours > 0
                            ? `${formatHoursHM(d.hours)} Hrs`
                            : '00:00 Hrs'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* VIEW 2: TABULAR VIEW */}
          {activeNav === 'tabular' && weekData && (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-600 border-b">
                  <tr>
                    <th className="p-3">Date</th>
                    <th className="p-3">Day</th>
                    <th className="p-3">Shift</th>
                    <th className="p-3">Check-in</th>
                    <th className="p-3">Check-out</th>
                    <th className="p-3">Total Hours</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {weekData.days.map((d) => (
                    <tr key={d.day} className="hover:bg-slate-50/50">
                      <td className="p-3 font-mono text-xs">{d.day}</td>
                      <td className="p-3 font-medium">{fmtDay(d.day)}</td>
                      <td className="p-3 text-xs text-slate-500">{todayData?.shift_name || 'General'}</td>
                      <td className="p-3 font-mono text-xs">{d.check_in ? format12h(d.check_in) : '—'}</td>
                      <td className="p-3 font-mono text-xs">{d.check_out ? format12h(d.check_out) : '—'}</td>
                      <td className="p-3 font-mono font-semibold text-xs">{d.hours > 0 ? `${formatHoursHM(d.hours)} Hrs` : '—'}</td>
                      <td className="p-3"><Pill value={d.state} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* VIEW 3: CALENDAR VIEW */}
          {activeNav === 'calendar' && monthData && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-slate-500">Working Days</p>
                  <p className="text-xl font-bold">{monthData.working_days}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-emerald-600">Present</p>
                  <p className="text-xl font-bold text-emerald-700">{monthData.summary.present ?? 0}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-sky-600">Leaves</p>
                  <p className="text-xl font-bold text-sky-700">{monthData.summary.leave ?? 0}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-rose-600">Absent</p>
                  <p className="text-xl font-bold text-rose-700">{monthData.summary.absent ?? 0}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-slate-500">Total Hours</p>
                  <p className="text-xl font-bold">{monthData.total_hours} h</p>
                </div>
              </div>

              <div className="card overflow-hidden">
                <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50 text-center text-xs font-bold uppercase text-slate-600">
                  {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d, i) => (
                    <div key={d} className={`py-2.5 ${i === 6 ? 'text-slate-400 bg-slate-100/50' : ''}`}>{d}</div>
                  ))}
                </div>
                <div className="grid grid-cols-7 divide-x divide-y divide-slate-100 bg-slate-200/40">
                  {Array.from({ length: monthData.days[0]?.weekday ?? 0 }).map((_, i) => (
                    <div key={`empty-${i}`} className="min-h-[5.5rem] bg-slate-50/60 p-2" />
                  ))}
                  {monthData.days.map((d) => {
                    const isSun = d.weekday === 6;
                    const isToday = d.day === todayIST();
                    return (
                      <div
                        key={d.day}
                        className={`min-h-[5.8rem] p-2 flex flex-col justify-between ${
                          isToday ? 'bg-amber-50/60 ring-2 ring-inset ring-amber-400' : isSun ? 'bg-slate-50/70' : 'bg-white'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-bold ${isToday ? 'rounded-full bg-amber-500 px-1.5 py-0.5 text-white' : 'text-slate-700'}`}>
                            {d.day_num}
                          </span>
                          {d.state !== 'upcoming' && d.state !== 'off' && <Pill value={d.state} />}
                          {d.state === 'off' && <span className="text-[10px] text-slate-400">Off</span>}
                        </div>
                        <div className="text-[11px] my-1">
                          {d.check_in ? (
                            <>
                              <p className="font-mono text-slate-700 font-medium">{d.check_in}–{d.check_out || '…'}</p>
                              {d.hours > 0 && <p className="font-semibold text-emerald-700 font-mono">{d.hours} hrs</p>}
                            </>
                          ) : d.state === 'leave' ? (
                            <span className="text-sky-700 font-medium">Leave</span>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* VIEW 4: OVERTIME VIEW */}
          {activeNav === 'overtime' && weekData && (
            <div className="space-y-4">
              <div className="rounded-lg bg-slate-50 p-4 border border-slate-200 text-xs text-slate-600">
                <p className="font-semibold text-slate-800">💡 Standard Shift Duration: 9.0 Hours</p>
                <p>Hours worked beyond 9.0 hours on working days are automatically accounted for as Overtime (OT).</p>
              </div>

              <div className="card overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-600 border-b">
                    <tr>
                      <th className="p-3">Date</th>
                      <th className="p-3">Day</th>
                      <th className="p-3">Actual Hours</th>
                      <th className="p-3">Standard Shift</th>
                      <th className="p-3">Overtime Hours</th>
                      <th className="p-3">OT Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {weekData.days.map((d) => {
                      const ot = d.hours > 9.0 ? round2(d.hours - 9.0) : 0;
                      return (
                        <tr key={d.day} className="hover:bg-slate-50/50">
                          <td className="p-3 font-mono text-xs">{d.day}</td>
                          <td className="p-3 font-medium">{fmtDay(d.day)}</td>
                          <td className="p-3 font-mono font-semibold text-xs">{d.hours > 0 ? `${d.hours} h` : '—'}</td>
                          <td className="p-3 font-mono text-xs text-slate-500">9.0 h</td>
                          <td className="p-3 font-mono font-bold text-xs text-emerald-700">{ot > 0 ? `+${ot} h` : '—'}</td>
                          <td className="p-3">
                            {ot > 0 ? (
                              <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                                Overtime
                              </span>
                            ) : (
                              <span className="text-xs text-slate-400">Regular</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* VIEW: LEAVE APPLICATIONS & APPROVAL STATUS */}
          {activeNav === 'leaves' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">My Leave Applications</h3>
                  <p className="text-xs text-slate-500">Track whether your submitted leaves are approved, pending, or rejected.</p>
                </div>
                <button onClick={() => setShowLeaveModal(true)} className="btn-dark py-1.5 text-xs font-semibold">
                  + Apply Leave
                </button>
              </div>

              {/* Status summary */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-slate-500">Total Applied</p>
                  <p className="text-xl font-bold text-slate-800">{leaves.length}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-amber-600">Pending Approval</p>
                  <p className="text-xl font-bold text-amber-700">{leaves.filter((l) => l.status === 'pending').length}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-emerald-600">Approved</p>
                  <p className="text-xl font-bold text-emerald-700">{leaves.filter((l) => l.status === 'approved').length}</p>
                </div>
                <div className="card p-3">
                  <p className="text-[11px] font-semibold uppercase text-rose-600">Rejected</p>
                  <p className="text-xl font-bold text-rose-700">{leaves.filter((l) => l.status === 'rejected').length}</p>
                </div>
              </div>

              {/* Leave Requests List */}
              <div className="card divide-y">
                {leaves.length === 0 && <p className="p-4 text-sm text-slate-500">No leave applications submitted yet.</p>}
                {leaves.map((l) => (
                  <div key={l.id} className="p-4 text-sm hover:bg-slate-50/50 transition-colors">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 capitalize">{l.leave_type} Leave</span>
                          <span className="text-xs text-slate-500">
                            ({l.working_days} working {l.working_days === 1 ? 'day' : 'days'})
                            {l.is_half_day && ` · Half Day (${l.half_day_session || 'first'})`}
                          </span>
                        </div>
                        <p className="text-xs font-mono text-slate-600">
                          {l.start_date} {l.start_date !== l.end_date ? `to ${l.end_date}` : ''}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <Pill value={l.status} />
                      </div>
                    </div>

                    <div className="mt-2 text-xs text-slate-600">
                      <span className="text-slate-400 font-medium">Reason: </span>
                      <span>“{l.reason}”</span>
                    </div>

                    {l.status === 'rejected' && l.rejection_reason && (
                      <div className="mt-2 rounded bg-rose-50 border border-rose-200 p-2 text-xs text-rose-700">
                        <span className="font-semibold">Admin Rejection Note: </span>
                        <span>{l.rejection_reason}</span>
                      </div>
                    )}

                    {l.status === 'approved' && (
                      <div className="mt-1 text-[11px] text-emerald-700 font-medium">
                        ✓ Approved by Admin
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VIEW 5: REGULARIZATION */}
          {activeNav === 'regularization' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Missed Punch Regularization</h3>
                  <p className="text-xs text-slate-500">Submit requests to fix forgotten check-in or check-out times.</p>
                </div>
                <button onClick={() => setShowRegModal(true)} className="btn-dark py-1.5 text-xs font-semibold">
                  + New Request
                </button>
              </div>

              <div className="card divide-y">
                {regs.length === 0 && <p className="p-4 text-sm text-slate-500">No punch requests submitted.</p>}
                {regs.map((r) => (
                  <div key={r.id} className="flex flex-wrap items-center gap-3 p-4 text-sm">
                    <div>
                      <span className="font-semibold text-slate-800">{fmtDay(r.day)}</span>
                      <p className="text-xs font-mono text-slate-500">{r.check_in} to {r.check_out || '—'}</p>
                    </div>
                    <span className="text-xs text-slate-600 max-w-sm truncate ml-2">“{r.reason}”</span>
                    <span className="ml-auto"><Pill value={r.status} /></span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VIEW 6: REPORTS */}
          {activeNav === 'reports' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">My Attendance Reports</h3>
                <p className="text-xs text-slate-500">Summary metrics and monthly totals.</p>
              </div>

              {monthData && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="card p-4">
                    <p className="text-xs text-slate-500 uppercase font-semibold">This Month Working Days</p>
                    <p className="text-2xl font-bold mt-1">{monthData.working_days} Days</p>
                  </div>
                  <div className="card p-4">
                    <p className="text-xs text-slate-500 uppercase font-semibold">Present Days</p>
                    <p className="text-2xl font-bold text-emerald-700 mt-1">{monthData.summary.present ?? 0} Days</p>
                  </div>
                  <div className="card p-4">
                    <p className="text-xs text-slate-500 uppercase font-semibold">Leaves Taken</p>
                    <p className="text-2xl font-bold text-sky-700 mt-1">{monthData.summary.leave ?? 0} Days</p>
                  </div>
                  <div className="card p-4">
                    <p className="text-xs text-slate-500 uppercase font-semibold">Total Logged Time</p>
                    <p className="text-2xl font-bold text-slate-800 mt-1">{monthData.total_hours} Hours</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* VIEW 7: SHIFT SCHEDULE */}
          {activeNav === 'shifts' && (
            <div className="space-y-4">
              <h3 className="text-base font-bold text-slate-900">Company Shifts</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {shifts.map((s) => (
                  <div key={s.id} className="card p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800">{s.name} ({s.code})</span>
                      {s.is_night_shift && <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700 font-semibold">Night Shift</span>}
                    </div>
                    <p className="text-sm font-mono text-slate-600">
                      Timings: <b>{s.start_time}</b> to <b>{s.end_time}</b>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Apply Leave Modal */}
      {showLeaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="card w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-2">
              <h3 className="text-lg font-bold text-slate-900">Apply for Leave</h3>
              <button onClick={() => setShowLeaveModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={handleApplyLeave} className="space-y-4 text-sm">
              <div>
                <label className="label">Leave Type</label>
                <select name="leave_type" required className="input">
                  <option value="casual">Casual Leave</option>
                  <option value="sick">Sick Leave</option>
                  <option value="earned">Earned Leave</option>
                  <option value="unpaid">Unpaid Leave</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Start Date</label>
                  <input type="date" name="start_date" required className="input" />
                </div>
                <div>
                  <label className="label">End Date</label>
                  <input type="date" name="end_date" required className="input" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-slate-700">
                <input type="checkbox" name="is_half_day" className="h-4 w-4 rounded border-slate-300" />
                Half Day Leave
              </label>
              <div>
                <label className="label">Reason</label>
                <textarea
                  name="reason"
                  required
                  rows={3}
                  minLength={3}
                  maxLength={500}
                  className="input"
                  placeholder="Reason for leave application..."
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t">
                <button type="button" onClick={() => setShowLeaveModal(false)} className="btn-ghost py-1.5">Cancel</button>
                <button type="submit" className="btn-dark py-1.5">Submit Application</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Missed Punch Modal */}
      {showRegModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="card w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-2">
              <h3 className="text-lg font-bold text-slate-900">Missed a Punch?</h3>
              <button onClick={() => setShowRegModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <form onSubmit={handleRegularize} className="space-y-4 text-sm">
              <div>
                <label className="label">Day</label>
                <input type="date" name="day" required max={todayIST()} className="input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Check In Time</label>
                  <input type="time" name="check_in" required className="input" />
                </div>
                <div>
                  <label className="label">Check Out Time (Optional)</label>
                  <input type="time" name="check_out" className="input" />
                </div>
              </div>
              <div>
                <label className="label">Reason</label>
                <input
                  name="reason"
                  required
                  minLength={3}
                  maxLength={500}
                  className="input"
                  placeholder="Forgot to punch, had client meeting..."
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t">
                <button type="button" onClick={() => setShowRegModal(false)} className="btn-ghost py-1.5">Cancel</button>
                <button type="submit" className="btn-dark py-1.5">Send Fix Request</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/** Formats 24h "09:00" to "09:00 AM" */
function format12h(timeStr: string) {
  const [hStr, mStr] = timeStr.split(':');
  let h = parseInt(hStr, 10);
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return `${String(h).padStart(2, '0')}:${mStr} ${ampm}`;
}

/** Formats float hours 6.5 -> "06:30" */
function formatHoursHM(h: number) {
  const totalMin = Math.round(h * 60);
  const hrs = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
}

function round2(n: number) {
  return Math.round(n * 100) / 100;
}

/** The Timeline Graphic Bar matching the reference with start dot, green bar, and coral end dot */
function TimelineBar({
  checkIn,
  checkOut,
  isToday,
  punches,
}: {
  checkIn: string;
  checkOut: string | null;
  isToday: boolean;
  punches?: Array<{ type: string; time: string }>;
}) {
  const toPct = (t: string) => {
    const parts = t.split(':');
    const h = Number(parts[0]) || 0;
    const m = Number(parts[1]) || 0;
    // Base 08:00 to 20:00 (12 hours workday span)
    const hoursFrom8 = h + m / 60 - 8;
    return Math.min(96, Math.max(4, (hoursFrom8 / 12) * 92 + 4));
  };

  // Build sessions from punches if available
  const sessions: Array<{ inTime: string; outTime: string | null; isInProgress: boolean }> = [];
  if (punches && punches.length > 0) {
    let curIn: string | null = null;
    for (const p of punches) {
      if (p.type === 'in') {
        curIn = p.time;
      } else if (p.type === 'out' && curIn) {
        sessions.push({ inTime: curIn, outTime: p.time, isInProgress: false });
        curIn = null;
      }
    }
    if (curIn) {
      sessions.push({ inTime: curIn, outTime: null, isInProgress: isToday });
    }
  }

  if (sessions.length === 0) {
    sessions.push({ inTime: checkIn, outTime: checkOut, isInProgress: !checkOut && isToday });
  }

  const nowIstStr = isToday
    ? new Date().toLocaleTimeString('en-US', {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <>
      {sessions.map((s, idx) => {
        const left = toPct(s.inTime);
        let right = left + 8;
        if (s.outTime) {
          right = toPct(s.outTime);
        } else if (s.isInProgress && nowIstStr) {
          right = Math.max(left + 6, toPct(nowIstStr));
        }
        const width = Math.max(3, right - left);

        return (
          <div
            key={idx}
            className="absolute h-[2px] bg-[#9FD8A3] flex items-center justify-between pointer-events-none"
            style={{ left: `${left}%`, width: `${width}%` }}
          >
            {/* Green start dot */}
            <span className="h-2 w-2 rounded-full bg-[#6BBF72] -ml-1 shrink-0 z-10" />

            {/* Dashed line if currently in progress today */}
            {s.isInProgress ? (
              <span className="absolute inset-0 border-t-2 border-dashed border-[#52B35B]" />
            ) : (
              /* Coral/Red end dot */
              <span className="h-2 w-2 rounded-full bg-[#E15B64] -mr-1 shrink-0 z-10" />
            )}
          </div>
        );
      })}
    </>
  );
}
