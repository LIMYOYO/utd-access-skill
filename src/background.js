import { buildLibKeyUrl, extractDoi } from "./doi.js";
import { installDownloader } from './downloader.js';

import { installPairDownloader } from './pair-downloader.js';
import { installBatchDownloader } from './batch-downloader.js';
import {installSsrnDownloader} from './ssrn-downloader.js';
let pairController,batchController,ssrnController;
const controller = installDownloader(chrome,{externalBusy:()=>pairController?.busy()||batchController?.busy()||ssrnController?.isBusy()||false});
pairController=installPairDownloader(chrome,{singleBusy:()=>controller.isBusy()||batchController?.busy()||ssrnController?.isBusy()||false});
batchController=installBatchDownloader(chrome,{externalBusy:()=>controller.isBusy()||pairController.busy()||ssrnController?.isBusy()});
import { installNativeBridge } from './native-bridge.js';
ssrnController=installSsrnDownloader(chrome,{externalBusy:()=>controller.isBusy()||pairController.busy()||batchController.busy()});
const bridge = installNativeBridge(chrome, controller, {pairController,batchController,ssrnController});
chrome.runtime.onMessage.addListener((message,sender) => {
  if (message?.type === 'bridge-reconnect' && sender.id === chrome.runtime.id && !sender.tab && sender.url === chrome.runtime.getURL('src/popup.html')) bridge.reconnect();
});

const MENU_ID = "paper-access-router-open";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: "Open paper through LibKey",
      contexts: ["selection", "link", "page"]
    });
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId !== MENU_ID) {
    return;
  }

  const candidates = [info.selectionText, info.linkUrl, info.pageUrl];
  const doi = candidates.map(extractDoi).find(Boolean);
  if (!doi) {
    return;
  }

  chrome.tabs.create({ url: buildLibKeyUrl(doi) });
});
