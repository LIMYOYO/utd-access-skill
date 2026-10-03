# Paper Access Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution, account registration, paid purchase, publication, or Git synchronization by itself.

**Goal:** 交付可公开安装的 `paper-access` skill 和本地工具：批量接收文献清单，取得并验证可用正文，支持续跑，逐篇说明版本、来源和未完成原因。

**Architecture:** Python 工具处理整批任务和文件，SQLite 保存进度，来源适配器负责发现和获取；skill 将自然语言请求转为工具参数并报告结果。当前 JavaScript 浏览器扩展保留为可选入口，学校登录在用户浏览器中完成。各来源独立失败，不拖住整批任务。

**Tech Stack:** 提议 Python ≥3.11、uv、httpx、标准库 sqlite3 / argparse / dataclasses、pypdf、defusedxml、Beautiful Soup、bibtexparser、rispy；测试使用 pytest 与本地 HTTP fixtures。实施时选定并锁定通过测试的依赖版本；不把依赖升级混入功能开发。

**Spec:** [项目目标与设计](../../PROJECT_PLAN.zh-CN.md)；[访问证据](../../research/2026-09-26-access-audit.md)。本计划细化实现选择；功能尚未实现，以下命令均为拟定接口。

## Global Constraints

- 正式版优先；暂按接受稿/工作论文可作为显式标记的替代版本设计，用户可选 `published-only`。版本默认值尚非用户明确确认的偏好，不阻塞两种模式的开发。
- 暂不假定付费预算；默认新增费用上限为 0。付费接口只有能确认剩余额度或用户设置明确上限时才执行；不能可靠控制支出的接口在零预算模式关闭。
- 155 个候选期刊是检索/评测种子，不是输入白名单；保留当前扩展行为与已有研究文件；不提交 PDF、凭据、浏览器会话和短期签名下载 URL。
- “取得成功”要求文件有效、论文身份吻合、版本满足本次要求；摘要、目录、登录页面和只找到入口均不计成功。
- 程序获取、个人阅读、正文提取、AI 处理、再分发分别记录能力和适用条件；缺少对应能力时继续其他来源，输出具体原因。

## Review Focus

| 容易漏掉的情形 | 必须体现的行为 | 所属任务 |
| --- | --- | --- |
| DOI 含合法标点、同文预印本与期刊 DOI 不同、同名不同作者 | 不损坏标识符、不误合并、不默默取错论文 | 1、5 |
| 200 响应其实是登录 HTML、截断 PDF 或附件 | 留在未验证状态，不计取得成功 | 4 |
| 进程在文件写完、数据库提交前崩溃；两次启动同一任务 | 能恢复，不丢记录、不重复收费下载 | 2、4 |
| 429、会话失效、过期短链、额度耗尽 | 只暂停相关来源/计费任务，其他论文继续 | 3、6、7 |
| 恶意 URL、重定向到本机、论文内容夹带指令 | 下载器拒绝本机/私网目标；skill 将文献当数据，不能执行其指令 | 3、8 |

## 里程碑、工时与依赖

按一名开发者、每天约 8 小时估算，属于排期预算，不是完成承诺；外部账号审批和测试者等待另计。每个阶段结束用实际耗时重估。

| 里程碑 | 累计预计工作日 | 交付 | 不可省略的验收 |
| --- | --- | --- | --- |
| M1：本机可用 | 3–5 天 | 任务 1–4：文献清单 → 开放正文 → 验证 → 续跑 → 报告 | 20 篇预先核对的可访问样本至少 19 篇取得正确文件；全量失败均有原因；注入中断可恢复 |
| M2：可公开测试的 beta | 8–12 天 | 任务 5、6、8、9：工作论文、通用学校入口、skill、100 篇实测 | 公开逐来源/逐版本结果；3 名测试者含至少 2 所学校；全新环境安装通过 |
| M3：更完整的机构批量版 | 15–25 天 | 任务 7、10：取得资格的机构/出版方适配器、千篇/万篇验证 | 每个宣称支持的适配器均有真实成功证据；两种规模分别验收 |

