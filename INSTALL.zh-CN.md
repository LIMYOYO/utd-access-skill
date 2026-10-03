# 安装 Paper Access

目前支持 **macOS + Chrome + 能执行本机命令的 Codex**，建议使用 Codex 桌面应用。INFORMS 自动下载目前限多大用户；SSRN 支持单篇。首次安装预留 10–20 分钟。

## 1. 交给 Codex 安装

在 Codex 中粘贴下面这段话；如果仓库已下载，也可以把链接替换为本机目录：

> 帮我安装 https://github.com/LIMYOYO/paper-access-router 的 Paper Access。先读 INSTALL.zh-CN.md 和 skills/paper-access/references/installation.md，检查已有环境，再完成依赖、CLI、skill、Chrome 扩展和 native bridge 的配置。需要 Chrome 权限、学校登录、MFA 或验证码时提示我本人操作。最后实际下载一篇论文，确认 PDF 可用后再告诉我安装完成。

不需要自己研究终端命令。Codex 会检查并补齐 **uv、Python 3.11+ 和项目依赖**；不需要 Node.js、EDS API 密钥或付费 API。仓库可用 Git 克隆，也可从 GitHub 下载 ZIP 解压。

这是公开仓库，不需要 GitHub 仓库访问权限。

## 2. 按 Codex 提示完成浏览器操作

1. 安装并打开 [Google Chrome](https://www.google.com/chrome/)，使用你平常访问论文的同一个 Chrome profile。
2. 在 `chrome://extensions` 打开 **Developer mode**，点击 **Load unpacked**，选择 Codex 给出的扩展目录；把扩展 ID 告诉 Codex。固定 **Paper Access Router** 到工具栏。
3. 按提示确认来源权限，并在 bridge 配置后点击 **Reload**。Chrome 的下载目录需与 Codex 配置一致；关闭“下载前询问保存位置”，让文件能自动落盘。
4. 下载 INFORMS 时，推荐安装 [LibKey Nomad](https://thirdiron.com/downloadnomad/) 并选择 **University of Toronto**，本人完成学校登录/MFA；Codex 也可直接使用多大 LibKey 入口。只用 SSRN 可跳过 Nomad 和学校登录。
5. 让 Codex 完成真实下载验收，然后新开一个 Codex 对话加载已安装的 skill。以后使用时保持这个 Chrome profile 运行。

不用把密码、cookie 或 MFA 码发给 Codex。Chrome 权限及本人认证操作不能仅靠复制 skill 完成。

## 3. 开始使用

在新对话中直接说：

> 调查 Mobile AED 相关文献；摘要不足以判断相关性时，下载关键论文并读正文。

也可以直接给 DOI 或 SSRN 链接。默认下载成功即可继续阅读；身份校验结果单独报告。需要严格核验时说“只有身份校验通过的论文才能用于分析”。

安装卡住、升级或手工安装时，把[Codex 安装执行指南](skills/paper-access/references/installation.md)交给 Codex。其他学校及 Windows/Linux 的浏览器自动下载尚未验收。
