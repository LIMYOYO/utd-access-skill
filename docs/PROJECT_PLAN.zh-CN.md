# Paper Access Router：面向 OM / OR / Economics 的公开 skill 规划

日期：2026-09-26（America/Toronto；查证跨 9 月 25–26 日）。状态：历史设计与访问调查。0.6.0 实现已进入仓库；当前安装和能力边界以根目录 [README](../README.md)、[安装文档](../INSTALL.zh-CN.md) 和 `skills/paper-access/` 为准。

本文保留早期范围、来源调查和阶段设计，其中“尚未实现”“拟定接口”等状态描述只代表 2026-09-26 当时，不再作为当前安装或发布说明。

执行交接：[具体任务、文件、接口、验收和排期](superpowers/plans/2026-09-26-paper-access-execution.md)。该计划细化为 10 个可验收任务；本文件保留目标与来源判断。

## 1. 重新定义目标

让任何机构的 OM、OR、管理学、经济学及相邻领域研究者，交给工具一份文献清单后，以尽可能少的人工操作取得可用全文，并知道每篇的版本、来源、缺失原因与下一步。最终公开分发 skill 与可复现的本地执行工具；各用户使用自己的访问资格和 API key。

输入支持 DOI、标题、SSRN / arXiv / RePEc / NBER 标识符及链接、BibTeX、RIS、CSV。第一阶段以明确文献清单为入口；按期刊与年份建立大规模文献集作为后续模式。期刊目录是检索和测试的种子，不是白名单，目录之外的 DOI 仍应工作。

“获取成功”必须是实际取得并验证了论文正文，而非打开网页、返回摘要、发现 PDF 链接或下载到登录页。输出包括原始 PDF / HTML / XML、在适用使用条件允许时生成的正文文本、来源清单、可续传任务状态和未完成队列。

设计默认：正式版优先，无法便捷取得时接受经过匹配的作者接受稿或工作论文，显式标注；只要用户选择“仅正式版”，则不把其他版本计入完成。这个偏好已询问用户，在答复前属于提议，不是已确认要求。暂不假定付费预算；默认新增费用上限为 0。

## 2. 查证结果改变了哪些假设

EBSCO 是重要的机构访问渠道，但不能当作所有期刊的统一全文来源。官方 Business Source Premier、Complete、Ultimate 目录在本次检查中有明显差异；例如 POM、JOM、QJE、JPE 在 Ultimate 中列有延迟全文，而在 Premier / Complete 中没有列出全文覆盖。AER 列有 24 个月全文延迟；Econometrica 与 EJOR 在这三份目录均没有列出全文覆盖。详情、来源和字段解释见 [访问审计](research/2026-09-26-access-audit.md) 与同目录 CSV。

目录所列覆盖不是用户所在学校的实际馆藏证明，也不是某篇文章的成功下载证明。出版年份、卷期、online-first 状态、数据库产品、机构订阅、缺失文章与临时故障都可能改变结果。空白延迟字段只表示“未列延迟”，不能自动推导实时收录。

