# Coding Agent 开发与学习文档

> 项目路径：`D:\GITHUBPROJECTS\AGENTPROJ_PERSONAL\Coding_Agent_1021`  
> 参考项目：`D:\GITHUBPROJECTS\learn-claude-code`  
> 当前模型：DeepSeek API / `deepseek-flash`  
> 当前阶段：Phase 1 —— DeepSeek 客户端基线已完成，下一步实现 Agent Loop

## 0. 文档目的

这不是普通的开发日志，而是本项目的“开发过程教材”。每完成一个功能，都要同时回答四个问题：

1. 这个功能解决了什么实际问题？
2. 代码是怎样运行的，数据经过了哪些模块？
3. 为什么采用当前方案，还有哪些替代方案？
4. 为了真正理解它，需要补充哪些 Python、网络、操作系统或 Agent 知识？

目标不是只得到一个能运行的 Coding Agent，而是最终能够由本人讲清楚：

```text
用户输入
→ Agent Loop
→ DeepSeek 判断下一步行动
→ Tool Calling
→ 本地工具执行
→ 工具结果返回模型
→ 模型继续行动或结束
```

## 1. 项目原则

### 1.1 独立开发

本项目代码全部位于当前项目目录，不复制 `learn-claude-code` 的实现。参考项目只用于：

- 学习 Agent Loop 和 Harness 设计
- 对照章节概念
- 阅读示例和实验思路
- 验证自己对架构的理解

### 1.2 完全使用 DeepSeek API

本项目直接使用 DeepSeek 的 OpenAI-compatible Chat Completions API：

```text
POST https://api.deepseek.com/chat/completions
```

项目不使用 Anthropic SDK，也不通过 Anthropic 兼容接口调用 DeepSeek。

配置位于本地 `.env`，该文件已加入 `.gitignore`，不能提交到 Git：

```env
DEEPSEEK_API_KEY=本地密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=60
```

### 1.3 先理解，再抽象

前期优先使用小模块和清晰数据流，不提前建立复杂的 Provider、Runtime、Event Bus 或插件系统。只有当真实需求重复出现时，才提取抽象。

### 1.4 Mock 优先，真实 API 辅助

普通测试不消耗 API 配额。只有显式执行真实冒烟测试时才调用 DeepSeek：

```powershell
python -m personal_agent.cli chat "用一句话说明什么是 Agent Loop"
```

## 2. 当前项目结构

```text
Coding_Agent_1021/
├─ .env                  # 本地密钥，不提交
├─ .env.example          # 配置模板，不包含密钥
├─ .gitignore
├─ pyproject.toml        # 项目元数据、依赖、pytest 配置
├─ README.md             # 快速开始
├─ CodingAgent开发文档.md # 本文档
├─ src/
│  └─ personal_agent/
│     ├─ __init__.py
│     ├─ cli.py           # 命令行入口
│     ├─ config.py        # 环境变量和配置对象
│     └─ deepseek_client.py # DeepSeek HTTP 客户端
└─ tests/
   ├─ test_config.py
   └─ test_deepseek_client.py
```

## 3. 已完成进度

### 3.1 Phase 0：环境与项目基线

状态：已完成。

完成内容：

- 在独立目录创建项目
- 使用 Python 3.12.10
- 创建 `.venv`
- 安装 `httpx`、`python-dotenv`、`pytest`
- 建立 `pyproject.toml`
- 建立 `.env.example`
- 建立 `.gitignore`
- 初始化 Git
- 创建 GitHub 远程仓库并同步
- 验证 API Key 不进入 Git

关键知识：

#### 虚拟环境

虚拟环境用于隔离项目依赖。即使两个项目都使用 Python，也可以安装不同版本的第三方库而互不影响。

```text
系统 Python
  ├─ 项目 A 的 .venv
  └─ Coding Agent 的 .venv
```

#### `pyproject.toml`

它是现代 Python 项目的统一配置文件，负责描述：

- 项目名称和版本
- Python 版本要求
- 运行依赖
- 开发依赖
- CLI 入口
- pytest 配置

#### `.env` 与 `.env.example`

`.env` 保存本机秘密，`.env.example` 只保存变量名和非敏感默认值。两者不能混用。

#### Git 与 GitHub

Git 保存本地版本历史，GitHub 保存远程副本。`commit` 是本地记录，`push` 才是上传到远程仓库。

### 3.2 Phase 1：DeepSeek 客户端基线

状态：已完成。

本阶段提交：

```text
f292076 feat: add native DeepSeek chat client
```

已完成内容：

- 普通文本请求
- DeepSeek 原生 Chat Completions URL
- Bearer Token 请求头
- 模型配置
- Tool Calling 参数发送
- Tool Calling 响应解析
- HTTP 错误包装
- 无效响应格式处理
- CLI `chat` 命令
- Mock HTTP 测试
- 一次真实 API 冒烟测试

测试结果：

```text
4 passed
```

## 4. Phase 1 代码导读

### 4.1 `config.py`：配置从哪里来

核心对象：

```python
@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    timeout_seconds: float = 60.0
```

运行过程：

```text
load_dotenv()
→ 读取 .env
→ os.getenv()
→ 生成 Settings
→ 客户端使用 Settings
```

为什么使用不可变配置对象？

- 配置加载集中在一个地方
- 其他模块不需要到处读取环境变量
- `frozen=True` 可以避免运行过程中意外修改配置
- 测试时可以直接构造测试配置

### 4.2 `deepseek_client.py`：如何发送请求

客户端完成四件事：

