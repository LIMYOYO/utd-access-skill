// Runs in the normal signed-in Chrome tab; does not solve verification challenges.
export function inspectSsrnPage(id,action='inspect',expectedUrl='') {
  const meta=name=>document.querySelector('meta[name="'+name+'"]')?.content?.trim()||'';
  if(location.origin!=='https://papers.ssrn.com')return {status:'attention',reason:'SSRN 页面跳转到其他网站，请人工检查'};
  if(meta('citation_doi').toLowerCase()!=='10.2139/ssrn.'+id) {
    const body=document.body?.innerText||'';
    return {status:'wait',reason:/verify|verification|just a moment|checking your browser|captcha/i.test(body+' '+document.title)?'SSRN 要求浏览器验证，请在该页面人工完成':'等待 SSRN 论文页面'};
  }
  const title=meta('citation_title'),authors=Array.from(document.querySelectorAll('meta[name="citation_author"]')).map(e=>e.content.trim()).filter(Boolean);
  if(!title||title.length>4096||!authors.length||authors.length>100||authors.some(a=>a.length>256))return {status:'attention',reason:'缺少或无效的论文标题与作者，未触发下载'};
  const links=Array.from(document.querySelectorAll('a.primary[data-abstract-id]')).filter(a=>a.getAttribute('data-abstract-id')===id&&a.getClientRects().length);
  const urls=[...new Set(links.map(a=>a.href))];
  if(urls.length!==1)return {status:'attention',reason:'正常下载入口缺失或不唯一'};
  const url=urls[0];let valid=false;
  try {const u=new URL(url);valid=u.origin===location.origin&&!u.username&&!u.password&&!u.hash&&/^\/sol3\/Delivery\.cfm(?:\/[^/]+\.pdf)?$/i.test(u.pathname)&&u.searchParams.get('abstractid')===id&&!u.searchParams.has('type');}catch{}
  if(!valid)return {status:'attention',reason:'下载入口与当前论文编号不匹配'};
  if(action==='click') {
    if(url!==expectedUrl)return {status:'attention',reason:'下载入口发生变化，未点击'};
    links[0].click();
  }
  return {status:'ready',title,authors,url};
}
