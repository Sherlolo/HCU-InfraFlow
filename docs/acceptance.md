# 能力与验证范围

本仓交付包含可运行 CLI、持久 flow/team/execution、推理质量与性能验收、streaming benchmark、绑定/查询、观测与报告、全部工作流与专业 Skills（含安装检查）、测试及 CPU demo。
自动化回归验证协议和模拟 endpoint，不代表 HCU 模型精度、真实推理性能、全量多机 profile、真实多 Agent 或长期生产恢复。
TrainFlow 或 infra-agent-v2 的历史硬件结果仅作参考，不继承为本仓实测。

发布检查：运行完整测试、CPU full demo、Skill quick_validate、安装 Skill 到隔离目录、wheel 构建/隔离安装与 CLI smoke，
核对文档链接和无训练领域知识目录。目标远端使用独立环境复跑，不更改正在运行的模型服务。
实际执行证据和需求逐项结论保存在 `validation/acceptance.json` 及相邻日志，缺少的硬件验收明确记录 hardware-not-run。

## 五模块扩展（2026-11-09）

0.1.0 的验证原件保留在 validation 根目录，包含当时的源码哈希，并非当前版本清单。五模块扩展的实际使用、当前测试和文件哈希见 `validation/1109/README.md` 与 `validation/1109/summary.json`。真实旧 trace 分析、离线仿真、资料读取和新服务性能实测分别陈述。
