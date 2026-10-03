export const DOWNLOAD_ACCESS = {
  permissions: ['downloads'],
  origins: ['https://pubsonline.informs.org/*', 'https://research.ebsco.com/*']
};

export function parseInformsDoi(input) {
  let value = String(input).trim();
  if (value.startsWith('https://')) {
    const url = new URL(value);
    if (!['pubsonline.informs.org', 'doi.org'].includes(url.hostname) || url.username || url.password) throw Error('请提供 INFORMS DOI 或论文链接。');
    value = decodeURIComponent(url.pathname.replace(/^\/doi\//, '').replace(/^\//, ''));
  }
  if (!/^10\.1287\/[a-z0-9._()-]+$/i.test(value)) throw Error('原型只支持一篇完整的 INFORMS DOI。');
  return value.toLowerCase();
}

export function libraryLink(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && u.hostname === 'libkey.io' && !u.username && !u.password &&
      /^\/libraries\/278\/articles\/\d+\/(?:full-text-file|content-location)$/.test(u.pathname);
  } catch { return false; }
}

export function matchesDownload(task, item) {
  if (task.phase !== 'waiting_download' || !task.viewerUrl || !item.referrer ||
      !(Date.parse(item.startTime) >= task.armedAt)) return false;
  try {
    const source = new URL(item.referrer), viewer = new URL(task.viewerUrl);
    return source.origin === 'https://research.ebsco.com' && source.origin === viewer.origin && source.pathname === viewer.pathname;
  } catch { return false; }
}

export function downloadOutcome(item) {
  if (item.state === 'interrupted' || item.exists === false) return 'stopped';
  if (item.state !== 'complete') return 'waiting_download';
  if (item.mime !== 'application/pdf' && !/\.pdf$/i.test(item.filename || '')) return 'stopped';
  return 'downloaded_unverified';
}


// This is a candidate for local DOI/content validation, never proof of paper identity.
export function candidateDownload(task, item) {
  if (task.phase !== 'waiting_download' || item.referrer || !task.viewerUrl ||
      !Number.isFinite(task.deadline)) return false;
  const started = Date.parse(item.startTime);
  if (!(started >= task.armedAt && started <= task.deadline)) return false;
  try {
    return new URL(task.viewerUrl).origin === 'https://research.ebsco.com' &&
      new URL(item.url).origin === 'https://research.ebsco.com';
  } catch { return false; }
}

// A detail page can only offer its own same-tenant, same-record PDF viewer.
export function detailViewerLink(value, current) {
  try {
    const from=new URL(current),to=new URL(value);
    const match=from.pathname.match(/^\/c\/([^/]+)\/search\/details\/([^/]+)$/);
    return Boolean(match && from.origin==='https://research.ebsco.com' && to.origin===from.origin && !to.username && !to.password && to.pathname==='/c/'+match[1]+'/viewer/pdf/'+match[2]);
  } catch {return false;}
}