另外，阅读权限、程序批量获取权限、保存期限、把全文用于 AI 的权限需要分别记录。EBSCO 公开标准协议 I.3 明确涉及系统性建库和 AI/ML 限制；学校另行签订的条款可能不同。EDS API 的技术存在不能直接推导批量使用许可。不要要求每位用户阅读一套通用法律清单：适配器有已核实的默认能力；仅在相应来源无法支持当前用途时提示具体缺失条件。[EBSCO 标准协议](https://legal.ebsco.com/license-agreement)

## 3. 期刊和文献范围

候选目录按五组组织，共 155 个标题，包含核心期刊、相邻领域和必要旧刊名。具体标题与 ISSN 由 EBSCO 目录、Crossref 或 OpenAlex 元数据核对；记录来源，不把聚合器登记的出版机构名称当作当前出版方的保证。[完整候选目录](research/journal-scope.csv) · [408 条 EBSCO 产品覆盖记录](research/ebsco-coverage.csv)

| 范围 | 代表性期刊 / 文献 |
| --- | --- |
| OM、供应链、服务、交通 | MS、M&SOM、OR、POM、JOM、Decision Sciences、EJOR、IJPE、IJPR、JSCM、JBL、IJOPM、Transportation Science、Transportation Research A–E、Omega、Naval Research Logistics、IISE Transactions |
| OR、优化、随机系统 | 全部 17 本 INFORMS 期刊；MOR、IJOC、IJOO、Stochastic Systems；Mathematical Programming、MPC、SIOPT、OR Letters、Annals of OR、Queueing Systems、JAP、AAP、概率相关期刊 |
| 管理、IS、营销 | Organization Science、ISR、MISQ、JMIS、JAIS、Marketing Science、JM、JMR、JCR、AMJ、AMR、SMJ、ASQ、Management Studies、Research Policy |
| 经济学 | 五大刊；AER Insights、四本 AEJ、JEL、JEP、JEEA、REStat、Economic Journal；JET、TE、QE、GEB、RAND、JIE、IJIO、JEMS；计量、劳动、公共、发展、国际、宏观、健康、能源、环境、城市经济学 |
| 金融、统计、ML 与工作论文 | JF、JFE、RFS、Review of Finance、JFQA；AoS、JASA、JRSS-B、Biometrika、Statistical Science、JMLR；SSRN、arXiv、RePEc / IDEAS、NBER、CEPR、IZA、CESifo、EconStor、大学仓库、作者网页 |

这不是“所有可能相关期刊”的穷尽性证明。不同 OM 方向还会涉及医疗、计算机、能源或政策领域。扩展机制比静态长名单重要：允许添加 ISSN / ISSN-L、标题别名、出版年份区间和用户自定义集合；保留 Interfaces → IJAA、IIE → IISE 等历史关系，并按实际文章标识符消歧。

SSRN 是工作论文平台，不应被处理成一个普通正式期刊。SSRN DOI 与最终期刊 DOI 是相关的不同文献记录，不做无条件合并。

## 4. 三种架构的取舍

| 方案 | 优点 | 主要问题 | 结论 |
| --- | --- | --- | --- |
| 扩展模拟人工逐页下载 | 登录直观、改造起点近 | 页面变化、会话过期、MFA、反自动化响应；难复现和续传 | 作为少量剩余项目的辅助入口 |
| 只用 EBSCO / LibKey | 机构路径集中 | 数据库差异、embargo、独立凭据与使用条件；LibKey 是链接解析，不是统一全文仓库 | 作为机构适配器 |
| 本地批量引擎 + 多来源解析 + skill | 能缓存、并发、续传、验证、记录版本；可跨机构 | 需要维护少数服务适配器并测覆盖 | 推荐主方案 |

保留 `src/` 内现有扩展。新增的核心应是独立于浏览器的 Python 批量工具，skill 调用工具处理整批工作，避免每篇论文都让模型走一遍网页。Node 扩展只是可选的 DOI 捕获与登录辅助端。第一版不依赖自建云服务，也不必把每个来源做成单独 MCP 服务。

## 5. 推荐访问路线

```text
清单 → 规范化 / 去重 / 身份匹配 → 本地缓存
                                  ↓ 未命中
                并行发现可用位置与版本（有各服务限速）
             Crossref + OpenAlex + Unpaywall + 可选 CORE
                                  ↓
       已缓存开放全文 / 开放仓库 / 允许当前用途的出版方 API
                                  ↓ 未完成
               用户机构的 LibKey / OpenURL / EDS 路径
                                  ↓ 未完成
               集中人工队列：SSRN、登录、ILL、作者版本
                                  ↓
             文件验证 + 版本记录 + 可选正文提取 + 报告
```

发现可以并行；下载按每篇选定来源进行，避免同时从五个站点重复下载。版本质量优先级通常为正式版、接受稿、工作论文；同一质量等级再按已验证成功率、延迟、费用和授权匹配排序。可提供 `fastest-available` 与 `published-only` 选项，速度偏好不能悄悄改变版本要求。

| 来源 / 平台 | 设计用途与技术路线 | 本次证据边界 |
| --- | --- | --- |
| OpenAlex | 文献、位置和版本发现；有缓存时使用官方 PDF / TEI XML content API；大任务评估官方 CLI | 元数据实测成功；无 key 下载返回 401；尚未实测带 key 下载 |
| Unpaywall | 按 DOI 获取开放版本位置，读取版本与许可字段 | 官方 API / 维护方代码核对；未提供真实联系邮箱，未做 API 调用 |
| CORE | 补齐大学仓库内容；评估全文与批量端点 | 官方说明核对；未做带 key 的端到端验证 |
| 开放机构仓库 | 使用已发现的正式公开文件入口，保留原始版本标记 | 宾大一篇 M&SOM 工作稿下载与 PDF 解析成功 |
| arXiv | 保留 arXiv ID 与版本；官方 metadata API + 指定批量全文渠道 | 官方批量文档核对；未下载大语料 |
| SSRN | 接受 abstract ID / DOI，发现同文版本；可访问时取得用户指定论文，遇 403 / 登录则集中处理 | 普通请求为 403；未证实通用公开批量全文 API。不得把 ScienceDirect TDM key 推断为 SSRN key |
| RePEc / IDEAS | 发现经济学工作论文、正式版关系及外部全文位置 | 官方 API 文档核对；RePEc 本身不是统一 PDF 仓库 |
| NBER / CEPR / IZA / CESifo / EconStor | 各自的论文编号与仓库入口；元数据与全文分开适配 | NBER 有官方批量元数据；其他平台全文条件逐个验证；部分 SSRN 集合收费 |
| LibKey / OpenURL | 机构馆藏解析、全文入口和文献传递兜底；不支持 LibKey 的学校也能使用通用 OpenURL | LibKey 入口返回 HTML；API 集成需要申请，不公开嵌入私钥 |
| EBSCO EDS | 有机构 API 凭据且用途获支持时：DOI 搜索 → `dbid/an` → retrieve → 当前 PDF/HTML | 官方接口说明支持；PDF URL 会过期。无机构凭据，未做受订阅全文获取 |
| Elsevier / Wiley | 用各自官方 TDM API；按资格、用途、速率和保存要求下载 | 官方文档支持；尚未完成带凭据测试。EBSCO 订阅不自动等于出版方 API 权限 |
| Sage / Springer Nature | Sage 的 Crossref TDM 链接；Springer 的 OA 或协议限定全文端点 | 技术与使用条件已查；不预设所有内容或 AI 用途都获准 |
| OUP / T&F / Emerald / AEA / Chicago / JSTOR | 开放版本 + 机构解析；需规模化时核对出版方 TDM / 语料服务 | OUP 与 T&F 政策有证据；其余 API 能力按来源保持待验证，不虚构统一接口 |

Crossref 的链接字段也不是自动下载许可；例如本次 INFORMS 记录中的链接用途是 `similarity-checking`，不能当作面向普通用户的 TDM 授权。元数据没有链接同样不证明不存在作者版本。

## 6. 最快、最方便、稳定如何落实

用户理想操作是：“把这个 BibTeX 的论文正文取到本地，允许接受稿，费用上限 0；完成后告诉我哪些仍需处理。”首次运行只配置实际要用的服务，学校配置可选。每位用户单独保存 key；不依赖项目作者的账号。

批量引擎以 SQLite 保存任务和每次尝试，以 DOI / 平台 ID 记录文献，以 SHA-256 记录文件。缓存命中直接复用；过期的是来源链接或授权状态时重新解析，不能反复使用 EBSCO 短期 URL。下载到临时文件，验证通过后原子移动；中断后仅重试未完成项目。文件级续传只有在服务器支持 Range 且 ETag / Last-Modified 一致时使用，否则重取该文件。用户重跑同一批任务不产生重复文件。

速率由来源决定，设全局和每个主机的并发上限、令牌桶、Retry-After、指数退避与抖动。429 对整个适配器减速；401 转配置/登录；403 转备用来源或人工队列；5xx 有限重试；预算耗尽可续传。禁止把“提高稳定性”实现为轮换身份绕过服务限制。元数据 API 的高吞吐量不能直接套用到 PDF 网站。

验证包括响应类型、PDF 文件签名与解析、HTML 登录页识别、正文长度、标题/作者/DOI 匹配、补充材料识别，以及论文版本。标题近似或期刊版和预印本内容关系不清时保留两个对象并标记人工确认。不能只凭同名或全文里出现 DOI 就当作正确论文。

正文首选来源提供的 XML / JATS / TEI 或 HTML；只有 PDF 时做本地提取，扫描件进入 OCR 队列。对 OM 论文另标公式、表格、附录是否完整；纯文本提取成功不等于数学内容无损。保留原文件和页码/段落映射；不以模型补写缺失正文。

任务状态建议：`resolved`、`queued`、`downloaded_unverified`、`verified_fulltext`、`needs_login`、`needs_credentials`、`needs_rights_review`、`ambiguous_match`、`retryable_failure`、`not_found`。工作完成状态与正文提取质量是两个维度。

## 7. 规模、费用与基准

100 篇、1,000 篇、10,000 篇是建议测试规模，不是已经达成的能力或性能承诺。先选 100 篇有分层的试验集，按 INFORMS、其他 OM、经济学、SSRN/工作论文、方法类各取 20 篇，同时覆盖新/旧文章与 OA/订阅情况。正式评估还应固定 2020–2026 各年份样本，避免只用容易访问的老论文。

必须分别报告：正式版取得率、接受稿取得率、工作论文取得率、未解决率、文件误匹配率、每来源成功率、首次耗时、续传耗时、人工操作数、API 费用和正文提取质量。OA 标记率、元数据匹配率不能冒充全文取得率。保留随机种子、样本 DOI 清单、软件版本和日期，不能以一篇样本外推整体覆盖率。

OpenAlex 本次官方价格：注册账户每天有 $1 API 用量额度，正文服务列为每文件 $0.01。按此计算，只下载一种格式的 1,000 份缓存文件，服务用量约 $10；扣除当天仍可用额度后再计付费，检索请求和双格式下载另算。这是费用演算，不是可获得 1,000 篇的保证。下载前估算，默认费用上限 0；用户愿意付费时再选择速度优先方案。[官方价格](https://help.openalex.org/access/pricing/) · [正文服务](https://help.openalex.org/access/fulltext/)

万篇级任务优先评估官方批量导出、OpenAlex CLI / archive、arXiv 批量渠道或出版方语料服务。无论规模多少，都先比较缓存和公开版本的命中情况，不需要一开始购买机构级套餐。

## 8. skill 分发结构与实现顺序

建议公开仓库保留现名，新增 `skills/paper-access/SKILL.md` 作为入口，使用 `references/` 存机构配置、来源能力与版本规则。确定性运行逻辑放可独立测试的 Python 包；skill 薄封装它。安装说明提供 Codex 和通用支持 SKILL.md 的 agent 用法；浏览器扩展单独说明。下列命令是拟定接口，尚不可执行：

```text
paper-access doctor
paper-access plan references.bib --version best-available --max-cost 0
paper-access fetch <job-id>
paper-access resume <job-id>
paper-access report <job-id>
```

| 阶段 | 有界交付物 | 完成证据 |
| --- | --- | --- |
| 1. 批量核心 + OA | DOI/BibTeX/CSV 导入，Crossref/OpenAlex 发现，公开文件获取，验证、缓存、续传、报告 | 固定 100 篇分层样本；正确文件与失败分类；断网/重跑不重复；零预算不收费 |
| 2. 工作论文与经济学 | SSRN/arXiv/RePEc/NBER 标识符、版本关系、仓库补齐；RIS 和标题消歧 | 同文多版本与错配测试；SSRN 403 不阻塞其他任务；无法解析的条目有原输入 |
| 3. 机构与出版方 | 通用 OpenURL / LibKey；独立 UofT 配置；EDS 与授权出版方 API | 至少两个机构配置；真实订阅、embargo、过期链接和会话测试；凭据不入库/日志 |
| 4. skill 封装与公开测试 | 轻量 skill、跨平台安装、文档、可再现 benchmark、隐私说明 | 全新机器按说明可运行；skill 行为测试；公开包不含凭据、会话或下载论文 |
| 5. 大批量稳定性 | 1,000 / 10,000 条任务、断点、限速、费用和失败隔离 | 真实授权渠道的规模测试结果；公开每来源覆盖与限制；不以小样本测试代替 |

这些是依赖顺序，不对外承诺工期。浏览器助手不应阻塞 OA 引擎运行；学校不订阅某个服务也不妨碍其他路线。公开的是工具、元数据目录、测试清单和性能记录，不是自动打包的论文库。

## 9. 本轮完成与仍未证明的事项

本轮已完成：重定位、候选期刊范围、三种 EBSCO 产品目录比对、主要来源官方文档核对、少量匿名 API / 文件访问验证和实施阶段设计。原型的“某篇为 OA”测试描述出现证据冲突，已改成待验证案例。

尚未完成：批量运行引擎、可发布 skill、用户真实 API key 下的正文下载、跨学校认证测试、期刊逐篇覆盖率、SSRN 稳定批量访问、1,000 / 10,000 篇性能验证。这些是实施与发布的验收项，不能在目前宣传为已具备。

下一步的有界动作：审阅本文件第 1 节的版本默认值，再实施第 1 阶段。真实库权限、付费预算和 AI 使用范围应在相应适配器启用时核实，不需要为了设计阶段先获取所有账号。
