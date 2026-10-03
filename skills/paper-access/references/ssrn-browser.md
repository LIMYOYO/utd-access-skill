# SSRN 浏览器单篇适配（扩展/核验器0.6.0）

本适配复用已登录 Chrome 的正常 SSRN 页面下载入口，先确认 Chrome 文件下载 complete，再安全暂存并执行已有正文/身份核验。Cookie 留在浏览器，不导出到 HTTP 客户端。本机2026-09-30已从CLI提交4189586，真实SSRΝ下载及身份/正文校验通过（8页，34.424秒，无人工下载点击）。另外5203708下载12页但严格身份校验失败；4558521页面明确审核中或移除，人工检查后取消等待。当前3篇样本2篇下载、1篇验证成功，不承诺SSRΝ普遍支持或批量稳定。自动化测试和模拟native host成功不能替代其他机器/论文的真实验收。

首次需要扩展0.6.0和本地运行环境0.6.0.dev1。由 Codex 准备和安装，用户在 Chrome Reload 扩展，然后打开扩展点击「启用 SSRN 网站权限」，只申请 https://papers.ssrn.com/*（并复用现有下载权限）。只用现有授权 Chrome，不要求 OpenAlex、Unpaywall 或 EDS API 密钥。人工处理登录和验证码。

先运行 `paper-access bridge doctor --json`，以返回的 runtime 为准；若CLI不在PATH，Codex通过该runtime的 `venv/bin/python -m paper_access` 调用。
提交 `paper-access bridge fetch-ssrn <论文编号、10.2139/ssrn.DOI 或 SSRN 论文链接> --out <输出目录>`。支持 --validation-policy advisory|strict，默认advisory；仅支持单篇 reading，不能与 INFORMS 请求同时运行。默认等待270秒，浏览器阶段240秒。CLI超时查询原request_id，不重复提交。

扩展开一个 inactive 论文标签页，核对页面 citation_doi、题名、作者与实际正常下载链接。链接文件名的 SSRN_ID 可能是修订编号，必须使用 abstractid 判断论文归属。相同下载按钮上下重复不算两个入口；多个不同入口则暂停。只点击一次，按下载URL和时间窗口绑定确切 Chrome download ID；不接受其他 SSRN PDF 或既有旧下载。

请求验证时，提示用户在对应标签页人工完成；不要自动破解、连续重试或启动新隐藏浏览器。240秒内未产生完成文件则 needs_attention，保留页面与文件。用户处理后先查询原请求，已终止时核对既有文件，再决定是否重新提交。

下载与身份核对分开报告：download_status=complete 表示文件已完整下载；identity_status=verified 且 state=verified_fulltext 才表示身份严格通过。匿名稿标为 authors_blinded，其他识别不足标为 not_verified，保留 delivered_file 供用户阅读，不能说下载失败或作者已核实。编号/DOI冲突在默认模式下保留文件并明确身份未通过，可分析文件内容但不把它确认为请求论文；strict则阻止分析。非正文或损坏文件不能通过下载关卡。读取 payload.snapshot/报告获取实际 PDF 路径并交付；版本缺少可靠出版证据时为 unknown，不能宣称 SSRN 托管必然是正式版或工作论文版。已有校验器要求可解析正文结构和 DOI 或题名作者证据；PDF 中冲突的 SSRN abstract 编号不能被忽略。

取消、断连、重启不自动重放下载；已完成的 downloaded_unverified 候选可在重连后再次提交本地核验。旧下载异常绑定原request_id，不得停止新请求；核验期间额外匹配文件视为歧义。INFORMS 下载适配和冻结0.4.1/0.4.0.dev1恢复基线保持不变。

2026-09-30 十份既有 SSRN PDF 本地复核（没有重新下载）：0.5.1 核验器9篇标题作者通过，1篇作者匿名已交付待核对；原始0.5.0测试10/10下载、3/10身份通过记录保留。识别限前三页，正文边界优先；仅去除明确期刊/工作论文固定前缀、修复名字内拆开的重音，不从参考文献找匹配，不让封面覆盖错误正文。版本仍为 unknown。

0.6.0 默认 advisory：downloaded_fulltext 也是成功下载和可分析终态；不再将身份未通过一律视为任务失败。strict 下载仍保留，但身份未通过时阻止后续分析。以 [下载与校验策略](delivery-policy.md) 为准。
