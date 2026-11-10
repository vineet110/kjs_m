'use client';
// Team attendance: who is in today, missed-punch approvals, leave approvals, and Excel export.
import { useCallback, useEffect, useState } from 'react';
import { addDays, EmptyState, fmtDay, PageTitle, Pill, todayIST } from '@/components/portal/ui';
import { useToast } from '@/components/portal/Toast';
import { api, ApiFailure, type LeaveRequest, type Regularization, type Shift } from '@/lib/api';
import { approvalsChanged } from '@/lib/portal-session';
import Loading from '@/components/ui/Loading';
import LoadError from '@/components/ui/LoadError';

// Clearer words for some roster states (the colour still comes from the state). Others show as they are.
const ROSTER_LABEL: Record<string, string> = { upcoming: 'Yet to check in', leave: 'On leave' };

type Row = { user_id: number; name: string; is_available: boolean; state: string; check_in: string | null; check_out: string | null; hours: number };

export default function TeamAttendance() {
  const toast = useToast();
  const [day, setDay] = useState(todayIST());
  const [rows, setRows] = useState<Row[] | null>(null);
  const [pendingRegs, setPendingRegs] = useState<Regularization[]>([]);
  const [pendingLeaves, setPendingLeaves] = useState<LeaveRequest[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [err, setErr] = useState('');
  const [loadErr, setLoadErr] = useState<unknown>(null);

  // Export Modal state
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportStart, setExportStart] = useState(() => `${todayIST().slice(0, 7)}-01`);
  const [exportEnd, setExportEnd] = useState(todayIST());
  const [exportUser, setExportUser] = useState<string>('');
  const [exportStatus, setExportStatus] = useState<string>('');
  const [exporting, setExporting] = useState(false);

  const load = useCallback(() => {
    // A failure shows the error with "Try again", never an empty list that looks like "nothing waiting"
    setLoadErr(null);
    api<Row[]>(`/attendance/team?day=${day}`).then(setRows).catch((e) => { setRows([]); setLoadErr(e); });
    api<Regularization[]>('/attendance/approvals').then(setPendingRegs).catch(setLoadErr);
    api<LeaveRequest[]>('/attendance/leaves/approvals').then(setPendingLeaves).catch(setLoadErr);
    api<Shift[]>('/attendance/shifts').then(setShifts).catch(setLoadErr);
  }, [day]);

  useEffect(() => {
    load();
  }, [load]);

  async function decideReg(id: number, approve: boolean) {
    setErr('');
    try {
      await api(`/attendance/approvals/${id}`, { method: 'POST', body: { approve } });
      toast(approve ? 'Missed punch approved' : 'Request rejected');
      approvalsChanged();
      load();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  async function decideLeave(id: number, approve: boolean) {
    setErr('');
    let rejection_reason: string | null = null;
    if (!approve) {
      rejection_reason = window.prompt('Please enter a rejection reason (optional):') || null;
    }
    try {
      await api(`/attendance/leaves/approvals/${id}`, {
        method: 'POST',
        body: { approve, rejection_reason },
      });
      toast(approve ? 'Leave request approved' : 'Leave request rejected');
      approvalsChanged();
      load();
    } catch (e) {
      setErr(e instanceof ApiFailure ? e.message : 'Could not save.');
    }
  }

  async function downloadExcel() {
    setExporting(true);
    setErr('');
    try {
      const params = new URLSearchParams({
        start_date: exportStart,
        end_date: exportEnd,
      });
      if (exportUser) params.append('user_id', exportUser);
      if (exportStatus) params.append('status', exportStatus);

      const res = await fetch(`/api/v1/attendance/export?${params.toString()}`, {
        headers: { 'x-requested-with': 'kjs' },
      });
      if (!res.ok) {
        throw new Error('Export failed');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `KJS_Attendance_${exportStart}_${exportEnd}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setShowExportModal(false);
      toast('Attendance report downloaded!');
    } catch (e) {
      setErr('Failed to download Excel report. Please check date range.');
    } finally {
      setExporting(false);
    }
  }

  const counts = (rows ?? []).reduce<Record<string, number>>((acc, r) => ({ ...acc, [r.state]: (acc[r.state] ?? 0) + 1 }), {});

  return (
    <div className="space-y-6">
      <PageTitle title="Team Attendance" sub="Monitor daily roster, approve leaves & missed punches, export reports.">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowExportModal(true)}
            className="btn-dark flex items-center gap-1.5 py-1.5 text-xs font-medium"
          >
            📥 Export to Excel
          </button>
          <div className="flex items-center gap-1 border-l pl-2 border-slate-200">
            <button className="btn-ghost py-1" onClick={() => setDay(addDays(day, -1))}>←</button>
            <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="input w-auto text-xs py-1" />
            <button className="btn-ghost py-1" onClick={() => setDay(addDays(day, 1))}>→</button>
          </div>
        </div>
      </PageTitle>

      {loadErr != null && <LoadError error={loadErr} onRetry={load} />}
      {err && <p className="rounded p-2 text-sm bg-red-50 text-red-700">{err}</p>}

      {/* Pending Leave Requests */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold flex items-center gap-2">
          Leave Requests Waiting Approval
          {pendingLeaves.length > 0 && (
            <span className="rounded-full bg-amber-500 px-2 py-0.5 text-xs text-white">
              {pendingLeaves.length}
            </span>
          )}
        </h2>
        {pendingLeaves.length === 0 && (
          <EmptyState tone="done" title="No pending leaves" text="Employee leave applications will appear here." />
        )}
        {pendingLeaves.map((l) => (
          <div key={l.id} className="card flex flex-wrap items-center gap-3 p-4 text-sm">
            <div className="min-w-[12rem]">
              <span className="font-semibold text-slate-900">{l.user_name}</span>
              <p className="text-xs text-slate-500 capitalize">{l.leave_type} Leave · {l.working_days} working day(s)</p>
            </div>
            <div>
              <span className="font-medium text-slate-800">{fmtDay(l.start_date)} {l.start_date !== l.end_date ? `to ${fmtDay(l.end_date)}` : ''}</span>
              {l.is_half_day && <span className="ml-2 text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">Half Day</span>}
            </div>
            <span className="text-slate-500 max-w-sm truncate">“{l.reason}”</span>
            <span className="ml-auto flex gap-2">
              <button onClick={() => decideLeave(l.id, true)} className="btn-dark py-1 text-xs">Approve</button>
              <button onClick={() => decideLeave(l.id, false)} className="btn-ghost py-1 text-xs text-red-600 hover:bg-red-50">Reject</button>
            </span>
          </div>
        ))}
      </section>

      {/* Missed Punch Requests */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold flex items-center gap-2">
          Missed-Punch Requests
          {pendingRegs.length > 0 && (
            <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-white">
              {pendingRegs.length}
            </span>
          )}
        </h2>
        {pendingRegs.length === 0 && (
          <EmptyState tone="done" title="Nothing waiting" text="Missed-punch requests from the team show here." />
        )}
        {pendingRegs.map((r) => (
          <div key={r.id} className="card flex flex-wrap items-center gap-3 p-4 text-sm">
            <span className="font-semibold">{r.user_name}</span>
            <span>{fmtDay(r.day, true)} · {r.check_in}–{r.check_out ?? '?'}</span>
            <span className="text-slate-500">“{r.reason}”</span>
            <span className="ml-auto flex gap-2">
              <button onClick={() => decideReg(r.id, true)} className="btn-dark py-1 text-xs">Approve</button>
              <button onClick={() => decideReg(r.id, false)} className="btn-ghost py-1 text-xs text-red-600 hover:bg-red-50">Reject</button>
            </span>
          </div>
        ))}
      </section>

      {/* Daily Team Roster */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold">{fmtDay(day, true)} Roster</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          {Object.entries(counts).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1.5 rounded-md bg-white px-2 py-1 border border-slate-200">
              <Pill value={k} label={ROSTER_LABEL[k]} /> <span className="font-bold text-xs">{v}</span>
            </span>
          ))}
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="p-3">Name</th>
                <th className="p-3">Status</th>
                <th className="p-3">Check In</th>
                <th className="p-3">Check Out</th>
                <th className="p-3">Hours</th>
                <th className="p-3">Receiving Tasks</th>
              </tr>
            </thead>
            <tbody>
              {rows === null && <tr><td className="p-3" colSpan={6}><Loading /></td></tr>}
              {rows?.map((r) => (
                <tr key={r.user_id} className="border-t hover:bg-slate-50/50">
                  <td className="p-3 font-medium text-slate-800">{r.name}</td>
                  <td className="p-3"><Pill value={r.state} label={ROSTER_LABEL[r.state]} /></td>
                  <td className="p-3 font-mono">{r.check_in ?? '—'}</td>
                  <td className="p-3 font-mono">{r.check_out ?? '—'}</td>
                  <td className="p-3 font-semibold">{r.hours > 0 ? `${r.hours} h` : '—'}</td>
                  <td className="p-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${r.is_available ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'}`}>
                      {r.is_available ? 'Available' : 'Away'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Export to Excel Modal */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="card w-full max-w-lg p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b pb-2">
              <h3 className="text-lg font-bold text-slate-900">Export Attendance to Excel</h3>
              <button onClick={() => setShowExportModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Start Date</label>
                  <input
                    type="date"
                    value={exportStart}
                    onChange={(e) => setExportStart(e.target.value)}
                    className="input"
                  />
                </div>
                <div>
                  <label className="label">End Date</label>
                  <input
                    type="date"
                    value={exportEnd}
                    onChange={(e) => setExportEnd(e.target.value)}
                    className="input"
                  />
                </div>
              </div>

              <div>
                <label className="label">Filter Employee</label>
                <select
                  value={exportUser}
                  onChange={(e) => setExportUser(e.target.value)}
                  className="input"
                >
                  <option value="">All Employees</option>
                  {rows?.map((u) => (
                    <option key={u.user_id} value={u.user_id}>
                      {u.name} (ID: {u.user_id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label">Filter Status</label>
                <select
                  value={exportStatus}
                  onChange={(e) => setExportStatus(e.target.value)}
                  className="input"
                >
                  <option value="">All Statuses</option>
                  <option value="present">Present Only</option>
                  <option value="leave">Leaves Only</option>
                  <option value="absent">Absents Only</option>
                </select>
              </div>

              <div className="rounded bg-slate-50 p-3 text-xs text-slate-500 space-y-1">
                <p>📊 <b>The generated .xlsx file contains 2 sheets:</b></p>
                <p>1. <b>Detailed Attendance</b>: Daily timestamps, shift code, hours worked, and status.</p>
                <p>2. <b>Employee Summary</b>: Aggregated working days, leaves, absents, total hours, and average hours/day.</p>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                type="button"
                onClick={() => setShowExportModal(false)}
                className="btn-ghost py-1.5"
                disabled={exporting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={downloadExcel}
                className="btn-dark py-1.5"
                disabled={exporting}
              >
                {exporting ? 'Generating Excel...' : 'Download .xlsx Report'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