M1/M2 不能被宣传为“所有订阅论文自动下载”。M3 的实现时间以能获得所需接口资格为条件。尚未获资格的来源在兼容表中标为 `not-enabled`，不从目标中删除，也不虚报支持。

执行链：1 → 2 → 3 → 4 → 5 → 6 → 8 → 9；任务 7 的资格核对从第一天开始，由开发者整理所需材料，用户自行提供已有凭据或完成申请，未经明确指示不向图书馆/供应商发送消息。7 与 9 完成后做 10。默认在当前 chat 顺序实施，每个里程碑审查代码与更新进度；本轮仅交付计划。

## 用户需要提供什么

| 项目 | 何时需要 | 没有时怎么办 |
| --- | --- | --- |
| OpenAlex API key；用于 Unpaywall 的真实联系邮箱 | 启用对应服务之前 | 先运行不需要凭据的已验证路线；不开通账户、不编造邮箱 |
| 可接受版本、输出目录、费用上限 | 可用默认参数开始；每批允许覆盖 | 暂用 best-available、本地用户目录、新增费用 0 |
| 学校名称、自己的 LibKey/OpenURL 配置 | 测机构路径时 | OA 路线照常运行；不把 UofT 配置套给所有学校 |
| EDS/出版方 API 资格和允许用途 | 启用机构批量适配器时 | 保留浏览器辅助入口，明确缺失的能力 |
| 第二所学校的试用者 | M2 跨机构验收 | 可以发布受限的测试版本，但不能宣称跨机构实测完成 |

凭据只经本地配置或系统凭据存储读取。skill 不要求用户把 key 粘贴到公开 issue、聊天记录或仓库文件。部署/发布另行执行，代码开发不自动推送 Git。

## 产品接口与输出约定

```text
paper-access doctor --json
paper-access plan references.bib --version best-available --max-cost-usd 0 --out ./papers
paper-access fetch <job-id>
paper-access resume <job-id>
paper-access report <job-id> --format json
```

`plan` 保存清单和选项，不下载正文、不调用可能计费的 discovery API；显示预检结果及哪些费用尚待估算。`fetch` 做发现、获取和验证；`resume` 仅处理未完成/到期可重试条目；已验证文件再次运行跳过。`doctor` 是本地配置/依赖检查，联网探测需显式 `--probe`。

输出目录为 `files/`、`text/`、`manifest.jsonl`、`report.csv`、`report.html`、`pending.csv`；状态数据库放用户数据目录，报告指向文件相对路径。报告区分已验证正式版、接受稿、工作论文、未知版本、待处理；版本未知不计入 published-only 成功。HTML 报告不加载外部脚本并转义标题等外部文本。

`fetch/resume` 退出码：0=所有有效输入都满足任务要求；2=部分未完成且报告已写出；1=无法建立任务/状态库等致命错误。skill 不因退出码 2 宣称整批失败，也不因进程正常结束宣称全成功。

## 文件与接口边界

根目录新增 `pyproject.toml`、`uv.lock`、`python/paper_access/`、`tests/python/`；采用显式 Python 包目录，避免与现有 `src/*.js` 冲突。每个包目录含必要 `__init__.py`。现有 `tests/doi.test.mjs` 留在原处。

`models.py` 定义以下共享类型，其他任务不得私自更名或自行创建第二套同义状态：

| 类型 | 必需字段 / 约定 |
| --- | --- |
| `PaperInput` / `ImportIssue` | 原始输入、行号、DOI/SSRN/arXiv/RePEc/NBER ID、标题/作者/年份；导入错误保留行号与原文 |
| `JobOptions` | version_policy=`best-available/published-only`，purpose=`reading/tdm/ai`，max_cost_usd，output_dir；金额用 Decimal |
| `Candidate` | 文献 ID、provider、持久位置标识符、版本/证据、格式、来源/许可/用途状态、预计费用；短期签名 URL 不持久化 |
| `AttemptOutcome` | status、provider、reason_code、next_retry_at、redacted_detail、cost_usd；状态覆盖设计文档所列状态，并增加 `budget_exhausted`、`rate_limited`、`invalid_input` |
| `Artifact` / `ValidationResult` | 临时/正式文件路径、hash、媒体类型、页数、字节数、身份/版本校验结果、提取质量；网络取得与验证成功分开 |

