# Paper Access

Paper Access 是一个供 Codex 调用的本地论文获取工具。它把 Python CLI、Chrome 扩展、本机 Native Messaging bridge 和 `paper-access` skill 放在同一个仓库里。

当前版本：Python/skill `0.6.0.dev1`，Chrome 扩展 `0.6.0`。

这是面向 macOS + Chrome 的实验性开源预览。INFORMS 自动下载适配当前固定为 University of Toronto；其他学校可使用手工 LibKey 路由，尚未提供对应自动适配。SSRN 自动入口当前支持单篇。

## 现在能做什么

- 在文献调查、相关性判断和模型比较中自然触发，不要求用户记住 skill 名称。
- 通过已登录 Chrome 获取单篇 SSRN 正文。
- 通过 LibKey Nomad、University of Toronto 和 EBSCO 获取 INFORMS 正文。
- INFORMS 一次提交最多 10 篇，并将单篇失败与其他任务隔离。
- 将“PDF 已完整下载”和“论文身份已核验”分开报告；默认允许阅读已下载但身份待核对的正文。
- 对开放来源执行 DOI/BibTeX/RIS/CSV 规划、下载、缓存、恢复和报告。

本工具使用用户已有的合法访问资格，不保存学校密码、MFA、Chrome cookie，也不绕过登录、人机验证、订阅或下载限制。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `python/paper_access/` | Python CLI、任务数据库、来源适配、校验和 native bridge |
| `src/`、`manifest.json` | 可由 Chrome **Load unpacked** 加载的扩展 |
| `skills/paper-access/` | 与本版本配套的 Codex skill |
| `profiles/providers/capabilities.json` | 来源能力边界 |
| `tests/` | Python 与扩展自动化测试 |
| `docs/` | 设计、访问调查和测试证据 |

## 安装

从[简明安装指南](INSTALL.zh-CN.md)开始；详细命令、授权、升级和排错见[Codex 安装执行指南](skills/paper-access/references/installation.md)。可把本仓库链接交给 Codex，再复制：

> 帮我安装这个仓库的 Paper Access。先读 INSTALL.zh-CN.md 和 skills/paper-access/references/installation.md，完成安装并实际下载一篇论文验收；需要 Chrome 权限或本人认证时提示我操作。

## 日常使用

安装完成后无需显式说“使用 paper-access”。下面这些请求会在需要正文时自然调用：

- “调查 Mobile AED 领域，确认哪些论文真的相关。”
- “这篇文章和我的模型到底哪里相似？”
- “找最近的 M&SOM、Management Science 和 SSRN 文章，摘要不够时读正文。”
- “下载 DOI 10.1287/mnsc.2018.3061。”

用户明确只要摘要、书目信息或链接时，不会为了凑数量自动下载论文。

## 开发验证

开发测试另需 Node.js/npm；日常安装与下载不需要。

```sh
uv sync --dev
uv run pytest
npm test
```

构建 wheel 并核对 skill 版本：

```sh
uv build --wheel
uv run paper-access doctor --json
```

真实浏览器验收需要 Chrome、正确的扩展 ID、用户自己的学校访问资格，以及本人完成登录/MFA。自动化测试不替代真实来源验收。四项真实 PDF 回放测试需要使用者自行提供合法获得的固定样本，并通过 `PAPER_ACCESS_ACCEPTANCE_DIR` 指定目录；默认跳过，仓库不附带论文全文。

## 已验证边界

本机 macOS + Chrome 已验证 INFORMS 单篇、十篇并发与失败隔离，以及 SSRN 单篇流程。其他电脑需按安装文档各做一篇真实验收。支持某个入口不表示每篇论文都有订阅，也不表示身份校验必然通过。

许可证：[MIT](LICENSE)。隐私说明：[PRIVACY.md](PRIVACY.md)。
