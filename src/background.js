import { buildLibKeyUrl, extractDoi } from "./doi.js";

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