核心接口：`import_records(path: Path) -> tuple[list[PaperInput], list[ImportIssue]]`；`Provider.discover(paper: PaperInput, context: AccessContext) -> list[Candidate]` 和 `Provider.acquire(candidate: Candidate, context: AccessContext) -> Artifact | AttemptOutcome` 均为 async。`AccessContext` 持有统一的 `HttpClient`、`BudgetLedger`、`CredentialResolver`、`JobOptions` 与 job_id；不得把凭据传入日志。

## Task 1：导入、身份与首次运行入口

**Files:** 创建 `pyproject.toml`、`python/paper_access/{cli,models,imports,config}.py`；测试 `tests/python/test_imports.py`、`test_cli.py`。依赖锁定与 README 开发命令在本任务一起完成。

**Interfaces:** 实现 `import_records`；`normalize_identifier(value: str) -> tuple[str, str] | None` 返回平台和规范 ID；`main(argv: list[str] | None = None) -> int` 为 CLI 入口。导入支持 DOI 文本、CSV、BibTeX、RIS；标题输入先保存，身份匹配在任务 5 完成。

- [ ] 写失败测试：混合输入导入保留顺序/来源行号，`DOI URL` 与同一裸 DOI 合并但保留输入映射；SSRN DOI 与期刊 DOI 不自动合并；合法括号 DOI 不被截断；坏行不使整批退出。
- [ ] 运行 `rtk uv run pytest tests/python/test_imports.py tests/python/test_cli.py -q`，确认因缺少实现失败。
- [ ] 实现导入和 `doctor`；配置仅包含实际使用来源；原有 JS DOI 逻辑作为行为参考而非未经验证地复制。
- [ ] 重跑上述测试，再运行 `rtk npm test`；两套入口均通过后保存本地变更，更新计划勾选。需要提交时使用显式文件清单，不推送。

## Task 2：持久任务、幂等与报告

**Files:** 创建 `python/paper_access/{store,jobs,report}.py`；测试 `tests/python/test_jobs.py`、`test_report.py`；扩展 `cli.py`。

**Interfaces:** `JobStore.create(inputs, issues, options) -> str` 返回 job_id；`JobStore.record_attempt(job_id, paper_id, outcome) -> None`；`JobStore.pending(job_id) -> list[PaperInput]`；`write_report(job_id: str, store: JobStore, output_dir: Path) -> None`。SQLite 表：jobs、inputs、papers、candidates、attempts、artifacts、cost_reservations；迁移版本显式记录。

- [ ] 写失败测试：同一 DOI 的两行输入映射到同一 paper；部分输入错误仍能出报告；标题含 HTML 被转义；第二进程执行同一 job 被提示已有执行者；过期执行租约可以恢复。
- [ ] 运行 `rtk uv run pytest tests/python/test_jobs.py tests/python/test_report.py -q`，确认失败。
- [ ] 实现 `plan` 和数据库事务；job 选项是不可变快照，更改版本/费用条件需新建关联 job；未知费用不填成 0。
- [ ] 测试通过，执行两次同一离线 fixture，验证重复执行不增加 artifact 数；记录本地验收结果。

## Task 3：网络、费用与开放来源发现

**Files:** 创建 `python/paper_access/{http,budget,providers/base,providers/crossref,providers/openalex,providers/unpaywall}.py`；测试 `tests/python/test_http.py`、`test_budget.py`、`test_discovery.py`。

**Interfaces:** `HttpClient.request(method, url, *, provider, **kwargs) -> httpx.Response`；`BudgetLedger.reserve(job_id, request_id, upper_bound: Decimal) -> bool`、`settle(request_id, actual_cost: Decimal) -> None`；`CredentialResolver.get(provider, key_name) -> str | None`。Crossref 只负责 metadata/标识符；OpenAlex、Unpaywall 提供候选位置。KEY 缺失返回明确能力状态。

