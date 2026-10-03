# UTD Access Skill 的 Codex 安装执行指南

目标：从完整仓库安装 CLI、同版 skill、Chrome 扩展和 native bridge，并取得真实可用的 PDF。用户无需自己运行终端命令；需要用户时只给当前一个具体浏览器操作。

适用：macOS + 桌面 Chrome + 可执行本机命令的 Codex。普通网页 ChatGPT、纯 API 或只有 SKILL.md 的环境不具备本机下载能力。INFORMS 自动适配固定为 University of Toronto / LibKey library 278 / EBSCO；SSRN 单篇不要求多大账号。其他平台或学校不得按本指南宣称自动下载已支持。

目录：[检查环境](#1-检查环境) · [安装工具和-skill](#2-安装工具和-skill) · [加载扩展和授权](#3-加载扩展和授权) · [建立-bridge](#4-建立-bridge) · [真实验收](#5-真实验收) · [升级与恢复](#6-升级与恢复) · [排错和卸载](#7-排错和卸载)

## 1. 检查环境

先检查已有安装，保留用户文件，不重复安装已经可用的组件。记录实际来源、版本、学校、Chrome profile、扩展加载目录和下载目录。不得索取或复制密码、MFA、cookie、会话令牌；登录与验证码交给用户本人。

| 组件 | 准备方法 |
| --- | --- |
| 完整仓库 | 使用用户提供的仓库链接/目录。可 `git clone`，或下载 GitHub ZIP 并解压到长期保留的可写目录。根目录必须有 `pyproject.toml`、`python/paper_access`、`manifest.json`、`src`、`skills/utd-access-skill`；只有 wheel 或 skill 不够。 |
| uv | 检查 `uv --version`；缺失时按 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)安装。已有 Homebrew 可用 `brew install uv`；否则用官方 standalone installer，无需先安装 Homebrew。若当前 shell 找不到 uv，使用安装器返回的绝对路径，不依赖重开终端。 |
| Python | 要求 3.11+；没有合适版本时执行 `uv python install 3.12`。uv 可管理 Python，不需要修改系统 Python；下面用 3.12 固定安装解释器。 |
| Chrome 和本机 Codex | Chrome 由用户在所选 profile 运行；Codex 必须能执行本机命令。正常 native bridge 下载不要求额外的 Codex 浏览器控制扩展；页面异常接管或手工后备才检查当前可用的浏览器工具。 |
| 来源资格 | INFORMS 必须有本人多大电子资源资格，按需完成学校登录；推荐安装 [LibKey Nomad](https://thirdiron.com/downloadnomad/) 并选择 University of Toronto，也可直接使用多大 LibKey 入口。只用 SSRN 时跳过 Nomad/学校配置。不需要 EDS/LibKey API key、OpenAlex key 或 Unpaywall 邮箱来运行这两条浏览器路线。 |

Node.js/npm 仅用于开发测试，不是安装运行依赖。Python 依赖由 uv 自动安装，无需手工安装 PDF 软件、数据库服务器或个人 EBSCO 账号。

确保后续 CLI 进程的 `PATH` 能找到 uv：`bridge prepare` 内部通过 `shutil.which('uv')` 启动构建，仅以绝对路径调用安装器还不够。可在执行命令的同一 shell 中把已经确认的 uv 所在目录加入 PATH；若工具每次开启新 shell，应在后续命令的环境中重复传入该目录，不假设上次 export 自动保留。

确认 Chrome 的 **Settings → Downloads** 中下载目录，以及 **Ask where to save each file before downloading** 已关闭。如开启，提示用户关闭后再验收。解析符号链接为真实绝对目录；不要把 `~/Downloads` 当作所有人的实际设置。扩展、Nomad、学校会话必须在同一 profile 中。不要清 cookie 或注销会话来测试。

以下命令都从仓库根目录执行。执行前将示例变量替换成已经核对的路径/ID；不要给用户留下待填写命令就称安装完成。

## 2. 安装工具和 skill

首次安装：

```sh
uv python install 3.12
uv tool install --python 3.12 .
uv tool dir --bin
```

从 `uv tool dir --bin` 返回目录找到 `utd-access-skill`。下面的 `utd-access-skill` 均指这个工具的绝对路径；确认 PATH 已可用才用裸命令。`utd-paper-access` 和 `paper-access` 是兼容旧安装的命令别名。`uv tool update-shell` 可为后续终端补 PATH，当前安装继续用绝对路径即可。

```sh
utd-access-skill install-skill
utd-access-skill doctor --json
```

预期 Python/skill 版本均为 `0.6.2.dev1`，`skill.compatible=true`。这个 doctor 核对的是包内 skill，**不是** Codex 实际发现的安装目录。另核对 `install-skill` 返回目录的文件与仓库 `skills/utd-access-skill` 一致。

默认 skill 安装目录为 `${CODEX_HOME:-$HOME/.codex}/skills/utd-access-skill`。升级自旧版本时，先把 `${CODEX_HOME:-$HOME/.codex}/skills/utd-paper-access` 和 `${CODEX_HOME:-$HOME/.codex}/skills/paper-access` 移到 `${CODEX_HOME:-$HOME/.codex}/skill-backups/` 下各自的新备份目录，避免多个 skill 重复触发；保留用户自定义内容并说明差异。新目录存在不同内容时安装器会拒绝覆盖，同一内容无需重装。

本项目未发布到 PyPI，不能执行 `pip install utd-access-skill` 或 `uv tool install utd-access-skill` 猜测安装来源。必须使用本仓库的 `.` 或已经确认来自本仓库的发布物。已有 CLI 时转到升级流程，不删除旧任务数据库或输出文件。

## 3. 加载扩展和授权

指引用户打开 `chrome://extensions` → **Developer mode** → **Load unpacked**，选择仓库根目录。给出该目录的完整路径。确认版本 `0.6.2`、实际 32 位扩展 ID，并固定 **UTD Access Skill** 到工具栏。

保留加载目录：Chrome 每次 Reload 都从该目录读源码。`bridge prepare` 生成的 `runtime/extension` 是备用快照，按本指南无需再加载它；更换目录可能改变扩展 ID，必须重新配对。已有可用的扩展更新应尽量保留原加载目录/ID并备份；不要为了整理目录直接移除用户现有扩展。

**INFORMS / EBSCO：** 已验证路线在同一 profile 安装 Nomad 并选择 University of Toronto，也可直接使用多大 LibKey 入口，按页面提示完成学校登录。UTD Access Skill 的来源权限当前通过弹窗 **后台下载这一篇** 按钮请求：在弹窗填写已知可访问的 INFORMS DOI，点击按钮并由用户接受权限。这个按钮同时启动一个独立下载任务；授权后点击 **暂停任务**，等任务停止，再提交 CLI 验收，以免与 bridge 请求重叠。已授权则不必再启动 UI 任务。详情页确认 `pubsonline.informs.org` 和 `research.ebsco.com` 允许访问。其他学校必须按本校 LibKey/EBSCO/OpenURL 配置调整和验收，不能直接复用 library 278 或多大 OpenAthens 地址。

**SSRN：** 在 UTD Access Skill 弹窗点击 **启用 SSRN 网站权限**，由用户接受 `https://papers.ssrn.com/*` 权限。此按钮不提交下载。登录或验证码仅在网站实际要求时交给用户。

Reload 不一定自动询问 optional 网站权限；不能以“没有弹窗”为权限已授予或权限失效的证据。

## 4. 建立 bridge

先记录准备好的真实值。以下目录为示例；`PA_RUNTIME` 必须尚不存在，`PA_DOWNLOAD_ROOT` 必须与 Chrome 设置相符。

```sh
PA_EXTENSION_ID="从Chrome详情页读取的32位ID"
PA_DOWNLOAD_ROOT="/已核对的真实下载目录"
PA_RUNTIME="$HOME/Library/Application Support/paper-access/bridge-runtime-0.6.2"

utd-access-skill bridge prepare \
  --destination "$PA_RUNTIME" \
  --extension-id "$PA_EXTENSION_ID" \
  --download-root "$PA_DOWNLOAD_ROOT" \
  --source-root "$PWD"

utd-access-skill bridge install --runtime "$PA_RUNTIME"
```

`prepare` 构建 wheel，创建独立 Python runtime 和扩展快照，但不登记 Chrome host。`install` 才登记 Native Messaging host。保留所用 uv 可管理的 Python 安装，不要删除其基础运行库。若使用 `PAPER_ACCESS_DATA_DIR`，准备、提交、状态查询须使用同一个值，不要无意分出两个队列。

登记后让用户在 UTD Access Skill 卡片/详情页点击 **Reload**，保持 Chrome 运行。检查：

```sh
utd-access-skill bridge doctor --json
```

必须有 `installed=true`、`connected=true`、`download_root_exists=true`，且返回的 runtime / 扩展 ID 对应刚安装的版本。`connected` 是队列的近期心跳，升级时还要确认旧 host 已关闭并 Reload；不能仅凭旧心跳证明新版本正在运行。缺少任一项先解决连接，不重复提交论文。

## 5. 真实验收

对用户实际要使用的来源各验收一篇，不要求 SSRN-only 用户取得学校资格。输出使用新的目录，保留 request_id。已知本机成功样例可参考下列命令，但不能保证别人的订阅或会话相同。

```sh
utd-access-skill bridge fetch 10.1287/mnsc.2018.3061 \
  --out "$HOME/Documents/UTD Access Skill/acceptance-informs"

utd-access-skill bridge fetch-ssrn 4189586 \
  --out "$HOME/Documents/UTD Access Skill/acceptance-ssrn"
```

按来源顺序执行，不同时提交两个独立 bridge 命令；队列为 single-flight。INFORMS 多篇在一个 `fetch-batch` 内并发，而不是启动多个 CLI 命令。

单篇 CLI JSON 的交付结果位于 `payload`。确认 `download_status=complete`、`delivered_file` 存在且 PDF 可解析、`analysis_allowed=true`；独立报告 `identity_status`。默认 advisory 允许身份未通过的可用正文继续分析。用户明确要求严格核验才使用 `--validation-policy strict`；strict 身份失败保留 PDF，但 `analysis_allowed=false`。

等待超时返回 `request_id` 时执行 `utd-access-skill bridge status <REQUEST_ID>`，不得重新提交。登录/MFA/验证码完成后继续原任务；如果任务已终止，先查明状态并告知用户，再创建有明确理由的新任务。没有主文、只得到摘要或补充材料不算验收通过。

完成后向用户交付：CLI 绝对路径、skill 路径、扩展 ID/runtime、来源验收结果和 PDF 链接。提示新开 Codex 对话加载 skill，并在以后使用时保持同一 Chrome profile 运行。若只有部分来源通过，明确该来源范围，不能笼统称全部已就绪。

## 6. 升级与恢复

先用旧 `bridge doctor` 记录 runtime / ID / 下载目录；查询活动请求，下载期间不更换登记。不知道 request_id 时可读取自己队列的非敏感任务状态，不能把数据库或临时认证链接上传。

1. 更新并备份已加载的扩展源码。先运行 `uv tool list`：若列出旧发行包 `utd-paper-access` 或 `paper-access`，分别执行 `uv tool uninstall utd-paper-access` 或 `uv tool uninstall paper-access`，再从完整新仓库执行 `uv tool install --python 3.12 .`；新包会同时提供 `utd-access-skill`、`utd-paper-access` 和 `paper-access` 三个命令。若已经列出 `utd-access-skill`，执行 `uv tool install --reinstall --python 3.12 .`。这一步不删除旧数据目录、bridge runtime、PDF 或任务数据库。随后按第 2 节备份并安装同版 skill。
2. 为新版本选尚不存在的 runtime 目录；按第 4 节 `prepare`，核对实际扩展 ID 和下载目录。暂不覆盖旧登记。
3. 无活动任务时执行 `bridge uninstall --runtime "旧runtime"`，随后 `bridge install --runtime "新runtime"`。旧登记未撤销会返回 `registration_conflict`；不得直接覆盖未知登记。
4. Reload 扩展，检查新环境并完成第 5 节真实验收；通过前保留旧源码/runtime、任务数据库、PDF。
5. 失败需恢复时，撤销新登记、还原旧扩展源码、重新登记旧 runtime，再 Reload 和检查连接。CLI/skill 也保留对应旧版本来源，避免版本不一致。

## 7. 排错和卸载

| 现象 | 检查和处理 |
| --- | --- |
| `Native host has exited` / 未连接 | 核对实际登记的 host 路径、runtime 是否存在、扩展 ID、当前 profile；Reload，必要时用弹窗 **重新连接 Codex**。不要重复安装来掩盖错误。 |
| `bridge_busy` | 查询原任务；等待或经用户意图取消原任务，不能并行提交独立请求。 |
| 浏览器有 PDF，CLI 未交付 | 检查保存位置询问、实际下载目录、文件是否完整、原 request_id 和 PDF 绑定；不要仅凭浏览器显示下载就称已完成。 |
| Forbidden / 登录 / 无全文 | 保留页面让用户处理认证，核对具体期刊年份/来源。不能直接解释成没有订阅，也不能转交 cookie 给本地程序。 |
| 身份待核对 | 保留默认 advisory 的完整 PDF 和结果；按用户选择决定是否要求 strict。 |

`doctor` 中缺 OpenAlex/Unpaywall 配置只影响相应开放后备，不阻塞 INFORMS/SSRN 浏览器路线。排错只返回必要状态和稳定入口，不展示含临时授权参数的 URL。

只撤销 bridge 登记：

```sh
utd-access-skill bridge uninstall --runtime "已经确认归属本项目的runtime路径"
```

该命令保留 runtime、PDF 和数据库。卸载 CLI 可用 `uv tool uninstall utd-access-skill`；Chrome 移除扩展、停用 skill 和删除用户数据是独立操作，按用户范围执行，不在排错过程中顺手删除。
