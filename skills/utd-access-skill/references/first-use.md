# UTD Access Skill 首次使用准备与检查

面向安装者和执行 Codex：用户无需学习终端命令；可由 Codex 检查和安装本地组件，用户只处理需要本人确认的扩展权限及学校认证。不能仅复制 SKILL.md 就宣称可下载。

## 需要准备什么

| 项目 | 是否需要 | 如何准备与验收 |
| --- | --- | --- |
| 可执行本地 CLI 的 Codex 环境 | native bridge 主路线必需 | 通过 shell 调用已安装工具即可提交正常下载。Codex 通用浏览器连接用于异常接管和手工后备，验收是能列出并读取目标 Chrome 标签页；连接就绪的 native bridge 不依赖 GPT 逐页操作。普通网页 ChatGPT 或纯 API 不自动具备本机 CLI/浏览器能力。 |
| 桌面 Chrome 与同一用户配置 | 本方案已验证环境 | 打开计划用于学校访问的 Chrome 配置，保持运行。连接扩展、Nomad 和学校登录都应在这个配置中；其他配置或应用内浏览器不会自动继承登录。无需照抄别的项目启用远程调试端口；只按当前浏览器工具的正式连接方法配置。 |
| LibKey Nomad | 推荐，已验证入口使用它 | 从 [Third Iron 官方下载页](https://thirdiron.com/downloadnomad/) 进入对应浏览器的官方扩展商店安装，打开扩展并选择 University of Toronto。别的学校选自己的机构。它负责提供全文入口，不负责给 Codex 浏览器控制权，也不授予订阅权限。缺少时仍可走 LibKey/图书馆入口，不能说必须安装才能访问。 |
| 学校电子资源资格与登录 | 订阅内容需要 | 用有资格的本人学校账号。在上述 Chrome 中经学校图书馆入口打开资源，按提示本人完成本校账号/MFA（多大为 UTORid）。推荐初次先登录以减少中断，但不要求每次提前登录；未登录时 Codex 可引导至登录页，完成后继续。不能以 Nomad 选中了学校当作已经认证。 |
| UTD Access Skill CLI、同版 skill、扩展与 native bridge | 浏览器自动获取、校验和任务记录需要 | Codex 执行 `utd-access-skill doctor --json` 与 `utd-access-skill bridge doctor --json`；CLI/skill 版本匹配，且 bridge 返回 installed=true、connected=true 才算本机连接就绪。旧命令 `utd-paper-access` 和 `paper-access` 可继续用于已有安装。缺失时按 installation.md 从完整仓库安装。任何一个组件单独存在都不等于自动下载已就绪。 |

本工具运行要求 Python3.11+；使用 uv 安装时需要本机有 uv。由 Codex 检查已有环境，缺失时使用 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)；不要编造包索引发布或要求用户自己研究命令。浏览器获取端到端目前只在 macOS＋Chrome 实测；Linux只验证了本地工具安装，Windows浏览器链路未验收。

## 首次调用时 Codex 的检查顺序

1. 先确认所需来源，检查 doctor 和输出目录可写。仅用 SSRN 不要求学校、Nomad 或学校登录；需要 INFORMS 机构入口时再从用户上下文确认学校。已有配置不重复安装，不自动替其他使用者选择多大。
2. 优先检查 native bridge；就绪时使用 CLI。需要页面异常接管或手工后备时再检查通用浏览器连接是否能读取目标 profile；不可用时说明该后备能力缺口，不把它判为正常 CLI 路线不可用。
3. 检查论文页面的 Nomad 学校按钮，或通过扩展界面确认所选机构。按钮未出现时先检查是否选对学校、页面是否有 DOI、扩展是否在当前配置启用；不直接判定没订阅。扩展安装和权限确认按当前工具要求处理。
4. 用用户实际需要的一篇论文测试学校路线。遇到认证页请用户本人完成，保留页面继续；不要求发送密码、MFA、cookie 或会话文件。不要为了测试注销已有会话、清空 cookie 或关闭安全保护。
5. 下载后检查文件真实落盘：bridge 已自动导入并校验，读取其 payload/report，不重复 import-file；手工浏览器路线才自行执行 import-file。报告工具连接、正文下载可用和身份核对结果；用到通用浏览器工具时另报其连接状态。默认只要求正文下载关卡通过即可分析；strict 另要求身份通过。参见 [下载与校验策略](delivery-policy.md)。

## 常见缺口怎么处理

- **有 Nomad，Codex 看不到 Chrome**：正常已连接的 native bridge 仍可运行；需要手工后备时才解决浏览器控制连接。
- **能看到 Chrome，但跳转登录**：同一配置中完成学校认证；不要退回要求 OpenAlex key。
- **已登录仍没有正文**：核对具体期刊/年份/记录及学校其他来源；可能是覆盖范围或链接问题，不能一概称登录失败。
- **浏览器显示下载完成但工具找不到文件**：查看该文件的“在 Finder/文件夹中显示”；下载目录可能是外置盘。不要再下载一次来猜位置。
- **缺 OpenAlex key / Unpaywall 邮箱**：仅影响相应开放后备，不阻塞 LibKey/EBSCO 主路线。普通浏览器获取不需要 EDS API 凭据，也不要求另建个人 EBSCO 账号。

自动 bridge 路线必须加载本仓库的 UTD Access Skill 扩展。LibKey Nomad 负责学校全文入口，Codex 浏览器连接负责通用页面操作，UTD Access Skill 负责请求队列、下载绑定和本地主机通信；三者职责不同，不能互相替代。若 bridge 未安装，Codex 仍可在浏览器中人工执行单篇路线，但必须明确这是降级操作。

## 官方依据与验证边界

核对日期2026-09-29。Nomad 安装后选择机构、无需 Nomad 个人账号：[Third Iron FAQ](https://support.thirdiron.com/support/solutions/articles/72000569997-libkey-nomad-technical-faq)。多大通过 OpenAthens、按提示 UTORid 登录：[多大电子资源访问说明](https://library.utoronto.ca/use/how-to/access-electronic-resources)；[多大 Nomad 页面](https://library.utoronto.ca/use/tool/libkey-nomad)。

应用浏览器连接要求来自当前工具提供的能力说明和本机已完成的实测，不是通用版本安装教程。新机器仍须现场检查；不承诺安装完扩展即具有全部期刊访问权。
