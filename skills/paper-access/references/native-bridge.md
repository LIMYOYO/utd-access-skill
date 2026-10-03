# Codex 本地连接（0.6.0 预览）

当前安装/升级以 [安装与升级](installation.md) 和仓库 INSTALL.zh-CN.md 为准。下方 0.3.x/0.4.x 测试时间轴是历史验收记录，不是当前安装版本或跨机器性能承诺。

## 状态和准备
源代码测试通过不代表用户浏览器已安装。安装须具备Chrome、Nomad多大配置、学校登录、本地主机运行环境，以及扩展nativeMessaging权限；对方电脑须使用其实际扩展ID和下载目录，不能照抄原用户的路径。
本地主机不读取学校密码/Cookie，不开放网络端口；能读取配对下载目录下的候选PDF并写入指定论文输出目录。首次启用需用户明确批准此权限及本地主机登记。

Codex执行 `paper-access bridge doctor --json`。未安装返回runtime_not_prepared；installed=true且connected=true才可提交。Chrome保持运行，扩展正常加载。扩展已准备但浏览器未重载时，提示用户重载，不自行绕过管理页工具限制。

本机已于2026-09-30通过单篇及MS/M&SOM/OR三篇顺序CLI-only真实验收（3/3，约80秒，逐篇完成后再开始下一篇（历史严格验收为verified_fulltext））。macOS默认运行环境使用 `~/Library/Application Support/paper-access/bridge-runtime`；Documents下启动器曾在Chrome启动前退出，改为Application Support后连接正常，勿把该现象泛化为确定的系统权限原因。
若 `paper-access` 不在PATH，由Codex使用该目录的 `venv/bin/python -m paper_access` 调用，不要求用户运行命令。不同用户先确认实际安装位置。

## 日常调用
`paper-access bridge fetch <DOI> --out <用户输出目录>`。
命令最多默认等待180秒，默认成功返回state=verified_fulltext或downloaded_fulltext；strict仅verified_fulltext允许分析。payload独立保存下载、身份和analysis_allowed，包含job_id、报告和核验记录。读取报告中的实际artifact路径返回PDF；不能把candidate、downloaded_unverified、pending当成功。
仅INFORMS单篇、reading用途；不要向这个入口传递要求AI/tdm使用的任务。来源授权边界与主skill一致。

`paper-access bridge status <request_id>`查询已有请求；`paper-access bridge cancel <request_id>`停止未来动作并保留原始文件。取消不会删除论文或强制关闭原标签页。
CLI等待超时会返回request_id和wait_timeout_do_not_resubmit，随后查询状态。bridge_busy先处理既有任务；不可重复提交来解决超时。

needs_attention或连接断开时查看原因及保留页面。用户完成学校登录后，先核对旧任务/下载；首次版不会自动重放中断浏览器动作。旧候选的核验恢复不等于重新下载。

## 安装准备（由Codex执行）
`paper-access bridge prepare --destination <稳定且尚不存在的目录> --extension-id <当前Chrome扩展ID> --download-root <实际下载目录> --source-root <完整源码目录>` 仅准备自包含Python运行环境、扩展和配置，不登记到Chrome。需要uv/Python及包安装网络访问。
准备后展示目录、权限及核验结果，获准后执行 `paper-access bridge install --runtime <准备目录>`；用户更新现有扩展并确认新增权限。若换新扩展目录导致ID变化，应重新配对，不能添加任意origin。
`paper-access bridge uninstall --runtime <准备目录>`只撤销归属于本工具的Chrome登记；保留运行环境、PDF及数据库供恢复。

真实验收必须只从CLI提交DOI，不人工点击下载来补成功；确认新PDF、正文核验以及CLI/扩展状态一致后，才把桥接标为可用。

## 双篇并行实验（已通过一组真实验收）

日常默认仍使用上面的单篇入口。用户要求并行时，可用 `paper-access bridge experiment-pair <DOI1> <DOI2> --out <输出目录>`；只接受两篇不同的 INFORMS DOI，不能与另一单篇或双篇任务同时提交。两篇各开后台标签页，原始下载在配对下载目录，核验结果分别写入 `paper-1`、`paper-2`。

