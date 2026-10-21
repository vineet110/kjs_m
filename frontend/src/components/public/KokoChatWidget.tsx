'use client';
// Screen 03: Koko AI Assistant floating widget
import { useState } from 'react';

export default function KokoChatWidget() {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {open ? (
        <div className="bg-white w-80 sm:w-96 h-[480px] rounded-2xl shadow-2xl border flex flex-col overflow-hidden">
          <div className="bg-blue-800 text-white p-4 flex justify-between items-center">
            <div>
              <h4 className="font-bold text-sm">Koko AI Assistant</h4>
              <p className="text-xs text-blue-200">Answers strictly from KJS specs</p>
            </div>
            <button onClick={() => setOpen(false)} className="text-white hover:text-slate-200 text-sm">✕</button>
          </div>
          <div className="flex-1 p-4 overflow-y-auto space-y-2 text-sm">
            <div className="bg-slate-100 p-2.5 rounded-lg max-w-[85%] text-slate-800">
              Hello! I'm Koko. Ask me about our coffee, tea, and confectionery packaging capacities!
            </div>
          </div>
          <div className="p-3 border-t bg-slate-50 flex gap-2">
            <input type="text" placeholder="Ask Koko..." className="flex-1 text-sm border rounded-lg px-3 py-1.5" />
            <button className="bg-blue-700 text-white px-3 py-1.5 rounded-lg text-sm font-semibold">Send</button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="bg-blue-800 text-white px-4 py-3 rounded-full shadow-lg hover:bg-blue-900 flex items-center gap-2 font-semibold text-sm"
        >
          <span>💬</span> Chat with Koko
        </button>
      )}
    </div>
  );
}