- [ ] 写失败测试：429 使同主机其他任务也等待 Retry-After；401 不无限重试；零预算且免费额度不可确认时不发计费请求；并发预留不超支；重定向到 localhost/私网地址被拒绝，key 在错误和报告中被遮蔽。
- [ ] 运行 `rtk uv run pytest tests/python/test_http.py tests/python/test_budget.py tests/python/test_discovery.py -q`，确认失败。
- [ ] 实现并发控制：开发默认元数据并发 2、全文并发 4、同全文主机并发 1，均服从来源更严格限制；这些是调试起点而非供应商限额。超时 30 秒、瞬时错误最多 3 次尝试；使用虚拟时钟测试退避，避免测试真实等待。
- [ ] fixtures 通过后，在用户已有配置下做每来源 1 次 live probe；无凭据记 skipped，不判失败或通过。记录 metadata 与 content 两种能力。

## Task 4：真实文件获取、验证、提取与中断恢复

**Files:** 创建 `python/paper_access/{download,validate,extract,runner,providers/repository}.py`；测试 `tests/python/test_download.py`、`test_validation.py`、`test_resume.py`、`test_extract.py`；接通 `fetch/resume`。

**Interfaces:** `run_job(job_id: str, store: JobStore, context: AccessContext) -> int`；`validate_artifact(artifact: Artifact, expected: PaperInput, candidate: Candidate) -> ValidationResult`；`extract_text(artifact: Artifact, output_dir: Path) -> Path | AttemptOutcome`。

- [ ] 写失败测试：HTTP 200 登录 HTML、截断 PDF、只含摘要 HTML、附件、同名不同作者论文均不计 verified；已有正确文件可复用；模拟 rename 后提交前中断，恢复后无需再次下载。
- [ ] 运行 `rtk uv run pytest tests/python/test_download.py tests/python/test_validation.py tests/python/test_resume.py tests/python/test_extract.py -q`，确认失败。
- [ ] 流式写 `.part`，最大 100 MiB 可配置，解析成功后原子移动；身份要求 DOI 主文档证据，或规范标题相符且作者相符，证据不足转 ambiguous；引用列表里的 DOI 不算主文档身份。选择候选只下载一个，失败后再换源。PDF 按页输出，XML/HTML 禁止外部实体/脚本；没有许可依据的 AI 处理不自动启用。
- [ ] 完成 M1 20 篇控制样本测试，并注入断网/进程终止后 resume；报告全部结果。扫描件标记 needs_ocr；正文提取不填补公式、表格或附录的缺失。

## Task 5：SSRN、工作论文、标题匹配与补充来源

**Files:** 创建 `python/paper_access/{matching,providers/ssrn,providers/arxiv,providers/repec,providers/nber,providers/core}.py`；测试 `tests/python/test_versions.py`、`test_working_papers.py`；扩展 `imports.py`。

**Interfaces:** 适配器遵循 `Provider`；`match_identity(input: PaperInput, records: list[PaperInput]) -> list[PaperInput]` 返回候选，不能凭第一条搜索结果定案；`link_versions(left_id: str, right_id: str, evidence: dict, store: JobStore) -> None` 保存关系与证据，不合并字节内容。

- [ ] 写失败测试：SSRN 403 后其余任务继续；没有 DOI 的工作论文保留平台 ID；同标题不同作者不自动匹配；arXiv v1/v2 保留版本；published-only 不接受 AAM；仅题名且无作者的模糊匹配进入确认队列。
- [ ] 运行 `rtk uv run pytest tests/python/test_versions.py tests/python/test_working_papers.py -q`，确认失败。
- [ ] 完成 SSRN ID/DOI 与同文仓库发现，403 时输出浏览器入口；实现 arXiv、RePEc、NBER 的已验证接口；有配置时加入 CORE。CEPR/IZA/CESifo/EconStor 先支持明确标识符和已发现公开链接，独立站点抓取只在文档与 live probe 证实可用后启用。
- [ ] 使用 20 篇工作论文样本核对身份/版本/失败原因；没有成功 live probe 的自动获取方法在兼容表写 `unverified`，而非 supported。

## Task 6：通用机构入口与浏览器补齐

**Files:** 创建 `python/paper_access/{institution,providers/libkey,providers/openurl}.py`、`profiles/institutions/{schema.json,utoronto.example.json}`；测试 `tests/python/test_institution.py`。修改扩展的多机构配置另列有界任务，不把它作为 Python 核心的前置依赖。

