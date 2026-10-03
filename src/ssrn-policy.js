export const SSRN_ACCESS={permissions:['downloads'],origins:['https://papers.ssrn.com/*']};
export function parseSsrnId(input) {
  let value=String(input).trim();
  if(value.startsWith('https://')) {
    const url=new URL(value);
    if(url.username||url.password||url.port||url.hash)throw Error('无效 SSRN 链接');
    if(url.hostname==='doi.org')value=url.pathname.slice(1);
    else if(['papers.ssrn.com','ssrn.com','www.ssrn.com'].includes(url.hostname)) {
      if(url.pathname==='/sol3/papers.cfm')value=url.searchParams.get('abstract_id')||'';
      else {const match=url.pathname.match(/^\/abstract=([1-9]\d{0,9})$/);value=match?.[1]||'';}
    } else throw Error('请提供 SSRN 论文编号或链接');
  }
  value=value.replace(/^10\.2139\/ssrn\./i,'');
  if(!/^[1-9]\d{0,9}$/.test(value))throw Error('请提供 SSRN 论文编号或链接');
  return value;
}
export function ssrnDownloadLink(value,id) {
  try {const u=new URL(value);return u.origin==='https://papers.ssrn.com'&&!u.username&&!u.password&&!u.hash&&/^\/sol3\/Delivery\.cfm(?:\/[^/]+\.pdf)?$/i.test(u.pathname)&&u.searchParams.get('abstractid')===id&&!u.searchParams.has('type');}
  catch{return false;}
}
export function matchesSsrnDownload(task,item) {
  const started=Date.parse(item.startTime);
  return ['waiting_download','downloaded_unverified'].includes(task.phase)&&started>=task.armedAt&&started<=task.deadline&&item.url===task.downloadUrl;
}
