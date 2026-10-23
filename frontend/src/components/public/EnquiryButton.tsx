'use client';
import { useState } from 'react';
import EnquiryForm from './EnquiryForm';

type Props = React.ComponentProps<typeof EnquiryForm> & { label: string; className?: string };

/** A button that opens the enquiry form in a modal. */
export default function EnquiryButton({ label, className = 'btn-gold', ...form }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} className={className}>{label}</button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-2 flex justify-end">
              <button onClick={() => setOpen(false)} className="text-sm text-slate-500 hover:text-slate-900" aria-label="Close">✕</button>
            </div>
            <EnquiryForm {...form} onDone={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
