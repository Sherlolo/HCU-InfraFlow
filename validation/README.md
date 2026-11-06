# 2026-11-07 交付验收

- `acceptance.json`：原需求六项映射、源码 SHA256、验证范围与限制。
- `base-reuse.json`：十二个 TrainFlow 派生模块的原件哈希、当前哈希与相似度。
- `pytest.log`：目标容器 Python 3.10.12，202 passed、2 个 Windows 专属 skip；Store/临时文件位于容器本地专属目录。
- `pytest-nfs-interrupted.log`：共享盘并发测试等待后主动中断，不计为通过。
- `bootstrap.log`：离线、项目独立 venv 安装，不修改系统包或模型依赖。
- `demo.json` / `demo-report.html`：真实 CPU 子进程和合成推理证据的完整工作流；reviewer 为 fixture，不是实际独立 Agent。
- `bindings*.json`：真实外部入口与哈希；LightOp 采用显式本地绑定。
- `knowledge-native.json`：原生知识索引查询未成功。
- `knowledge-discovery.json`：只读 tracked Markdown 部分检索结果，保留正文行号与哈希，不代表全量索引或正文结论已验证。
- `skills-install.json` / `structure.json`：六个自有 Skill 的隔离安装与结构校验。
- `wheel-build-local.log` / `wheel-smoke-local.json`：最终 wheel 构建、隔离安装及 CPU 全流程验证。

复跑 Linux 回归（仅 CPU，不占用 GPU）：

```bash
docker exec --workdir /public/home/yangyn1/work_space/2026/agent/hcu-infra-agent \
  -e TMPDIR=/tmp/hcu-infra-agent-1107-validation \
  -e PYTHONDONTWRITEBYTECODE=1 yangyn_sglang_plugin_1022 \
  .venv/bin/python -m pytest -q -rs
```

该容器默认 root 有现成用户记录；以宿主 UID 1156 运行 OpenSSH 配置解析测试会因容器没有同 UID 账户而失败。
测试不需要、也不会修改容器账户。硬件推理、真实多 Agent、通知送达、长期恢复尚未在本仓验收。
