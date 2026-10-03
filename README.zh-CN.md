# UTD Paper Access

**让 AI 研究助手读到论文正文，而不只看摘要。**

UTD Paper Access 是一个本地运行的 Agent Skill + Chrome 连接工具，用来获取并阅读 **UTD Top 24 商学院期刊**和相关 SSRN 工作论文。它只使用用户自己已有的访问资格。

[English](README.md) · [简明安装](INSTALL.zh-CN.md) · [隐私说明](PRIVACY.md) · [参与开发](CONTRIBUTING.md)

> **这里的 UTD 指 University of Texas at Dallas 的 Top 24 期刊集合，不是 University of Toronto。** University of Toronto（多大）只是当前已经验证的 INFORMS LibKey/EBSCO 机构路线。最新期刊范围以 [UT Dallas 官方清单](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/index.php)为准。

## 快速安装

当前需要 macOS、Google Chrome 和能执行本机命令的 Codex。把下面这段话粘贴给 Codex：

> 帮我安装 https://github.com/LIMYOYO/utd-paper-access 的 UTD Paper Access。先读 INSTALL.zh-CN.md 和 skills/utd-paper-access/references/installation.md，完成 CLI、skill、Chrome 扩展和 native bridge 的配置。对我需要使用的每条路线，最后实际下载一篇论文验收。只有需要 Chrome 权限、学校登录、MFA 或网站验证时再让我操作。

Codex 会处理本机安装。用户通常只需要加载未打包扩展、批准网站权限、按需完成本人学校认证，并在使用时保持同一个 Chrome profile 开启。

只复制 `SKILL.md` 不能完成下载，因为浏览器路线还需要本仓库的 CLI、扩展和 native bridge。新命令是 `utd-paper-access`；为了兼容已有安装，旧的 `paper-access` 命令、数据目录和 native bridge 标识继续保留。

## 平常怎么用

安装后不需要显式说出 skill 名称：

```text
调查 Mobile AED 领域最近的 UTD Top 24 和 SSRN 论文。
摘要不足以判断相关性时，下载正文并阅读相关章节。
```

也可以直接提供 INFORMS DOI 或 SSRN 链接。

## UTD Top 24 覆盖情况

UTD 官方排名目前追踪 24 本期刊。本项目**还没有为全部 24 本期刊提供出版社自动下载路线**。

| 覆盖状态 | 期刊或来源 | 当前能力 |
| --- | --- | --- |
| 有专用浏览器自动路线 | **Information Systems Research、INFORMS Journal on Computing、Marketing Science、Management Science、Operations Research、Manufacturing & Service Operations Management、Organization Science** | INFORMS DOI → LibKey → 多大/EBSCO → 本地 PDF。INFORMS 每批最多 10 篇；每篇单独报告订阅、下载和身份校验结果。 |
| 支持开放副本和本地文件 | 全部 24 本期刊 | 可复用用户已有的合法 PDF；版本要求允许时，可尝试稳定的开放仓库副本，但不保证一定存在。 |
| 工作论文路线 | SSRN；SSRN 本身不属于 UTD Top 24 期刊 | 支持 Chrome 单篇下载，下载成功和论文身份校验分开报告。 |
| 暂无出版社专用自动路线 | **The Accounting Review、Journal of Accounting and Economics、Journal of Accounting Research、Journal of Finance、Journal of Financial Economics、Review of Financial Studies、MIS Quarterly、Journal of Consumer Research、Journal of Marketing、Journal of Marketing Research、Journal of Operations Management、Production and Operations Management、Academy of Management Journal、Academy of Management Review、Administrative Science Quarterly、Journal of International Business Studies、Strategic Management Journal** | 目前只能使用开放副本、已有本地 PDF，或由用户在浏览器完成合法下载后导入。 |

## 支持状态和后续路线

| 能力 | 当前状态 | 后续计划 |
| --- | --- | --- |
| UTD24 中的 7 本 INFORMS 期刊 | 已验证多大 LibKey/EBSCO 路线 | 随出版社和 EBSCO 页面变化持续增强稳定性。 |
| 其他学校 | 已能根据学校名称、LibKey library ID、OpenAthens 域名和 OpenURL resolver 生成入口 | 增加学校 profile 和可配置 EBSCO tenant。现在需要使用者根据本校订阅调整路线，并用一篇真实论文验收。 |
| SSRN | 支持单篇 | 单篇路线积累更多稳定样本后，再增加受控批量。 |
| 其他 17 本 UTD24 期刊 | 仅开放副本、本地导入或人工合法下载 | 按出版社分组逐步增加路线，不提前宣称全部支持。 |
| 系统与浏览器 | macOS + Google Chrome | 后续验证 Windows/Linux 和其他 Chromium 浏览器；当前不支持 Firefox。 |
| 补充材料、数据集和代码 | 没有专用获取路线 | 先定义文件类型和校验规则，再考虑自动化。 |

## 研究用途声明

UTD Paper Access 的目的，是让 AI 研究助手能够阅读**用户已经依法有权访问**的论文，帮助个人研究判断、文献综述和模型比较。它不是论文传播或分发工具。

不得用它绕过订阅、登录、MFA、CAPTCHA、网站验证、速率限制或许可条款；不得超出本人授权批量下载；不得重新分发、公开分享或重新发布取得的 PDF。机构提供的阅读权限，也不自动等于再分发、文本与数据挖掘或 AI 处理权限。使用者需要遵守本校图书馆和出版社的适用条款。

项目没有云端后台、统计分析、广告或账号系统，也不导出密码、cookie、MFA 信息和学校凭据。PDF 与任务数据保存在本机。详见 [PRIVACY.md](PRIVACY.md)。

本项目已在一套 macOS + Chrome 环境中验证 INFORMS 与 SSRN 单篇、INFORMS 十篇批量和混合成功/失败隔离。新电脑和新学校仍需使用自己的合法访问资格，各做一次真实论文验收。

许可证：[MIT](LICENSE)。
