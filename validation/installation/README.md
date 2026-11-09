# 安装与官方 Cookbook 接入验证

本次版本 0.3.0：Cookbook 固定为 HYGON-AI/inference-cookbook-das 官方 HTTPS 查询；不需要知识库，也不回退到知识镜像。
`cookbook-official.json` 是真实官方查询和固定提交正文/相关链接；网络接口单元测试使用明确的 mock。

`simtools-fetch.json`：从用户指定 OpenDAS/DCUSimTools 获取到任务专属目录，记录 revision 和可用 wheel。
`fetched-simtools-install.log`：将该获取结果安装在独立 Python 3.10 环境；`fresh-simulation.json` 记录实际离线仿真。
没有将原生 wheel 或新 clone 的仓库加入本仓 Git。

`doctor.json`：在选定容器中检查实际组件，使用新安装的 simulation_python、既有服务解释器，以及用户已有的手动知识库。
知识库没有被获取、更新或重建；目录存在检查不等于完整知识内容、在线权限或模型验收。
容器检测和用户声明分开记录；没有升级镜像、修改共享服务环境或执行 GPU 测量。

`pytest.log`：219 passed，2 个 Windows 路径语义专属 skip。
`skills-install.json`：七个自有 Skill 在任务隔离目录安装，包括 hcu-infra-agent-install。
README 回归检查确认无个人目录、个人 SSH 别名或个人容器名。
