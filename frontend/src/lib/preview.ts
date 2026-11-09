// Small helpers for the in-page file preview (components/portal/FilePreview.tsx), kept here so the
// unit tests (tests/lib.test.mjs) can check them.

export type PreviewKind = 'pdf' | 'image' | 'text' | 'sheet' | 'word' | 'none';

/** How a file is shown in the page. By the extension checked at upload; 'none' = Download only. */
export function previewKind(f: { name: string; content_type: string }): PreviewKind {
  const ext = f.name.includes('.') ? f.name.split('.').pop()!.toLowerCase() : '';
  if (f.content_type === 'application/pdf') return 'pdf';
  if (f.content_type.startsWith('image/')) return 'image';
  if (ext === 'csv' || ext === 'xlsx' || ext === 'xls') return 'sheet';
  if (ext === 'docx') return 'word'; // old .doc can't be read in the browser: Download
  if (ext === 'txt') return 'text';
  return 'none';
}

/** Excel-style column letters: 0 -> A, 25 -> Z, 26 -> AA, 701 -> ZZ, 702 -> AAA. */
export function colName(i: number): string {
  let s = '';
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
}

/** Word files can hold any link, even `javascript:`. The preview frame can't run scripts anyway; as a
 *  second guard, every link that isn't a plain web or email address, or a jump inside the document
 *  (footnotes, contents: "#..."), loses its address (the text stays). */
export function safeLinks(html: string): string {
  return html.replace(/\shref="([^"]*)"/gi, (whole, url: string) =>
    /^(https?:\/\/|mailto:|#[\w-]+$)/i.test(url) ? whole : '');
}

export const viewUrl =(id: number) => `/api/v1/files/${id}/view`;
export const downloadUrl = (id: number) => `/api/v1/files/${id}/download`;
