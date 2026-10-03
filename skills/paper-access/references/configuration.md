# 安装与配置

首次安装先读 [安装与升级](installation.md) 和 [首次使用准备](first-use.md)，它们区分本地 bridge、浏览器连接、Nomad 和学校认证；本页补充运行配置。

需要 Python 3.11+。工具和 skill 使用同一份发布包；在仓库根目录运行 `uv tool install .`，再运行 `paper-access install-skill` 安装随包附带的同版 skill，随后新开 Codex 会话加载。

本项目尚未上传包索引，不要安装同名 PyPI 包或猜测下载地址。优先从包含 `pyproject.toml`、`python/paper_access`、`src`、`manifest.json` 和 `skills/paper-access` 的完整仓库安装。若只收到 skill 或 wheel，明确报告缺少完整浏览器组件；不能声称已具备 INFORMS/SSRN 自动下载。

`OPENALEX_API_KEY`、`UNPAYWALL_EMAIL` 可通过当前运行环境配置，值不写入任务/报告。邮箱必须由用户提供，不编造；不要求把 key 发到聊天。这些配置仅用于开放后备，不是多大浏览器主路线的前置条件。

数据默认保存在 macOS 的 `~/Library/Application Support/paper-access`、Linux 的 `$XDG_DATA_HOME/paper-access` 或 `~/.local/share/paper-access`、Windows 的 `%LOCALAPPDATA%/paper-access`。`PAPER_ACCESS_DATA_DIR` 可覆盖。保留同一数据目录以查找已有 job；不要为了重试创建新状态目录。

学校配置是可选 JSON，传 `plan --institution <路径>`。字段：`institution_name`、`resolver_base_url`（HTTPS OpenURL 地址）、`libkey_library_id`（数字）、`openathens_domain`。UofT 可使用 `{"institution_name":"University of Toronto","openathens_domain":"utoronto.ca"}`；不要套用给别的学校。

输出包括 files、text、manifest.jsonl、report.html/csv、pending.html/csv。数据库与文件要一起保留，续跑会检查原文件。删除前让用户明确选择范围。
