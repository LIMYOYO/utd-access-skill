# UTD Access Skill 的版本与来源

- best-available 优先正式版，然后接受稿、工作论文，最后未知版本；published-only 仅接受有版本证据的正式版。
- DOI/SSRN/NBER 可经 Crossref 元数据与 OpenAlex、Unpaywall 已发现的开放链接获取。SSRN 入口不等于自动下载成功，遇到封锁转浏览器。
- arXiv 精确编号保留版本；无版本输入使用 API 返回的具体 PDF 版本。请求在同一本地状态目录中串行并留出至少三秒间隔；多台电脑不要同时运行 arXiv 获取。
- 仅题名且无作者不自动匹配。提供 DOI 或完整作者、年份再建任务；同名多结果留待确认。
- RePEc API 未配备访问资格，CORE 与机构/出版方批量适配器未启用。不能宣称这些来源已支持自动全文。
- 阅读、文本提取、AI、再分发权限分别判断。当前自动来源默认仅 reading。提取文本保留原文件和页映射，但公式/表格排版未经保证；扫描件保留 needs_ocr。
- INFORMS 优先按 informs-browser.md 走多大浏览器；CLI fetch/resume 仍只执行已实现的自动来源。浏览器中断需回到原页面继续，OA 下载中断后调用 resume。单个尚未写完的文件可能重新下载；已验证文件经复核后复用。重复点击入口不会更改成功状态。