1. 检查 API Key 是否存在。
2. 组装 DeepSeek 请求 JSON。
3. 发送 HTTP 请求。
4. 把响应转换为项目内部的 `ChatResponse`。

请求的最小结构：

```json
{
  "model": "deepseek-flash",
  "messages": [
    {"role": "user", "content": "hello"}
  ]
}
```

带工具时增加：

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "parameters": {}
      }
    }
  ],
  "tool_choice": "auto"
}
```

模型可能返回普通文本：

```json
{
  "message": {
    "role": "assistant",
    "content": "hello"
  },
  "finish_reason": "stop"
}
```

也可能返回工具调用：

```json
{
  "message": {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_1",
        "type": "function",
        "function": {
          "name": "read_file",
          "arguments": "{\"path\":\"README.md\"}"
        }
      }
    ]
  },
  "finish_reason": "tool_calls"
}
```

注意：当前客户端只负责“发送”和“解析”，还不负责执行工具。工具执行属于下一步 Agent Loop。

### 4.3 `cli.py`：用户如何触发代码

普通调用链：

```text
PowerShell
→ python -m personal_agent.cli chat "..."
→ main()
→ chat(prompt)
→ load_settings()
→ DeepSeekClient.chat()
→ print(response)
```

`doctor` 不调用模型，只检查本地配置；`chat` 才会发起真实 API 请求。

### 4.4 `test_deepseek_client.py`：为什么需要 Mock

测试使用 `httpx.MockTransport` 拦截请求，因此不会访问网络，也不会消耗 API 配额。

测试验证：

- URL 是否正确
- Authorization 是否正确设置
- 模型是否正确
- tools 是否进入请求
- 普通消息是否能解析
- tool call 是否能解析
- HTTP 401 是否转换成项目异常

这体现了一个重要原则：测试不应依赖模型每次生成完全相同的自然语言，而应该验证协议和程序行为。

## 5. 当前还没有实现什么

目前还不是完整 Coding Agent，缺少：

- Agent Loop
- 工具注册表
- 文件读取工具
- 代码搜索工具
- 文件修改工具
- Shell 执行工具
- 工作区边界保护
- 用户审批
- 测试执行与结果回传
- 会话历史管理
- 任务恢复

当前客户端能够理解 tool call 的数据，但还不会根据 tool call 自动执行动作。

## 6. 下一步：Agent Loop

下一步目标是实现一个最小循环：

```text
1. 收集用户问题
2. 请求 DeepSeek
3. 如果是普通文本，输出并结束
4. 如果是 tool_calls，解析工具名和参数
5. 找到对应工具函数
6. 执行工具
7. 把 assistant 消息和 tool 消息加入 messages
8. 再次请求 DeepSeek
9. 重复直到模型结束或达到最大轮数
```

伪代码：

```python
messages = [{"role": "user", "content": user_input}]

for _ in range(max_turns):
    response = client.chat(messages, tools=tool_schemas)
    messages.append(response.message)

    tool_calls = response.message.get("tool_calls", [])
    if not tool_calls:
        return response.message.get("content", "")

    for call in tool_calls:
        result = registry.execute(call["function"]["name"], call["function"]["arguments"])
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })
```

### 6.1 需要补充的知识

- `while`/`for` 循环和终止条件
- Python 字典和 JSON
- 函数注册表
- 异常处理
- 消息协议
- 状态机
- 为什么工具结果必须带 `tool_call_id`
- 为什么模型响应不能直接当作工具执行
- 为什么必须限制最大循环次数

### 6.2 下一步学习实验

在真正连接文件工具前，先写一个假的 `get_time` 工具：

1. 模型请求调用 `get_time`。
2. 程序识别工具名。
3. 程序执行本地函数。
4. 程序把结果回传给模型。
5. 模型生成最终自然语言回答。

这个实验可以在不涉及文件修改和 Shell 安全的情况下，完整理解 Agent Loop。

## 7. 后续开发阶段

### Phase 2：最小 Coding Agent

目标：完成“读取代码—修改文件—运行测试”的闭环。

计划工具：

```text
read_file
list_directory
search_text
write_file
run_command
```

完成标准：

> Agent 可以在固定的小型 Python 项目中修改一个函数，并运行 pytest 验证结果。

### Phase 3：权限和安全

增加：

- 工作区路径限制
- 文件覆盖确认
- 删除操作确认
- Shell 超时
- 输出长度限制
- 操作日志

### Phase 4：任务和恢复

增加：

- Todo
- 会话 JSONL
- 中断恢复
- 最大轮数
- 上下文压缩
- 完成条件

### Phase 5：有限职责 Subagent

先实现：

```text
Researcher：只读分析
Tester：运行测试
Reviewer：检查 diff
```

暂不实现复杂 Agent Team。

## 8. 每次开发完成后的记录模板

以后每完成一个功能，在本文档追加以下内容：

```markdown
## YYYY-MM-DD：功能名称

### 本次目标

### 完成内容

### 运行数据流

### 代码导读

### 为什么这样设计

### 需要掌握的知识

### 测试与结果

### 遇到的问题

### 独立练习

### 下一步
```

## 9. 当前进度表

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 环境、虚拟环境、Git、配置 | 已完成 |
| Phase 1 | DeepSeek 普通调用和 tool call 解析 | 已完成 |
| Phase 2 | Agent Loop 和假工具实验 | 进行中 |
| Phase 3 | 文件、搜索、命令、测试工具 | 未开始 |
| Phase 4 | 权限、审批和工作区保护 | 未开始 |
| Phase 5 | 任务、恢复和上下文管理 | 未开始 |
| Phase 6 | 有限职责 Subagents | 未开始 |

最后更新：Phase 1 完成后。