**Interfaces:** `build_access_links(paper: PaperInput, institution: dict | None) -> list[dict[str,str]]`；输出稳定的访问入口，不复制浏览器 cookie。机构 profile 包含 institution_name、resolver_base_url、可选 libkey_library_id、可选数据库产品名称，凭据只存引用。

- [ ] 写失败测试：未配置学校照常做 OA；学校 A 的 resolver 不泄漏到学校 B；标题/DOI 正确编码；pending 队列一次列出全部剩余条目；入口页不能改变全文成功计数。
- [ ] 运行 `rtk uv run pytest tests/python/test_institution.py -q`，确认失败。
- [ ] 生成 pending.html/csv；用户完成合法下载后可执行 `paper-access import-file <job-id> <paper-id> <file>`，调用任务 4 的验证再更新状态，不能仅点“已完成”。
- [ ] 在两个机构环境核对入口与各自取得的至少一份允许访问的论文；记录环境/日期/版本，不记录账号信息。无第二机构测试结果时标记待验收。

## Task 7：机构/出版方批量适配器与能力表

**Files:** 创建 `python/paper_access/providers/{eds,elsevier,wiley,sage,springer}.py`、`profiles/providers/capabilities.json`；测试 `tests/python/test_licensed_providers.py`、`test_capabilities.py`；新增 `docs/provider-compatibility.md`。

**Interfaces:** 同一 `Provider` 接口；能力表记录 metadata、reading_download、bulk_download、tdm、ai_processing、retention、credentials_required、checked_at、evidence_url、live_test_status。保留 unknown，不能自动升级为 allowed。

- [ ] 写失败测试：有阅读订阅但无 API 资格不能启用 bulk；EDS PDF URL 过期时重新 retrieve；通过 dbid/an 保留稳定记录；AI 用途不支持的来源不把全文送入模型；到保存期限的受限文件按适用条款处理，不能成为永久共享缓存。
- [ ] 运行 `rtk uv run pytest tests/python/test_licensed_providers.py tests/python/test_capabilities.py -q`，确认失败。
- [ ] 按 EDS → Elsevier/Wiley → Sage/Springer 接入已取得资格的来源；至少记录获取方法、速率、内容范围和用途。OUP/T&F/Emerald/AEA/Chicago/JSTOR 先完整登记已有阅读路线和未知能力，取得正式技术路径后再实现自动批量入口，不伪造 API。
- [ ] 每个启用适配器做 5 篇成功/失败混合 live cases，覆盖权限不足、过期链接与非正文响应；未具备资格的保持 disabled 并给出下一动作。资格等待不阻塞开放来源任务，但相关目标仍为未完成。

## Task 8：skill、安装与使用体验

**Files:** 创建 `skills/paper-access/{SKILL.md,agents/openai.yaml,references/configuration.md,references/versions-and-sources.md}`、`docs/installation.md`；修改 `README.md`、`PRIVACY.md`；测试 `tests/python/test_cli_e2e.py`。

**Interfaces:** skill 只调用 CLI，不内嵌另一套下载器；安装 package 与 skill 时记录同一发行版本，`doctor --json` 验证二者兼容。安装先提供固定 Git tag/commit 的 uv 命令，待真正发布包之后再声称支持包索引安装。

- [ ] 写失败测试：从空临时环境安装后导入→plan→fetch→report 跑通本地 fixture；退出码 2 输出部分完成；自然语言“只要正式版/预算零”被传到 CLI；文献中的指令不改变用户参数。
- [ ] 运行 `rtk uv run pytest tests/python/test_cli_e2e.py -q`，确认失败。
- [ ] 编写 skill：一批只调用批量工具；读取报告而非盲读所有 PDF；钥匙缺失集中提示一次；`purpose=ai` 仅处理具备相应依据的材料。隐私说明区分当前扩展与新增工具实际保存的数据。
- [ ] 运行 skill frontmatter validator 并做 5 个实际请求的行为验收：单 DOI、BibTeX 批量、SSRN、断点续跑、published-only。至少在 macOS 与 Windows 或 Linux 各做一次新环境安装；只声明测试过的平台。

