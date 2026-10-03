# 下载与校验两层关卡（0.6.2）

默认 advisory：文件完整、可解析并具备正文后即可交付/提取/分析；题名、作者、DOI 或 SSRN 编号校验失败仍保留文件，标为身份待核对。损坏、登录页、摘要、补充材料、请求/候选绑定错误仍被阻止。默认不把失败身份视为成功身份，也不把待核对文件的作者或论文归属当成事实。

用户说「严格校验」或「必须校验通过」时使用 strict：下载文件仍交付并保留，但 analysis_allowed=false，不能进入自动后续分析，直到身份通过或用户创建 advisory 新任务。任务策略固定并持久化；旧任务继续其原严格规则，不静默放宽。新任务默认 advisory。

CLI：plan、bridge fetch、fetch-ssrn、fetch-batch、experiment-pair 均支持 --validation-policy advisory|strict；Codex 代为设置，用户不用运行命令。bridge 来源可另加 --version-policy best-available|published-only；plan 用 --version。身份严格模式与正式版限定是独立选项。权限、费用、用途、正式版限定仍生效。

报告独立列出 download_status=complete|not_complete、identity_status=verified|authors_blinded|not_verified、analysis_allowed=true|false。downloaded_fulltext 表示可用正文但身份未核实；verified_fulltext 表示正文和身份均通过。默认前两种均成功交付，strict 只有后者允许分析。strict 下载数可以高于分析可用数，不能丢失文件链接或把后续来源失败覆盖为下载失败。

并行候选必须先确定对应请求，不能按完成顺序猜论文归属。无法绑定的文件不自动标成某篇成功；保持原始下载，报出绑定问题供检查。取消/断连/超时不自动重放下载；advisory已取得的正文resume时复用，strict恢复重新评估身份并采用本次结果。
