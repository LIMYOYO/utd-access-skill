# 开源前审查：0.6.0 预览

审查日期：2026-10-03。范围：当前工作树、将要发布的 `main` 历史、Python/Chrome 下载与校验逻辑、安装文档、wheel 和源码发布包。

结论：本轮发现的确定性发布问题已修复，可以按 **macOS + Chrome、INFORMS 多大专用适配、SSRN 单篇的实验性预览** 发布。未发现真实密钥或受限论文全文进入待提交内容。此次结论不等于跨机器真实浏览器验收或长期稳定性证明。

## 1. 已修复的问题

| 编号 | 原问题与影响 | 修复和证据 |
| --- | --- | --- |
| R1，中 | 源码包实际包含 `.serena` 本地配置和 `.planning` 临时工作记录 | `.gitignore` 排除本地配置、规划、凭证文件、PDF、数据库；`pyproject.toml` 的 sdist 使用明确文件清单。重建后源码包 116 个成员、wheel 59 个成员，检查未含这些内容 |
| R2，中 | 单篇 native host 断开后仍可继续导航或点击下载，CLI 与浏览器状态分离 | `src/native-bridge.js:131` 将断开传给单篇 controller；`src/downloader.js:152` 中断活动任务和权限待决启动，保留完整候选。3 项新回归测试分别覆盖页面检查中断、权限待决、候选保留 |
| R3，中 | 安装器接受符号链接下载目录，安全 staging 随后拒绝所有候选；doctor 却表现为目录存在 | `python/paper_access/bridge/install.py:27` 在 prepare/install/doctor 检查真实路径，明确拒绝不支持的别名。卸载独立检查登记所有权，下载目录消失时仍可卸载；新增 3 项回归测试 |
| R4，中 | 升级文档省略撤销旧登记，实际返回 `registration_conflict`；其他学校容易误用固定的多大适配 | `INSTALL.zh-CN.md` 补充新 runtime 准备、旧登记撤销、重新登记和恢复流程；说明 Library 278 固定适配、扩展 ID、真实下载目录和 CLI/浏览器连接各自职责。skill 安装引用同步修正 |
| R5，中 | 从旧基线恢复的测试缺少默认 advisory 和 strict 的完整文件交付证据 | 新增 `tests/python/test_delivery_policy.py`：生成合成 PDF，不分发论文，验证两种策略的文件保留/分析权限、报告一致性、SSRN 导入和登录页拒绝，共 6 项测试 |

同时在 native disconnect 回调读取 `runtime.lastError`，避免 Chrome 将已知连接错误报告为 unchecked；这只能改善错误处理，不能代替本地主机异常的诊断。

所有核心修复经独立只读代码审查复核。审查阶段没有替换用户运行环境；随后的小样例验收已备份旧环境、更新现有扩展并切换到当前源码构建的新 runtime，详见[真实浏览器验收](SMALL_SAMPLE_ACCEPTANCE.zh-CN.md)。

## 2. 哪些内容不应发布

凭证、会话 cookie、MFA 信息、短期带认证链接、下载的论文正文、任务数据库、`bridge-config.json` 和 `prepared.json` 都属于用户运行数据，不进入源码发布物。本轮检查的待提交文件中未发现这些真实数据；配置键名和测试中的 `private-secret` 是程序/合成测试内容。

`.serena/`、`.planning/`、虚拟环境、缓存与 `dist/` 为本地辅助内容，已忽略。构建产物如需分发，应使用经过检查的 Release 附件。

公开仓库只发布远端 `main`；未合并的本地开发分支不推送。2026-10-03 再次检查 `main` 可达对象、当前工作树和发布文件，未发现论文 PDF、任务数据库、环境文件、bridge 配置或真实 token。若以后发布其他分支或使用 `push --all`，必须单独复查对应历史。本次发布不重写历史。

Git 提交本身可能公开作者姓名/邮箱，应在提交前核对自己的 Git 身份。这属于发布者选择，不自动修改现有署名或历史。

模式扫描有检测边界，不能证明任意格式的秘密都不存在；本轮还人工核查了匹配结果、输入数据和发布包成员。

## 3. 冗余材料的处理建议

`docs/research/` 保存早期公开来源调查和元数据，可作为研究出处保留；它没有论文 PDF，且不进入 Python sdist。它不是当前全文覆盖率或机构订阅保证。

`docs/superpowers/` 和 `docs/PROJECT_PLAN.zh-CN.md` 是历史设计，保留可追溯性；后者已经明确标为历史。skill 的 `native-bridge.md` 仍有 0.3/0.4 测试时间轴，已增加当前版本与历史边界提示。后续可以把时间轴移入独立历史文档，让 agent 日常只读当前接口。

`experiment-pair` 和 pair 实现是早期实验接口，和当前 batch 路线重叠。暂时保留以兼容旧任务；后续标记弃用、迁移旧调用后再移除，不在开源前直接删除有恢复价值的代码。

## 4. 尚未完成的优化

1. SSRN 浏览器 controller 的验证码等待、重复候选和重连尚缺直接自动化测试；本轮补齐的是 SSRN 本地导入与策略层。后续优先补这类回归和 macOS/Linux CI。
2. 单篇/双篇/批量 controller 存在重复逻辑，部分代码较密集。稳定接口后统一格式，并逐步共享状态转换；现在不做大范围重构。
3. `doctor` 的 skill 兼容性检查核对的是安装包随附的 skill；不保证 Codex 实际发现的 skill 目录内容已经更新。安装文档要求单独安装并新开对话，后续可增加已安装 skill 路径/版本诊断。
4. 其他学校与 Windows/Linux native bridge 未经本项目验收；INFORMS DOI 前缀匹配不代表所有 INFORMS 期刊都具备完整下载或正式版识别能力。

## 5. 当前验证证据

- Python：218 passed、4 skipped。4 项真实 PDF 回放需要自备固定样本，并设置 `PAPER_ACCESS_ACCEPTANCE_DIR`；它们没有作为成功项计入。
- JavaScript：56 passed；全部 JavaScript 语法检查通过。
- Skill：quick_validate 通过；wheel 携带同版本 skill。
- 依赖：pip-audit 查询了 25 个第三方包，没有报告已知漏洞；本地未发布的 paper-access 不在 PyPI，已由代码审查覆盖，不能按数据库结果宣称它无漏洞。
- 发布物：wheel 与 sdist 构建成功，不包含本地配置、规划、PDF、数据库或环境文件。
- 从 sdist 解压后安装进独立环境：doctor、同版 skill 安装、6 项安装 smoke 场景、native runtime 准备成功。
- `git diff --check` 通过。

上述安装 smoke 的来源响应为合成 fixture。后续[真实浏览器小样例验收](SMALL_SAMPLE_ACCEPTANCE.zh-CN.md)另完成了 3 篇 INFORMS 和 1 篇 SSRN 的实网下载、一个并行失败隔离样例及非法输入拒绝，均符合预期。跨机器安装、失效学校会话和验证码仍需要使用者按安装文档验收。

## 6. 提交范围

公开发布只推送经过检查的 `main`。不使用 `push --all`，不上传本地运行数据，也不清理用户已下载文件。
