# Coding Agent 1021

个人 DeepSeek Coding Agent / Harness 学习与实践项目。s01–s17 的核心学习阶段已完成，并已在本项目中实现 Agent Loop、工具系统、权限与 Hooks、任务和记忆、子 Agent 与团队、MCP、集成 Harness、Workflow Runtime 和 Goal Loop 等组件。当前重点是核对实现边界、补齐可靠性与评测，并规划知识检索（RAG）等后续实践；这不代表所有组件已达到生产级。

## 安全提醒

把 API Key 写入本地 `.env`，不要提交 `.env`。项目只使用 DeepSeek 原生 API 的 OpenAI-compatible Chat Completions 端点，不使用 Anthropic SDK 或 Anthropic 兼容接口。

## 本地设置

```powershell
cd D:\GITHUBPROJECTS\AGENTPROJ_PERSONAL\Coding_Agent_1021
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
python -m personal_agent.cli doctor
pytest
# 配置 .env 后的真实 API 冒烟测试
python -m personal_agent.cli chat "用一句话说明什么是 Agent Loop"
```

## 当前实现概览

- **模型接口：** 使用 DeepSeek OpenAI-compatible Chat Completions API。
- **Agent Harness：** 已实现循环执行、工具注册与调用、文件和命令工具、权限策略与 Hooks。
- **上下文与协作：** 已实现 Todo、Subagent、Skills、上下文压缩、跨会话记忆、持久任务、后台任务、调度器和 Agent Teams。
- **扩展与运行：** 已实现 MCP 工具接入抽象、集成 Harness、Workflow Runtime 和 Goal Loop。
- **验证：** 仓库包含对应的模块测试；本 README 不声明这些测试在每次更新时均已运行，也不将模拟 MCP transport、示例 Workflow 等当前边界描述为生产级能力。

详细阶段记录、架构说明和已知限制见 [CodingAgent开发文档.md](./CodingAgent开发文档.md)。

后续优化路线、s18 数据集评测和 s19 项目知识检索（RAG）入口见 [Agent项目优化路线图.md](./Agent项目优化路线图.md)。

### 本地评测与知识检索

```powershell
# 离线检查评测集结构，不访问模型 API
python -m personal_agent.cli eval --dry-run

# 明确选择真实模型后运行任务评测（会调用 DeepSeek API）
python -m personal_agent.cli eval --real-model --task python-verifier --repeats 3

# 对当前项目代码/文档运行检索 Recall@k 与 MRR 评测
python -m personal_agent.cli eval --retrieval-dataset evals/retrieval.json --top-k 5
```

Agent 任务评测结果默认追加到 `.agent-data/evals/results.jsonl`；该目录作为本地运行数据，不应提交。真实模型评测需配置 `.env`，并会产生 API 调用和费用。当前知识检索使用本地稀疏检索与确定性特征哈希相似度基线，不是神经 embedding 服务；先用检索评测判断收益，再考虑接入 embedding。