下载事件本身不决定论文归属。本地工具安全暂存文件，读取正文主 DOI，唯一匹配后分别核验；两份核验完成，还须浏览器关闭候选池并确认同一组下载编号，才报告整批 `verified_fulltext`。超出两份、归属不唯一、任何异常或断线均暂停；已有文件保留，不自动重复下载。

0.3.1 在本机现有登录会话中，3061/2095 两篇 CLI-only 并行下载及核验通过，耗时20.403秒，各16页，无人工下载点击。首轮3148/0800批次因0800显示 Article Link 而非 Download PDF 停止；扩展0.3.2已补上Article Link及同记录EBSCO详情→PDF阅读页分支，Reload后0800/3148两篇复测2/2通过，耗时26.952秒，各19/28页。实际复测未单独记录中间跳转，分支另有流程测试覆盖。并行机制有成功样本，覆盖和长期稳定性尚不足；本轮未独立确认是否抢前台，不承诺任意论文或速度翻倍。运行环境以 bridge doctor 返回的 runtime 为准，本机新版是 ~/Library/Application Support/paper-access/bridge-runtime-0.3.1。


## 独立并发队列（0.4.0入口，扩展0.4.1已完成本机样本验收）

用户给多篇时使用 `paper-access bridge fetch-batch <DOI1> <DOI2> ... --concurrency <1至10> --out <输出目录>`。一次1至10个不同INFORMS DOI；设为10可同时启动10篇，不再切成5批双篇。默认并发2；用户指定并发数时按其要求执行。不得与其他桥接请求同时提交。

每篇独立后台标签页、150秒下载与核验期限和结果。某篇浏览器路线失败或全文核验未通过，会释放名额让下一篇继续；普通单篇失败不终止同批其他论文。结果中的 `payload.results` 按子任务编号保存具体状态、原因、报告与文件；与 `payload.papers` 对照DOI和输出目录 `paper-1` 至 `paper-N`。部分成功时整批状态为needs_attention、reason为partial_failure，仍交付已验证论文，逐篇报告失败原因；不能把Forbidden或题名不匹配推断成未订阅。

下载文件按正文主DOI归属，不按下载顺序或文件名配对。文件归属无法确认、额外候选、下载中断无法归属或连接断开时停止未完成任务；保留已经核验的结果和文件。全部子任务结束且浏览器确认候选池关闭后，才报告整批成功。超时查询原request_id，不自动重放。

本版队列和失败隔离已有自动化测试、独立代码审查及本机Chrome样本验收。2篇、5篇通过；扩展0.4.1完整十篇复测10/10，66.335秒，混合3篇2成功/1题名失败，28.026秒，无人工下载点击。可作为本机日常并发入口；其他用户仍须完成本人机构准备和验收，不承诺任意INFORMS论文。


### 2026-09-30 真浏览器验收与0.4.1改动
0.4.0已真实通过2/2（45.130秒）、5/5（23.733秒）；10篇同时启动但0/10通过，全部停在EBSCO认证回跳后超时，读取一份页面显示Forbidden。混合3篇1篇正文通过、2篇认证回跳后超时；成功文件独立保留。不将这些现象推断为无订阅。
扩展0.4.1仅把授权跳转上限设为2；可同批启动10个后台publisher标签页，某篇进入viewer就立即释放一个认证名额，PDF下载与核验仍并发，无固定双篇批次。等待认证名额的时间计入150秒单篇期限，若前两篇长期停滞，后续篇可能排队超时。自动化测试及审查通过；Reload后实测记录如下。

0.4.1首轮10篇9/10（150.767秒）：0800停LibKey无法定位全文，独立重试20.403秒成功；随后完整十篇复测10/10，66.335秒。混合3061/0737/2095为2成功、0737题名不匹配失败，28.026秒，成功文件独立保留。不是所有失败都代表未订阅。证据目录 ~/Documents/Paper Access/auth-gate-acceptance-20260930-124929。
日常一次提交整批DOI，用户指定并发10就按10执行；授权跳转单独上限2，逐篇到viewer放行，不是5个固定双篇批次。临时入口失败逐篇报告，用户要求重试时查清原request/已有文件再单独提交，不隐藏重试或自动重复下载。

0.6.0统一默认advisory，可加 --validation-policy strict。另可 --version-policy published-only 限定正式版。INFORMS/SSRN/开放副本的正文下载与身份校验分开报告；策略和来源独立。详情见 [下载与校验策略](delivery-policy.md)。
