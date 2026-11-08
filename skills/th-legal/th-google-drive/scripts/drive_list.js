// Privacy-safe Google Drive folder listing through Drive's own files API (run in a drive.google.com tab).
// Input (replaced before running): __PARAMS__ = {"folder": "<folderId>"}
// Output: JSON {ok, count, items:[{id, folder, num, kw, ext, size, created, modified}]}
// NEVER returns item names: only the leading number (e.g. claim number), matched keywords and extension.
(async (P) => {
  const KW = ['رد المدين', 'مخالصة', 'مخالصه', 'تسوية', 'تسويه', 'مدمج', 'اثبات', 'إثبات', 'التبليغ', 'طلب',
    'النواقص', 'حكم', 'صك', 'وكالة', 'فاتورة', 'هوية', 'سجل', 'عقد', 'كشف', 'سند', 'إيصال', 'ايصال', 'شيك', 'خطاب', 'رد'];
  const norm = s => s.replace(/[إأآ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي');
  const cookies = Object.fromEntries(document.cookie.split('; ').map(c => [c.slice(0, c.indexOf('=')), c.slice(c.indexOf('=') + 1)]));
  const sapisid = cookies['SAPISID'] || cookies['__Secure-3PAPISID'] || cookies['__Secure-1PAPISID'];
  if (!sapisid) return JSON.stringify({ ok: false, error: 'not signed in to Google in this tab' });
  const origin = 'https://drive.google.com';
  const ts = Math.floor(Date.now() / 1000);
  const dig = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(`${ts} ${sapisid} ${origin}`));
  const auth = 'SAPISIDHASH ' + ts + '_' + [...new Uint8Array(dig)].map(b => b.toString(16).padStart(2, '0')).join('');
  let key = null;
  try {
    const w = window.WIZ_global_data || {};
    key = (typeof w.yLTeS === 'string' && w.yLTeS) || Object.values(w).find(v => typeof v === 'string' && /^AIza[\w-]{30,}$/.test(v));
  } catch (e) {}
  if (!key) return JSON.stringify({ ok: false, error: 'Drive API key not found on this page (open drive.google.com first)' });
  const q = `'${P.folder}' in parents and trashed = false`;
  const items = [];
  let token = '';
  for (let page = 0; page < 50; page++) {
    const url = 'https://clients6.google.com/drive/v3/files?q=' + encodeURIComponent(q) +
      '&fields=' + encodeURIComponent('nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime)') +
      '&pageSize=1000&supportsAllDrives=true&includeItemsFromAllDrives=true&key=' + key + (token ? '&pageToken=' + token : '');
    let r, j;
    for (let attempt = 0; attempt < 3; attempt++) {
      try { r = await fetch(url, { headers: { Authorization: auth, 'X-Goog-AuthUser': '0' }, credentials: 'include' }); j = await r.json(); break; }
      catch (e) { await new Promise(res => setTimeout(res, 1500)); }
    }
    if (!r || !r.ok) return JSON.stringify({ ok: false, status: r && r.status, error: j && j.error && j.error.message });
    for (const f of j.files || []) {
      const n = (f.name || '').trim();
      const m = n.match(/^\s*(\d+)/) || n.match(/(\d{3,6})\s*(?:\.\w+)?$/);
      const nn = norm(n);
      items.push({
        id: f.id, folder: f.mimeType === 'application/vnd.google-apps.folder',
        num: m ? m[1] : null,
        kw: KW.filter(k => nn.includes(norm(k))),
        ext: (n.match(/\.(\w{2,5})$/) || [, ''])[1].toLowerCase(),
        size: f.size ? Number(f.size) : null, created: f.createdTime, modified: f.modifiedTime,
      });
    }
    token = j.nextPageToken;
    if (!token) break;
  }
  return JSON.stringify({ ok: true, count: items.length, items });
})(__PARAMS__)
