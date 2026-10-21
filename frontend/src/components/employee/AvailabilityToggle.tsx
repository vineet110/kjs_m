'use client';
// Screen 05: Availability Toggle
import { useState } from 'react';

export default function AvailabilityToggle() {
  const [isAvailable, setIsAvailable] = useState(true);

  return (
    <button
      onClick={() => setIsAvailable(!isAvailable)}
      className={`px-3 py-1.5 rounded-full text-xs font-bold border transition-colors flex items-center gap-2 ${
        isAvailable
          ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
          : 'bg-slate-100 text-slate-600 border-slate-300'
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${isAvailable ? 'bg-emerald-500' : 'bg-slate-400'}`}></span>
      {isAvailable ? 'Available: Receiving Tasks' : 'Unavailable: Off Duty'}
    </button>
  );
}
