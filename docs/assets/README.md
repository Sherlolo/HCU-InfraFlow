# 工作流总览图

总览图参考 HCU-TrainFlow README 的“统一主控 + 三阶段分栏 + 贯穿能力”表达方式，节点、工具和验收条件按 HCU Infra Agent 当前实现重新整理，未复制训练的 loss、反向或 checkpoint 验收语义。

- [workflow-overview.png](workflow-overview.png)：3200×2280，用于 README 的稳定显示。
- [workflow-overview.svg](workflow-overview.svg)：1600×1140 的可缩放矢量图，带标题与描述。
- [生成脚本](../../scripts/render_workflow_overview.mjs)：图形、文案、颜色与布局的可编辑来源；版本号读取 pyproject.toml。

图中的关键约定来自[架构](../architecture.md)、[模块指南](../modules.md)及[模型优化闭环](../model-optimization-loop.md)。主控由宿主 Agent 会话承担，执行与恢复设施按现场绑定；仿真、工具报告与实际模型验收各有范围。

## 再生成

仅生成 SVG 需要 Node.js：

```bash
node scripts/render_workflow_overview.mjs --svg-only
```

同时生成 README PNG 时，在私有工具目录安装渲染器，并提供可用的中文字体：

```bash
npm install --prefix .work/workflow-render @resvg/resvg-js@2.6.2 --no-audit --no-fund
node scripts/render_workflow_overview.mjs --font /path/to/NotoSansCJK-Regular.ttc
```

`--font` 可重复指定；未指定时使用系统字体。不同字体可能影响字宽，重新生成后应检查文字、连线和边界。渲染依赖只用于文档工具，不加入 HCU 推理运行依赖。修改文案时同时更新生成脚本、SVG 和 PNG。
