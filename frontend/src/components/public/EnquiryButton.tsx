'use client';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import EnquiryForm from './EnquiryForm';

type Props = React.ComponentProps<typeof EnquiryForm> & { label: string; className?: string; onOpen?: () => void; onClose?: () => void };

/** A button that opens the enquiry form in a modal.
 *  The modal is drawn straight into <body> (a portal): a parent with a CSS transform would otherwise
 *  squeeze its full-screen layer into the parent's box (e.g. the floating enquiry-list bar). */
export default function EnquiryButton({ label, className = 'btn-gold', onOpen, onClose, ...form }: Props) {
  const [open, setOpen] = useState(false);
  const close = () => {
    setOpen(false);
    onClose?.();
  };
  return (
    <>
      <button onClick={() => { onOpen?.(); setOpen(true); }} className={className}>{label}</button>
      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
            data-enquiry-modal
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.target === e.currentTarget && close()}
          >
            <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl">
              <div className="mb-2 flex justify-end">
                <button onClick={close} className="text-sm text-slate-500 hover:text-slate-900" aria-label="Close">✕</button>
              </div>
              <EnquiryForm {...form} onDone={close} />
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
