// Privacy-friendly page reader for manage.th-lawfirm.sa (Laravel Livewire + Flux UI).
// Emits "label: value" lines so the privacy shield can recognise names/IDs that follow labels,
// plus attachment groups and file cards. Never returns raw HTML.
(() => {
  const T = s => (s || '').replace(/\s+/g, ' ').trim();
  const NAV = new Set(['لوحة التحكم', 'القضايا']);
  const LABELS = ['الدائن', 'المدين', 'رقم المطالبة', 'القضية', 'مبلغ المطالبة', 'تاريخ الإنشاء', 'تم إنشاؤه بواسطة',
    'الحالة', 'نوع القضية', 'الأولوية', 'المحامي الرئيسي', 'العملاء الأفراد', 'وصف القضية', 'متطلبات العميل',
    'رقم القضية', 'مرجع Odoo', 'المحكمة', 'القاضي', 'الخصم', 'عميل', 'ملاحظات', 'الفئة', 'النوع', 'الفريق القانوني'];
  const root = document.querySelector('main') || document.body;
  const WC = () => [...document.querySelectorAll('button, a, div, span')].filter(e => e.hasAttribute('wire:click'));
  // ordered list of visible text chunks
  const texts = [];
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: n => (T(n.nodeValue) && n.parentElement && n.parentElement.offsetParent !== null
      && !n.parentElement.closest('script,style,template')) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
  while (tw.nextNode()) texts.push(T(tw.currentNode.nodeValue));
  const out = ['URL: ' + location.pathname];
  const crumbs = [...document.querySelectorAll('[data-flux-breadcrumbs-item], nav[aria-label*=read] a, .breadcrumb li')].map(e => T(e.innerText)).filter(Boolean);
  if (crumbs.length) out.push('المسار: ' + crumbs.map(c => NAV.has(c) ? c : 'الطرف: ' + c).join(' › '));
  const seen = new Set();
  for (let i = 0; i < texts.length - 1; i++) {
    const k = texts[i].replace(/\s*:$/, '');
    const isLabel = LABELS.includes(k) || (/:$/.test(texts[i]) && texts[i].length < 35);
    if (!isLabel) continue;
    const v = texts[i + 1];
    if (!v || LABELS.includes(v.replace(/\s*:$/, '')) || v.length > 400) continue;
    const line = `${k}: ${v}`;
    if (!seen.has(line)) { seen.add(line); out.push(line); }
  }
  for (const b of WC()) {
    const w = b.getAttribute('wire:click') || '';
    const g = w.match(/^addFilesToGroup\('(.*)'\)$/);
    if (g) out.push('مجموعة مرفقات: ' + T(g[1]));
  }
  for (const b of WC().filter(e => (e.getAttribute('wire:click') || '').startsWith('viewAttachment'))) {
    const id = ((b.getAttribute('wire:click') || '').match(/\d+/) || [''])[0];
    let card = b;
    for (let up = 0; up < 8 && card.parentElement; up++) {
      card = card.parentElement;
      if (/نوع الملف/.test(card.innerText || '')) break;
    }
    const lines = (card.innerText || '').split('\n').map(T).filter(s => s && s !== 'عرض');
    out.push(`ملف [attachment_id=${id}]: ` + lines.join(' | ').slice(0, 300));
  }
  const tabs = [...new Set([...document.querySelectorAll('a[href*="/case/"], a[href*="/claim/"]')]
    .map(a => `${T(a.innerText)} -> ${a.getAttribute('href').replace(/^https?:\/\/[^/]+/, '')}`))];
  if (tabs.length) out.push('روابط: ' + tabs.slice(0, 60).join(' | '));
  return out.join('\n');
})()
