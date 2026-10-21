'use client';
// Screen 02: Category Access Form (DPDP Act 2023 compliant)
import { useState } from 'react';

export default function CategoryGateModal({ categorySlug }: { categorySlug: string }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white max-w-md w-full rounded-xl p-6 space-y-4 shadow-2xl">
        <h3 className="text-lg font-bold text-slate-900">Unlock {categorySlug} Products</h3>
        <p className="text-sm text-slate-500">Tell us who you are. You will only need to do this once.</p>
        <form className="space-y-3">
          <input type="text" placeholder="Your Name" required className="w-full border px-3 py-2 rounded-md text-sm" />
          <input type="text" placeholder="Phone (+91...) or Email" required className="w-full border px-3 py-2 rounded-md text-sm" />
          <label className="flex items-start gap-2 text-xs text-slate-600">
            <input type="checkbox" required className="mt-0.5" />
            <span>I consent to be contacted regarding this catalogue in accordance with DPDP Act 2023.</span>
          </label>
          <button type="submit" className="w-full bg-blue-700 text-white py-2 rounded-md font-medium text-sm">
            Unlock Catalog
          </button>
        </form>
      </div>
    </div>
  );
}
