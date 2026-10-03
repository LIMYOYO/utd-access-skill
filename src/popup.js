import { buildLibKeyUrl, buildUofTSessionUrl, extractDoi } from "./doi.js";
import { DOWNLOAD_ACCESS, parseInformsDoi } from './download-policy.js';
import {SSRN_ACCESS} from './ssrn-policy.js';

const form = document.querySelector("#doi-form");
const input = document.querySelector("#doi-input");
const status = document.querySelector("#status");
const startSession = document.querySelector("#start-session");

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function collectPageCandidates() {
  const selectors = [
    'meta[name="citation_doi"]',
    'meta[name="dc.identifier"]',
    'meta[name="dc.identifier.doi"]',
    'meta[name="prism.doi"]',
    'meta[property="og:url"]'
  ];
  const metaValues = selectors
    .map((selector) => document.querySelector(selector)?.content)
    .filter(Boolean);
  const doiLinks = [...document.querySelectorAll('a[href*="doi.org/10."]')]
    .slice(0, 10)
    .map((anchor) => anchor.href);

  return [window.location.href, ...metaValues, ...doiLinks];
}

async function detectDoi() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      setStatus("Paste a DOI to continue.");
      return;
    }

    const [{ result: candidates = [] }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: collectPageCandidates
    });
    const doi = candidates.map(extractDoi).find(Boolean);
    if (doi) {
      input.value = doi;
      setStatus("DOI detected from the current page.");
    } else {
      setStatus("No DOI detected. Paste one below.");
    }
  } catch {
    setStatus("This page cannot be inspected. Paste a DOI below.");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const doi = extractDoi(input.value);
  if (!doi) {
    setStatus("Enter a valid DOI, such as 10.1287/mnsc.2025.00819.", true);
    input.focus();
    return;
  }

  chrome.tabs.create({ url: buildLibKeyUrl(doi) });
  window.close();
});

startSession.addEventListener("click", () => {
  chrome.tabs.create({ url: buildUofTSessionUrl() });
  window.close();
});

input.addEventListener("input", () => {
  if (status.classList.contains("error")) {
    setStatus("Paste a DOI or keep typing.");
  }
});

detectDoi();

const downloadStatus = document.querySelector('#download-status');
const downloadButton = document.querySelector('#download-paper');
function showTask(reply) {
  if (!reply?.ok) { downloadStatus.textContent = reply?.error || '无法连接下载工具。'; return; }
  const task = reply.task;
  downloadStatus.textContent = task ? [task.doi,task.message,task.filename].filter(Boolean).join('\n') : '尚未开始。';
  downloadButton.disabled = Boolean(task && (['publisher','viewer','waiting_download'].includes(task.phase) || (task.request_id && task.phase === 'downloaded_unverified')));
}
downloadButton.addEventListener('click',async () => {
  try {
    const doi = parseInformsDoi(input.value);
    const granted = await chrome.permissions.request(DOWNLOAD_ACCESS);
    if (!granted) throw Error('未授予所需权限，未开始下载。');
    showTask(await chrome.runtime.sendMessage({type:'paper-start',doi}));
  } catch (error) { downloadStatus.textContent = error.message; }
});
document.querySelector('#stop-download').addEventListener('click',async () => {
  try { showTask(await chrome.runtime.sendMessage({type:'paper-stop'})); }
  catch (error) { downloadStatus.textContent = error.message; }
});
chrome.storage.onChanged.addListener((changes,area) => {
  if (area === 'local' && changes.singlePaperTask) showTask({ok:true,task:changes.singlePaperTask.newValue});
});
chrome.runtime.sendMessage({type:'paper-status'}).then(showTask).catch(error => { downloadStatus.textContent = error.message; });

document.querySelector('#diagnose-download').addEventListener('click',async () => {
  try {
    const reply = await chrome.runtime.sendMessage({type:'paper-diagnose'});
    const output = document.querySelector('#download-diagnostics');
    if (!reply.ok) { output.textContent = reply.error; return; }
    if (reply.task?.diagnostics) {
      const rows = reply.task.diagnostics;
      output.textContent = `${reply.task.doi || ''} 下载记录诊断（不代表正文校验）：` + (rows.length ? '\n'+JSON.stringify(rows,null,2) : '未找到本次时间范围内的 EBSCO PDF 记录。');
    }
  } catch (error) { downloadStatus.textContent = error.message; }
});

const bridgeStatus = document.querySelector('#bridge-status');
const showBridge = value => { bridgeStatus.textContent = value?.message || 'Codex 本地连接尚未启用。'; };
chrome.storage.local.get('bridgeConnection').then(data=>showBridge(data.bridgeConnection));
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local' && changes.bridgeConnection)showBridge(changes.bridgeConnection.newValue);});
document.querySelector('#bridge-reconnect').addEventListener('click',()=>{chrome.runtime.sendMessage({type:'bridge-reconnect'}).catch(()=>{});});

const pairStatus=document.querySelector('#pair-status');
const showPair=task=>{pairStatus.textContent=task ? '双篇实验：'+task.message : '';};
chrome.storage.local.get('parallelPairTask').then(data=>showPair(data.parallelPairTask));
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.parallelPairTask)showPair(changes.parallelPairTask.newValue);});

const showBatch=task=>{if(task){pairStatus.textContent='并发任务：'+task.message;if(task.phase==='running')downloadButton.disabled=true;}};
chrome.storage.local.get('parallelBatchTask').then(data=>showBatch(data.parallelBatchTask));
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.parallelBatchTask)showBatch(changes.parallelBatchTask.newValue);});

const ssrnStatus=document.querySelector('#ssrn-status');
document.querySelector('#enable-ssrn').addEventListener('click',async()=>{
  try {const granted=await chrome.permissions.request(SSRN_ACCESS);ssrnStatus.textContent=granted?'SSRN 权限已启用，可以让 Codex 提交论文编号。':'未授予 SSRN 网站权限。';}
  catch(error){ssrnStatus.textContent=error.message;}
});
const showSsrn=task=>{if(task)ssrnStatus.textContent='SSRN '+task.ssrn_id+'：'+task.message;};
chrome.storage.local.get('ssrnPaperTask').then(data=>showSsrn(data.ssrnPaperTask));
chrome.storage.onChanged.addListener((changes,area)=>{if(area==='local'&&changes.ssrnPaperTask)showSsrn(changes.ssrnPaperTask.newValue);});
