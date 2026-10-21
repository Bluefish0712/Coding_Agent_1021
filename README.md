# Coding Agent 1021

个人 DeepSeek Coding Agent 项目。当前处于 Phase 0：环境、配置和 DeepSeek API 基线。

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

Phase 1 当前已完成 DeepSeek 普通文本调用客户端和 tool calling 响应解析；Agent Loop 与工具执行将在下一步实现。