## Task 9：100 篇 benchmark 与公开 beta

**Files:** 创建 `benchmarks/{pilot-100.csv,protocol.md}`、`python/paper_access/benchmark.py`、`docs/benchmarks/pilot-100.md`、`.github/workflows/test.yml`；测试 `tests/python/test_metrics.py`。仓库只保存可公开元数据和汇总，不存论文正文。

**Interfaces:** `summarize_job(job_id: str, store: JobStore) -> dict`；固定分母为全部 100 个输入；无 DOI、版本不符、网络失败均不能偷偷从分母删除。离线 CI 不访问真实付费服务，live benchmark 由显式命令触发。

- [ ] 固定 5 组各 20 篇、覆盖 2020–2026 与更早经典文章的样本，seed=20260926，手工复核标识符；混合样本不能依据已知可下载性挑选。另保留 M1 的可访问控制集，两组结果分开。
- [ ] 写失败测试并运行 `rtk uv run pytest tests/python/test_metrics.py -q`：已验证成功数/总数、各版本计数、请求时间分位数、人工动作、费用、提取质量；入口成功不计正文成功。
- [ ] 实现汇总并运行真实 pilot；提出产品目标自动正确取得 ≥70/100，作为继续投入的假设，不是已有结果或保证。未达标时用前两大失败类别决定改进，保留原样本和结果，不能换成更容易的样本。
- [ ] 3 名测试者/2 所学校反馈通过，fixture 全通过、成功文件抽检无错配、预算和恢复缺陷为 0 后准备 beta 发布包。达到公共发布条件后再执行明确授权的发布；未达覆盖目标可作标明限制的预览，不能称稳定版。

## Task 10：1,000 / 10,000 条任务与后续维护

**Files:** 新增 `benchmarks/{batch-1000.csv,batch-10000-query.json}`、`docs/benchmarks/{batch-1000.md,batch-10000.md}`；修改网络/runner 的调优参数须有基准支持。新增测试 `tests/python/test_large_job.py`、`test_incremental.py`。

**Interfaces:** 新命令 `paper-access collect --issn <issn> --from-year <year> --to-year <year> --max-records <n>` 生成可审阅 manifest；保存 cursor、查询、返回 ID 和时间。collect 只发现清单，fetch 仍由同一任务/预算/版本规则执行。

- [ ] 用 10,000 条本地 fixtures 测稳定分页、去重、内存有界与每条状态持久化；注入中断、429、响应类型错误及跨来源失败，继续仅处理未完成项。
- [ ] 运行 `rtk uv run pytest tests/python/test_large_job.py tests/python/test_incremental.py -q`，先确认失败，实现后通过；此结果只证明本地调度可靠性，不证明真实千篇下载成功。
- [ ] 在具备相应访问条件和明确费用上限时执行 1,000 条真实任务，随后执行 10,000 条；公开每阶段取得数、版本、耗时、实际费用、人工数和失败比例。预算不足时保存断点，报告未完成，不能以模拟运行替代。
- [ ] 发布兼容表与支持声明，记录每个 provider 最后成功探测时间；建议每月人工检查文档与少量样本，尚不创建自动监控。失败来源有降级开关，按失败证据更新适配器。

## 完成审计与交接

本计划与设计范围的对应关系：输入/去重=1；持久化/报告=2；多来源发现/费用=3；实际全文/质量/恢复=4；SSRN/econ/版本=5；跨机构=6；许可接口=7；skill/安装/隐私=8；可公开实测=9；大规模/期刊年份清单=10。模块接口共用同一套 models 和状态。

现在的下一项是 Task 1。先在合适的本地隔离分支/工作区实施导入与任务入口，保留本次规划与审计文件；不把 `.serena/` 当作已审查发布内容。每个里程碑结束更新本文件勾选和 `docs/PROJECT_PLAN.zh-CN.md` 的已验证进度，记录测试命令、结果、剩余依赖。

发布承诺分层：M1=本机原型；M2=有已公布局限的公开 beta；M3=仅对真实验收过的来源/规模声称稳定支持。没有账号、没有学校测试或没有规模测试，都不能靠文档勾选替代。
