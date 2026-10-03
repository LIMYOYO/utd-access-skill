// Serialized by chrome.scripting: keep this function self-contained.
export function inspectOrAct(action, expected) {
  const roots = [document];
  for (let i = 0; i < roots.length; i++) {
    for (const element of roots[i].querySelectorAll('*')) if (element.shadowRoot) roots.push(element.shadowRoot);
  }
  const all = selector => roots.flatMap(root => [...root.querySelectorAll(selector)]);
  const visible = node => Boolean(node.getClientRects().length) && getComputedStyle(node).visibility !== 'hidden';
  const name = node => (node.getAttribute('aria-label') || node.textContent || '').trim();
  const normalized = value => value.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
  const buttons = root => [...root.querySelectorAll('button,[role="button"]')].filter(node => visible(node) && /^(下载|Download)$/i.test(name(node)) && !node.disabled && node.getAttribute('aria-disabled') !== 'true');
  if (action === 'publisher') {
    const metadata = [...document.querySelectorAll('meta')].map(node => ({
      name: (node.getAttribute('name') || '').toLowerCase(),
      content: (node.getAttribute('content') || '').trim()
    }));
    const dois = metadata.filter(meta => ['citation_doi','publication_doi','dc.identifier','dc.identifier.doi','prism.doi'].includes(meta.name))
      .map(meta => meta.content.replace(/^https?:\/\/(?:dx\.)?doi\.org\//i,'').toLowerCase())
      .filter(value => /^10\.\d{4,9}\//.test(value));
    const title = metadata.find(meta => ['citation_title','dc.title'].includes(meta.name))?.content || document.querySelector('h1')?.textContent;
    if (dois.some(doi => doi !== expected.doi)) return {error: '出版社 DOI 不匹配。'};
    if (!dois.includes(expected.doi) || !title) return {waiting: true};
    const links = all('a[href]').filter(a => /(Download PDF|Article Link)/i.test(name(a)) && /University of Toronto/i.test(name(a)));
    if (links.length !== 1) return {waiting: true};
    return {title: title.trim(), href: links[0].href};
  }
  if (location.origin !== 'https://research.ebsco.com') return {waiting:true};
  const details = location.pathname.match(/^\/c\/([^/]+)\/search\/details\/([^/]+)$/);
  if (!details && !location.pathname.includes('/viewer/pdf/')) return {waiting:true};
  const title = document.querySelector('h1,[role="heading"][aria-level="1"]')?.textContent || '';
  if (!title) return {waiting:true};
  if (normalized(title) !== normalized(expected.title)) return {error:'EBSCO 论文标题不匹配。'};
  if (details) {
    if (action !== 'viewer') return {waiting:true};
    const links = all('a[href]').filter(a => {
      try {
        const u = new URL(a.href);
        return u.origin === location.origin && !u.username && !u.password &&
          u.pathname === '/c/'+details[1]+'/viewer/pdf/'+details[2] &&
          /^(转到全功能阅读视图。?|Go to full reader view\.?|Full reader view)$/i.test(name(a));
      } catch { return false; }
    });
    if (links.length !== 1) return {waiting:true};
    return {navigate:links[0].href};
  }
  if (action === 'viewer') return {ready:true};
  if (action === 'open-dialog') {
    const existing = all('[role="dialog"]').filter(visible);
    if (existing.length) return {done:true};
    const choices = buttons(document);
    if (choices.length !== 1) return {waiting:true};
    choices[0].click(); return {done:true};
  }
  const dialogs = all('[role="dialog"]').filter(visible);
  if (dialogs.length !== 1) return {waiting:true};
  const dialog = dialogs[0];
  const selected = dialog.querySelector('[role="tab"][aria-selected="true"]');
  const pdf = [...dialog.querySelectorAll('input[type="radio"],[role="radio"]')].filter(node => {
    const label = node.labels?.[0]?.textContent || node.getAttribute('aria-label') || node.parentElement?.textContent || '';
    return /PDF/i.test(label) && (node.checked || node.getAttribute('aria-checked') === 'true');
  });
  if (!selected || !/^(全文|Full text)$/i.test(name(selected)) || pdf.length !== 1 || buttons(dialog).length !== 1) return {waiting:true};
  if (action === 'click-download') buttons(dialog)[0].click();
  return {done:true};
}
