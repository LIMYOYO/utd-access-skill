# Paper Access

**让 Codex 读到论文正文，而不只看摘要。**

Paper Access 是一个本地运行的 Agent Skill + 浏览器连接工具。它让 Codex 使用你已有的访问资格，下载、校验并阅读 SSRN 和 INFORMS 论文正文。目前 INFORMS 自动路线适配 University of Toronto 的 LibKey/EBSCO。

[English](README.md) · [简明安装](INSTALL.zh-CN.md) · [隐私说明](PRIVACY.md) · [参与开发](CONTRIBUTING.md)

> 当前为预览版：支持 macOS + Google Chrome；INFORMS 自动路线目前限多大；SSRN 每次处理一篇。

## 快速安装

准备好 macOS、Google Chrome 和能执行本机命令的 Codex，然后把下面这段话粘贴给 Codex：

> 帮我安装 https://github.com/LIMYOYO/paper-access-router 的 Paper Access。先读 INSTALL.zh-CN.md 和 skills/paper-access/references/installation.md，完成 CLI、skill、Chrome 扩展和 native bridge 的配置。最后实际下载一篇论文验收。只有需要 Chrome 权限、学校登录、MFA 或网站验证时再让我操作。

Codex 会处理本机安装。你通常只需要：

1. 按 Codex 给出的目录，在 Chrome 中加载未打包扩展。
2. 接受扩展需要的网站权限。
3. 下载 INFORMS 时登录多大/LibKey/EBSCO；SSRN 要求验证时由本人完成。
4. 使用时保持同一个 Chrome profile 开启。

完整步骤见[简明安装指南](INSTALL.zh-CN.md)。只复制 `SKILL.md` 不能完成下载，因为运行时还需要本仓库的 CLI、扩展和本机 bridge。

## 平常怎么用

安装后不需要显式说出 skill 名称。直接提出研究问题：

```text
调查 Mobile AED 领域，找最近的 M&SOM、Management Science 和 SSRN 文章。
摘要不足以判断相关性时，下载正文并阅读相关章节。
```

也可以直接给 DOI 或 SSRN 链接：

```text
下载并阅读 https://pubsonline.informs.org/doi/10.1287/mnsc.2018.3061，
告诉我它的模型与我的模型有何不同，并给出页码证据。
```

## 能做什么

- 通过用户正常使用的 Chrome 会话下载 SSRN 单篇论文。
- 通过 University of Toronto LibKey/EBSCO 获取 INFORMS 正文。
- 一批处理最多 10 篇 INFORMS 论文，单篇失败不会拖垮整批。
- 把“PDF 下载成功”和“论文身份校验通过”分开报告。默认 advisory 模式可继续阅读身份待核对的可用 PDF；strict 模式要求两关都通过。
- 复用已有文件；版本要求允许时，可尝试开放副本。

## 权限和隐私

Paper Access 使用你已有的合法访问资格，不提供订阅，也不绕过登录、MFA、CAPTCHA、网站验证或下载限制。需要本人完成的步骤会留在浏览器中。

项目没有云端后台、统计分析、广告或账号系统，也不读取或导出密码、cookie、MFA 信息和学校凭据。PDF 与任务数据保存在本机。详见 [PRIVACY.md](PRIVACY.md)。

## 当前支持范围

| 项目 | 当前支持 |
| --- | --- |
| 系统 | macOS |
| 浏览器 | Google Chrome |
| Agent | 能执行本机命令的 Codex |
| INFORMS | University of Toronto LibKey/EBSCO |
| SSRN | 单篇请求 |
| 批量 | 每批最多 10 篇 INFORMS 论文 |

本项目已在一套 macOS + Chrome 环境中验证 INFORMS 与 SSRN 单篇、INFORMS 十篇批量和混合成功/失败隔离。新电脑仍需用自己的合法访问资格各做一次真实论文验收。其他学校及 Windows/Linux 尚未验证。

开发、测试与仓库结构见 [English README](README.md)。许可证：[MIT](LICENSE)。
