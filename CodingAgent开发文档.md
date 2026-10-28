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

## 7. 第一课：最小 Agent Loop + `get_time` 假工具

状态：已完成。

### 7.1 本课目标

本课只引入一个 Agent 机制：模型可以请求工具，程序执行工具，再把结果交回模型。

本课没有引入文件系统、Shell、权限或复杂工具注册系统。这样做是为了先把 Agent 的最核心循环理解清楚。

新增文件：

```text
src/personal_agent/agent_loop.py
tests/test_agent_loop.py
```

新增 CLI 命令：

```powershell
python -m personal_agent.cli agent "What time is it?"
```

### 7.2 Agent Loop 的运行过程

```text
第一次请求
  用户消息
      ↓
  DeepSeek 返回 tool_calls: get_time
      ↓
本地程序
  解析工具名和 arguments
      ↓
  执行 get_time()
      ↓
  生成 role=tool 消息
      ↓
第二次请求
  用户消息 + assistant tool_calls + tool result
      ↓
  DeepSeek 返回最终文本
```

关键点是：模型不会直接执行 Python 函数。模型只能提出一个结构化请求，真正执行动作的是本地程序。

### 7.3 `agent_loop.py` 代码导读

`ToolHandler` 是工具函数的统一类型：

```python
ToolHandler = Callable[[dict[str, Any]], str]
```

这表示工具接收一个字典参数，返回一个字符串结果。现在只有 `get_time`，未来文件工具、搜索工具也会遵守类似的调用边界。

`GET_TIME_TOOL` 是发送给模型的工具 Schema。它告诉模型三件事：

- 工具叫 `get_time`
- 工具可以做什么
- 工具需要什么参数

Schema 是给模型看的“工具说明书”，而 `self.tools` 是程序真正执行的“工具实现”：

```python
self.tools = {"get_time": get_time}
self.tool_schemas = [GET_TIME_TOOL]
```

这两个对象现在并存，是因为模型需要描述，程序需要函数。后续第二课会把它们整理成更清晰的 Tool Registry。

`run()` 是最小循环：

1. 创建初始 `messages`。
2. 调用 `client.chat()`。
3. 将 assistant 消息加入历史。
4. 没有 `tool_calls` 时返回文本。
5. 有 `tool_calls` 时逐个执行工具。
6. 将工具结果以 `role=tool` 追加到历史。
7. 进入下一轮。

工具结果必须携带原始的 `tool_call_id`：

```python
{
    "role": "tool",
    "tool_call_id": call["id"],
    "content": result,
}
```

它是模型把“请求”和“结果”配对的标识。如果没有它，多工具调用或多轮调用时模型可能无法判断哪个结果对应哪个请求。

### 7.4 为什么需要最大轮数

模型可能反复调用工具，或者因为错误结果一直尝试。`max_turns` 是程序侧的安全保险：

```python
for _ in range(self.max_turns):
```

达到上限后抛出错误，而不是无限消耗 API 配额。当前默认值是 8，后续会把它做成配置项。

### 7.5 错误处理

当前工具实验处理三类问题：

- 未知工具：返回 `tool error`
- arguments 不是合法 JSON：返回 `tool error`
- 超过最大轮数：抛出 `DeepSeekError`

这里暂时把工具错误作为结果回传给模型，而不是立即终止。原因是模型可能根据错误信息选择另一种行动。这是 Agent 与普通函数调用的重要区别。

### 7.6 测试设计

新增测试验证：

- 第一次响应包含工具调用
- 程序确实执行 `get_time`
- 第二次请求包含 `role=tool`
- `tool_call_id` 能正确配对
- 第二次响应的最终文本能返回给用户
- Agent 达到最大轮数后会停止

测试仍然使用 `httpx.MockTransport`，所以不需要真实 API，也不会产生费用。

### 7.7 需要掌握的知识

- Python `for` 循环和循环终止
- 字典、列表和 JSON 字符串
- 函数作为值保存到字典中
- `Callable` 类型标注
- 消息协议中的 `role`
- 工具调用 ID 的关联关系
- 异常和错误结果的区别
- 为什么模型只负责建议，程序负责执行

### 7.8 实际运行实验：`chat` 和 `agent` 的区别

同一个问题使用两个命令会得到不同结果：

```powershell
python -m personal_agent.cli chat "现在是什么时间？"
```

这个命令可能回答“无法获取实时时钟”，这是正常的。`chat` 命令只发送普通消息：

```text
用户输入
→ DeepSeek
→ 普通文本
```

它没有传入 `get_time` 工具，也没有启动 Agent Loop，因此模型不能访问本地系统时钟。

而下面的命令会启动工具循环：

```powershell
python -m personal_agent.cli agent "What time is it?"
```

运行流程是：

```text
用户问题
→ DeepSeek 请求 get_time
→ 本地 Python 执行 datetime.now()
→ 工具结果返回 DeepSeek
→ DeepSeek 生成最终答案
```

这次实验说明了一个核心区别：

```text
chat  = 直接调用模型
agent = 模型 + 工具 + 循环
```

模型本身并没有实时读取电脑时钟的能力。实时信息来自本地工具，模型只是决定“需要调用这个工具”，并负责解释工具返回的结果。

中文和英文提示词在本课中都可以使用。英文提示只是可能更容易触发模型选择工具；真正决定 Agent 能力的是是否使用 `agent` 命令并传入工具 Schema。

### 7.9 本课练习

建议独立完成以下练习，再进入第二课：

1. 把 `get_time` 改为返回 UTC 时间。
2. 增加一个 `get_date` 工具。
3. 让 Agent 同时处理两个 tool calls。
4. 为未知工具增加测试。
5. 将 `max_turns` 改为命令行参数。

## 8. 第二课：Tool Registry

状态：已完成。

### 8.1 本课目标

第一课把 `get_time` 的 Schema、处理函数和工具映射暂时放在 `agent_loop.py` 中。这样适合学习最小循环，但工具数量增加后会出现问题：

- Agent Loop 会越来越长
- 每添加一个工具都要修改核心循环
- 工具 Schema 和真实函数容易不一致
- 工具错误处理会重复

第二课把这些职责移动到 `ToolRegistry`：

```text
ToolDefinition
  ├─ name
  ├─ schema
  └─ handler

ToolRegistry
  ├─ register()
  ├─ schemas()
  └─ execute_call()
```

### 8.2 新增文件

```text
src/personal_agent/tools/__init__.py
src/personal_agent/tools/clock.py
src/personal_agent/tools/registry.py
tests/test_tool_registry.py
```

### 8.3 数据流变化

第一课：

```text
AgentLoop
  ├─ 保存工具 Schema
  ├─ 保存工具函数
  ├─ 解析 JSON 参数
  └─ 执行工具
```

第二课：

```text
AgentLoop
  ├─ 向 Registry 索取 schemas
  └─ 向 Registry 请求 execute_call

ToolRegistry
  ├─ 管理工具定义
  ├─ 解析 arguments
  ├─ 检查工具是否存在
  └─ 执行 handler
```

核心变化是：Agent Loop 现在只关心“模型要求调用工具”，不关心具体工具如何实现。

### 8.4 `ToolDefinition`

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    schema: dict[str, Any]
    handler: ToolHandler
```

它把一个工具的三个组成部分放在一起：

```text
名称：程序识别它
Schema：模型理解它
Handler：程序执行它
```

注册时会检查名称是否一致：

```python
schema_name = definition.schema.get("function", {}).get("name")
if schema_name != definition.name:
    raise ValueError(...)
```

这是一个重要的防御性检查。如果 Schema 叫 `read_file`，但注册名叫 `readfile`，模型和程序就会产生分歧。

### 8.5 `ToolRegistry`

注册工具：

```python
registry.register(definition)
```

提供给模型的工具列表：

```python
registry.schemas()
```

执行模型请求：

```python
registry.execute_call(call)
```

未知工具和无效参数不会让主循环崩溃，而是返回标准化的 `tool error` 字符串，交给模型继续判断。

### 8.6 为什么现在可以添加第二个工具

不需要再修改 `AgentLoop` 的循环逻辑，只需要：

1. 编写工具函数。
2. 编写工具 Schema。
3. 创建 `ToolDefinition`。
4. 注册到 `ToolRegistry`。

这体现了“开放扩展、封闭修改”的思想：工具集合可以扩展，核心循环不必反复改动。

### 8.7 需要掌握的知识

- `dataclass`
- `Callable`：函数作为参数和对象保存
- 字典作为注册表
- 模块和包的拆分
- Schema 与实现的对应关系
- 单一职责
- 开放封闭原则
- 集中式错误处理

### 8.8 第二课测试

新增测试验证：

- Registry 能暴露工具 Schema
- Registry 能执行对应 handler
- 不能重复注册同名工具
- Schema 名称和注册名称必须一致
- 未知工具返回错误
- 无效参数返回错误

当前测试结果：

```text
9 passed
```

### 8.9 第二课练习

在不修改 `AgentLoop` 的前提下，尝试增加一个 `get_date` 工具：

1. 在 `tools/clock.py` 编写函数。
2. 添加对应 Schema。
3. 创建 `ToolDefinition`。
4. 注册到默认 Registry。
5. 为 Registry 增加测试。

完成后再进入第三课。

## 9. 后续开发阶段

### 第二课：Tool Registry

对应参考项目：`learn-claude-code/s02_tool_use`。

目标：把工具名称、Schema、处理函数和错误处理统一管理。

本课完成后，再开始添加真实文件工具。

## 10. 第三课：只读文件工具

状态：已完成。

### 10.1 本课目标

在不修改文件、不执行命令的前提下，让 Agent 能观察代码工作区：

```text
list_directory
read_file
search_text
```

观察是 Coding Agent 的第一种真实能力。模型必须先看到代码，才有可能提出合理的修改方案。

### 10.2 工作区概念

第三课引入了 `workspace`：

```text
workspace = Agent 被允许观察的根目录
```

工具收到相对路径后，会把它解析到 workspace 内：

```text
用户提供 src/main.py
→ workspace / src/main.py
→ resolve()
→ 检查是否仍在 workspace 内
→ 执行读取
```

`../secret.txt` 会被拒绝。这不是完整权限系统，完整的审批和权限课程会放到第六课；但即使只读工具，也必须先建立最基本的边界。

### 10.3 三个工具

`list_directory` 返回目录条目，目录用 `/` 标记。

`read_file` 读取 UTF-8 文本，并限制默认最大字符数，避免一次把超大文件全部放进上下文。

`search_text` 递归搜索文本文件，返回：

```text
相对路径:行号:匹配行
```

搜索结果最多返回 100 条，避免工具结果无限增长。

### 10.4 为什么只读工具先于修改工具

Coding Agent 的基本循环是：

```text
观察 → 推理 → 行动 → 验证
```

第三课只实现“观察”。这样可以先学习：

- 工具如何接收参数
- 工具如何返回结果
- 工具结果如何进入上下文
- 路径如何解析
- 大结果如何限制

如果一开始就加入写文件和 Shell，观察、修改、安全和回滚会同时出现，难以判断问题来自哪一层。

### 10.5 代码组织

新增：

```text
src/personal_agent/tools/filesystem.py
tests/test_filesystem_tools.py
```

`filesystem.py` 通过 `create_filesystem_tools(workspace)` 创建工具定义，因此工具函数可以绑定不同 workspace，而不需要依赖全局变量。

AgentLoop 默认注册：

```text
get_time
list_directory
read_file
search_text
```

AgentLoop 本身仍然不包含这些工具的实现，只从 Registry 获取 Schema 并执行调用。

### 10.6 需要掌握的知识

- `pathlib.Path`
- `resolve()` 和相对路径
- `relative_to()` 的边界检查
- 目录遍历和递归遍历
- 文件编码与 `errors="replace"`
- 文本结果截断
- 为什么上下文大小是 Agent 的资源
- 观察权限和修改权限的区别

### 10.7 测试结果

新增测试验证：

- 目录列表
- 文件读取
- 文本搜索
- 相对路径输出
- 工作区外路径拒绝

当前测试结果：

```text
11 passed
```

### 10.8 第三课练习

1. 让 `list_directory` 支持只返回文件。
2. 让 `read_file` 返回行号。
3. 让 `search_text` 支持大小写敏感选项。
4. 为二进制文件增加跳过逻辑。
5. 为超大文件截断行为增加测试。

### 10.9 第三课自测命令

所有命令都应在项目根目录执行：

```powershell
cd D:\GITHUBPROJECTS\AGENTPROJ_PERSONAL\Coding_Agent_1021
```

#### 测试目录查看

```powershell
python -m personal_agent.cli agent "请查看当前工作区的目录结构，并列出主要文件。"
```

预期现象：模型调用 `list_directory`，然后根据返回结果总结目录。

#### 测试读取文件

```powershell
python -m personal_agent.cli agent "请读取 README.md，并告诉我这个项目当前完成到了哪一课。"
```

预期现象：模型调用 `read_file`，工具结果中出现 README 内容，最终回答项目状态。

#### 测试代码搜索

```powershell
python -m personal_agent.cli agent "请搜索项目中所有出现 ToolRegistry 的位置，并说明它的作用。"
```

预期现象：模型调用 `search_text`，结果包含文件路径、行号和匹配行。

#### 测试工作区边界

```powershell
python -m personal_agent.cli agent "请读取 ../secret.txt 的内容。"
```

预期现象：工具拒绝工作区外路径，模型应说明无法读取，而不是输出文件内容。

#### 测试工具选择

```powershell
python -m personal_agent.cli agent "请先查看 src/personal_agent 目录，再读取其中的 agent_loop.py，最后解释 AgentLoop 如何工作。"
```

预期现象：模型至少调用 `list_directory` 和 `read_file`，并可能分多轮完成任务。

注意：模型决定是否调用工具，因此自然语言表达可能影响工具选择。如果模型没有调用预期工具，可以把指令写得更明确，例如“必须调用 read_file 工具读取……”。

## 12. 每一课的自测规范

以后每完成一课，都提供三类测试：

### A. 直接功能测试

验证本课新增能力是否能单独工作。

### B. Agent 场景测试

通过：

```powershell
python -m personal_agent.cli agent "自然语言任务"
```

验证模型是否能选择正确工具并完成多轮流程。

### C. 失败场景测试

输入错误路径、错误参数或制造工具失败，观察 Agent 是否能返回清晰错误并安全结束。

当前各课自测入口：

| 课程 | 自测方式 | 主要验证 |
|---|---|---|
| Phase 0 | `python -m personal_agent.cli doctor` | 环境和 API 配置 |
| Phase 1 | `python -m personal_agent.cli chat "..."` | DeepSeek 普通调用 |
| 第一课 | `python -m personal_agent.cli agent "请调用 get_time..."` | Agent Loop |
| 第二课 | `python -m personal_agent.cli agent "..."` | Registry 分发工具 |
| 第三课 | `python -m personal_agent.cli agent "请读取 README.md..."` | 文件观察工具 |
| 第四课 | 等实现后补充 | 文件修改 |
| 第五课 | 等实现后补充 | 命令和测试执行 |
| 第六课 | 等实现后补充 | 权限和 Hooks |

每课文档必须记录：实际命令、模型是否调用预期工具、工具返回是否正确、最终结果是否符合预期、失败时发生了什么。

## 13. 第四课：文件修改工具

状态：已完成。

### 13.1 本课目标

第三课让 Agent 能观察工作区，本课增加最小的修改能力：

```text
write_file
apply_patch
```

现在 Agent 开始具备：

```text
观察 → 修改
```

测试执行和自动修复要到第五课再加入。

### 13.2 `write_file`

`write_file` 用于创建新文件，或者在显式设置 `overwrite=true` 时覆盖已有文件。默认拒绝覆盖，以避免模型无意中替换原文件。

写入前仍然经过 `_resolve()`，因此不能写到 workspace 外部。

### 13.3 `apply_patch`

本课的 `apply_patch` 采用“唯一文本替换”模型：

```json
{
  "path": "hello.py",
  "old_text": "x = 1",
  "new_text": "x = 2"
}
```

程序会检查文件存在、旧文本能找到且只出现一次；如果匹配不到或匹配到多处，就拒绝修改。这比直接让模型提交整份文件更容易检查修改范围。

### 13.4 为什么先实现两种修改方式

`write_file` 适合创建新文件或完整重写小文件；`apply_patch` 适合只修改已有代码中的一个片段并保留其余内容。本课暂不引入完整 unified diff 解析器，先理解“修改前内容必须唯一匹配”。

### 13.5 当前限制

本课还没有用户审批、Git diff 展示、自动备份、回滚、Shell 测试和删除文件。权限、审批和验证会在第六课及后续课程中补充。

### 13.6 需要掌握的知识

- `Path.write_text`
- 文件覆盖风险
- 字符串 `count()` 和 `replace()`
- 唯一匹配
- 修改工具为什么必须返回明确结果
- 观察、行动和验证的区别

### 13.7 第四课自测命令

```powershell
python -m personal_agent.cli agent "请创建一个 notes.txt 文件，内容写成：这是我的 Coding Agent 学习笔记。"
```

预期：模型调用 `write_file`，项目目录中出现 `notes.txt`。

```powershell
python -m personal_agent.cli agent "请读取 README.md，然后把其中的 Phase 0 改成 Phase 0（环境完成）。"
```

预期：模型先调用 `read_file`，再调用 `apply_patch`。测试后使用下面的命令检查修改：

```powershell
git diff -- README.md
```

```powershell
python -m personal_agent.cli agent "请把 README.md 全部覆盖成 test。"
```

预期：工具默认拒绝覆盖已有文件。

## 14. 后续开发阶段

### 第五课：命令和测试工具

目标：添加 `run_command`、`run_tests`、`git_diff`，完成第一次代码修复闭环。

### 第六课：权限和 Hooks

对应参考项目：`s03_permission`、`s04_hooks`。

目标：加入工作区保护、危险操作审批、超时、输出限制和执行前后钩子。

### 后续阶段

以下内容等用户明确通知后再继续：

- 任务和上下文管理
- 会话恢复
- Subagent
- Agent Team
- 桌面工作助手

原先的工具计划仍保留在这里作为长期方向，但不会提前实现。

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
| 第一课 | Agent Loop 和 `get_time` 假工具 | 已完成 |
| 第二课 | Tool Registry | 已完成 |
| 第三课 | 只读文件工具 | 已完成 |
| 第四课 | 文件修改工具 | 已完成 |
| 第五课 | 命令、测试和 Git diff | 已完成 |
| 第六课 | 权限和 Hooks | 等待通知 |
| 后续 | 任务、恢复、Subagent、桌面助手 | 未开始 |

最后更新：第五课完成后。

## 16. 第五课：命令、测试和 Git diff

状态：已完成。

### 16.1 本课目标

第四课让 Agent 能修改文件，本课增加修改后的验证能力：

```text
run_command
run_tests
git_diff
```

现在基本流程变成：

```text
观察 → 修改 → 执行 → 检查
```

这是 Coding Agent 第一个接近真实开发的闭环，但权限审批仍未加入。

### 16.2 三个命令工具

`run_command` 在 workspace 中执行命令并返回退出码、标准输出和错误输出，同时限制超时时间与输出长度。

`run_tests` 是 `run_command` 的语义封装，默认运行：

```text
python -m pytest
```

`git_diff` 查看当前工作区修改，底层使用：

```text
git diff -- <path>
```

它们让 Agent 能够在修改后检查结果，但当前不会自动提交、回滚或推送。

### 16.3 为什么需要退出码和超时

模型不能只根据命令输出判断成功。命令可能打印内容但返回失败退出码，因此工具结果必须包含：

```text
exit_code
stdout
stderr
```

命令也可能卡住，所以当前默认超时 60 秒，最大允许 300 秒。输出默认限制 12,000 字符，避免错误日志占满上下文。

### 16.4 安全说明

本课首次允许模型执行命令，目前仍是学习版实现：

- 使用 `shell=True`
- 尚未拦截危险命令
- 尚未加入用户审批
- 尚未设置命令白名单
- 尚未限制网络访问

因此暂时只在自己的测试项目中使用。第六课再加入权限与 Hooks。

### 16.5 需要掌握的知识

- `subprocess.run`
- 工作目录 `cwd`
- stdout、stderr 和退出码
- 子进程超时
- Shell 命令风险
- Git diff
- 为什么测试结果是 Agent 的验证依据
- 为什么模型声称成功不能替代程序验证

### 16.6 第五课自测命令

```powershell
python -m personal_agent.cli agent "请运行项目测试，并告诉我通过了多少个测试。"
```

```powershell
python -m personal_agent.cli agent "请查看当前 Git diff，并总结最近的代码修改。"
```

```powershell
python -m personal_agent.cli agent "请执行 python --version，并告诉我 Python 版本。"
```

```powershell
python -m personal_agent.cli agent "请运行一个一定会失败的测试命令，并解释退出码和错误输出。"
```

测试时不要让 Agent 执行删除文件、修改系统设置或访问工作区外的命令；这些行为要等第六课加入权限机制后再测试。

## 17. 第六课：权限和 Hooks

状态：已完成。

### 17.1 本课目标

第五课之后，Agent 已经可以执行命令，但“模型提出工具调用”不应该等于“工具一定执行”。第六课把工具执行流程改为：

```text
模型提出工具调用
    ↓
解析参数
    ↓
PermissionPolicy 权限判断
    ↓
before hooks
    ↓
执行工具
    ↓
after hooks / error hooks
    ↓
把结果返回模型
```

这次没有把权限判断写进 `AgentLoop`，因为 AgentLoop 只应该负责对话循环。权限属于工具调度层，所以放在 `ToolRegistry.execute_call()` 中。

### 17.2 权限策略

文件位置：`src/personal_agent/tools/permissions.py`。

当前策略把以下工具视为高风险：

```text
write_file
apply_patch
run_command
run_tests
```

只读工具默认允许；高风险工具需要 `approval_callback` 返回 `True`。如果没有审批回调，高风险工具默认拒绝，这是一种 fail closed（失败时关闭权限）的安全默认值。

CLI 中的 `agent` 命令会在执行高风险工具前显示：

```text
Allow tool run_tests({})? [y/N]
```

输入 `y` 或 `yes` 才会继续，其他输入都拒绝。

### 17.3 Hooks

`ToolRegistry` 现在支持三类 Hooks：

- `before_hooks`：工具执行前调用，可用于日志、审计或后续更细的拦截。
- `after_hooks`：工具成功执行后调用，可用于记录耗时、结果状态等。
- `error_hooks`：权限拒绝、参数错误或工具异常时调用，可用于错误统计和诊断。

Hook 接收工具名和参数，但当前不修改参数，也不替代权限策略。这样先把生命周期事件抽象出来，后续可以继续增加日志、计时和重试机制。

### 17.4 第六课自测命令

只读工具不需要确认：

```powershell
python -m personal_agent.cli agent "请读取 README.md，并告诉我项目当前完成到哪一课。"
```

运行测试时会出现确认提示：

```powershell
python -m personal_agent.cli agent "请运行项目测试，并告诉我测试结果。"
```

输入 `y` 允许执行；输入 `n` 或直接回车，观察 Agent 如何处理权限拒绝。

文件修改也会要求确认：

```powershell
python -m personal_agent.cli agent "请在当前项目创建一个 lesson6_probe.txt，内容写入 permission test。"
```

本课仍然不要批准删除文件、修改系统设置、访问工作区外路径或未知网络命令。当前审批是工具级别的第一版，后续还要加入命令分类、路径校验和更细粒度规则。

### 17.5 第六课修正版：从工具级审批到命令级防护

第一次实测暴露了一个问题：仅仅询问“是否允许 `run_tests`”还不够，因为模型可能把 Linux 命令、Shell 链接或删除命令放进 `run_tests` 的参数里。因此本次修正版补充了三层保护：

1. `run_tests` 只接受以 `python -m pytest` 开头的命令，不再是任意命令执行器。
2. `run_command` 和 `run_tests` 对 `del`、`rmdir`、`rm`、`sudo`、`shutdown`、`format` 等危险命令做硬拒绝，即使用户审批回调返回允许也不会执行。
3. 拒绝 `/workspace`、`/dev/`、`2>/dev/null`、`tail` 等明显 Linux 专用路径或语法，避免模型把其他运行环境的命令直接带到 Windows 项目中。

`git_diff` 也不再把路径直接拼接进 Shell 字符串，而是先限制路径必须位于 workspace，再使用参数列表调用 Git，减少路径注入风险。

这次修正对应参考项目中更完整的 s03 Permission：有硬拒绝、规则匹配和用户审批；当前 Hooks 则是 s04 的基础版。它还没有进入 s05 TodoWrite。

## 18. 第七课：TodoWrite 任务清单

状态：已完成。

### 18.1 本课目标

前几课的 Agent 已经会观察、修改、执行和验证，但面对复杂任务时没有显式计划。本课加入 `todo_write`，让模型可以维护当前任务清单：

```text
规划任务 → 执行一个步骤 → 更新状态 → 继续下一步 → 汇报进度
```

这对应参考项目的 `s05_todo_write`。当前实现把清单保存在一次 Agent 实例的内存中，不写文件、不使用数据库；持久化会留到后面的 s10 Task System。

### 18.2 工具输入

模型调用格式：

```json
{
  "todos": [
    {"id": "1", "content": "读取相关代码", "status": "completed"},
    {"id": "2", "content": "定位问题", "status": "in_progress"},
    {"id": "3", "content": "修改并运行测试", "status": "pending"}
  ]
}
```

每个任务必须有唯一 `id`、非空 `content`，状态只能是 `pending`、`in_progress` 或 `completed`。一次 `todo_write` 会整体替换旧清单，而不是悄悄合并，避免模型看到过期任务。

### 18.3 架构变化

新增文件：`src/personal_agent/tools/todo.py`。它使用 `create_todo_tools()` 返回工具定义和内部状态；`AgentLoop` 只负责把这个工具注册到默认注册表，不负责统计任务数量或判断状态。

因此架构仍然是：

```text
AgentLoop → ToolRegistry → todo_write → 内存中的 todo state
```

工具返回完成数、进行中数量、待办数量和每条任务，模型可以据此决定下一步。它不是新的 AgentLoop，也不是新的模型调用循环。

### 18.4 第七课自测命令

```powershell
python -m personal_agent.cli agent "这是一个复杂任务：先查看项目结构，再读取 agent_loop.py，然后运行测试。请先创建任务清单，执行过程中及时更新任务状态，最后汇报每一步。"
```

```powershell
python -m personal_agent.cli agent "请为‘修复一个测试失败问题’创建一个三步任务清单，并说明每个任务的状态。"
```

观察重点：模型是否先调用 `todo_write`；任务是否从 `pending` 变成 `in_progress` 和 `completed`；测试失败时是否保留失败步骤，而不是声称全部完成。

### 18.5 需要掌握的知识

- 状态机：`pending → in_progress → completed`
- 数据校验和唯一 ID
- 内存状态与持久化状态的区别
- 为什么工具状态不应该硬编码进 AgentLoop
- 为什么“整体替换清单”比隐式合并更容易理解和验证
- 任务计划如何帮助模型分解复杂目标

## 19. 第八课：Subagent 子 Agent

状态：已完成。

### 19.1 本课目标

第七课让主 Agent 记录任务，第八课加入 `task` 工具，把一个明确的子任务交给独立的子 Agent：

```text
主 Agent
  ├─ 自己处理主任务
  └─ task(prompt) → 子 Agent 使用全新的 messages[] → 返回最终摘要
```

这对应参考项目的 `s06_subagent`。这里隔离的是对话上下文，不是进程或文件系统：父子 Agent 仍在同一 Python 进程和同一个 workspace 中运行，因此子 Agent 的文件修改会影响父 Agent 能看到的项目。

### 19.2 父子 Agent 的边界

- 父 Agent 拥有 `task` 工具。
- 子 Agent 使用文件、命令、Todo 等基础工具，但 `include_subagent=False`，因此不能继续创建子 Agent。
- 子 Agent 从新的 `messages = [{"role": "user", "content": prompt}]` 开始，不复制父 Agent 的历史工具调用。
- 子 Agent 最终只返回文本摘要，子 Agent 的中间消息不会进入父 Agent 的上下文。
- 父子 Agent 共享 DeepSeekClient、workspace、权限策略和 Hooks。

### 19.3 为什么要隔离上下文

如果父 Agent 为了分析某个文件调用了十几次工具，所有中间结果都会留在父上下文中。把“研究调用链”“总结测试结构”等工作交给子 Agent 后，父 Agent 只接收最终结论，可以减少上下文噪声。

它不是多进程，也不是并行执行；当前实现是同步嵌套调用：父 Agent 等子 Agent 返回后再继续。

### 19.4 第八课自测命令

```powershell
python -m personal_agent.cli agent "请使用一个子 Agent 检查项目使用了什么测试框架，并把子 Agent 的结论告诉我。"
```

```powershell
python -m personal_agent.cli agent "请把‘读取项目结构并总结主要模块’交给子 Agent，父 Agent 只汇报子 Agent 的最终摘要。"
```

运行时观察：

```text
[Subagent started]
Allow tool read_file(...)? [y/N]
[Subagent done]
```

如果子 Agent 需要执行高风险工具，父子 Agent 共享当前权限策略，因此仍然会请求审批。子 Agent 不应再次调用 `task`。

## 20. 第九课：Skill Loading 按需加载技能

状态：已完成。

### 20.1 本课目标

第八课之后，Agent 可以委派子任务，但不同任务需要不同知识。本课加入技能目录和 `load_skill` 工具：启动时只把技能名称和简介放进 system prompt，模型判断需要时再加载完整 `SKILL.md`。

```text
启动时：技能目录（名称 + 简介）
任务中：调用 load_skill(name)
调用后：完整技能说明进入 tool result
```

这对应参考项目的 `s07_skill_loading`，目的是减少无关说明对上下文和输入 token 的占用。

### 20.2 技能文件结构

```text
skills/
  code-review/SKILL.md
  testing/SKILL.md
```

每个 `SKILL.md` 使用简单 YAML frontmatter。`SkillLoader.scan()` 只读取工作区 `skills` 目录下的一级子目录，建立名称到技能的注册表；`load()` 按名称查询，不把模型输入直接当作文件路径。

### 20.3 架构变化

新增 `src/personal_agent/skills.py` 和 `tools/skills.py`。`AgentLoop` 通过可选的 `skill_loader` 注册 `load_skill`，通过可选的 `system_prompt` 接收技能目录；主循环仍然不关心 Markdown 文件格式或技能内容。

CLI 会加载当前项目的 `skills/` 目录。技能完整内容不会在每次请求中自动发送，只有模型调用 `load_skill` 后才作为工具结果进入上下文。

### 20.4 第九课自测命令

```powershell
python -m personal_agent.cli agent "当前有哪些可用技能？请先选择与测试相关的技能并加载它，然后说明项目测试应该遵守哪些原则。"
```

```powershell
python -m personal_agent.cli agent "请加载 code-review 技能，然后检查当前项目最近的代码修改并给出审查结果。"
```

观察重点：system prompt 中是否只有技能目录；模型是否调用 `load_skill`；完整技能内容是否只在调用后进入上下文；未知技能是否返回可读错误。

## 21. 第十课：Context Compact 上下文压缩

状态：已完成。

### 21.1 本课目标

长任务会让 `messages[]` 不断增长：文件内容、搜索结果、测试日志和模型回复都会继续留在上下文。本课加入 `ContextCompactor`，在下一次调用 DeepSeek 前检查消息数量和字符数，超限时归档旧历史并保留当前目标与最近消息。

```text
messages[] 变长
    ↓
估算消息数量和字符数
    ↓
完整历史写入 .transcripts/
    ↓
保留当前目标 + 最近消息
    ↓
继续调用模型
```

### 21.2 为什么先归档再压缩

压缩会丢失一部分上下文细节，所以 `ContextCompactor` 先把完整消息写入 `.transcripts/transcript-*.json`。当前消息中留下归档路径和当前用户请求，需要时可以通过文件工具恢复历史。

本课使用确定性压缩，不调用额外模型生成摘要：这样行为容易测试，且不会增加 DeepSeek API 请求。后续可以再加入模型摘要和 API 返回上下文过长时的补救。

### 21.3 两种触发方式

1. 自动触发：每次调用 DeepSeek 前，消息数量超过 20 条或估算字符数超过 30,000 时压缩。
2. 主动触发：模型调用 `compact` 工具；当前这一批工具调用全部完成后再压缩，避免留下孤立的工具调用或工具结果。

`compact` 工具不是删除文件的工具，它只管理当前会话消息，并把备份写入 `.transcripts/`。

### 21.4 工具调用配对保护

OpenAI 兼容消息中，assistant 的 `tool_calls` 和对应的 `tool` 消息必须成对存在。压缩切点如果落在两者之间，下一次 DeepSeek 请求可能被判为无效。因此压缩时如果保留区从 `tool` 消息开始，就向前移动一个位置，保留对应的 assistant 消息。

### 21.5 第十课自测命令

```powershell
python -m personal_agent.cli agent "请连续读取并比较多个项目文件，在任务中适时调用 compact，最后总结你保留了哪些重要信息。"
```

```powershell
python -m personal_agent.cli agent "请先分析项目结构，再主动压缩上下文，然后继续读取 agent_loop.py 并解释它。"
```

观察项目目录中是否出现：

```text
.transcripts/transcript-*.json
```

重点观察：压缩后任务是否仍然记得当前用户目标；工具调用和工具结果是否仍然成对；模型是否能继续工作，而不是因为历史被裁剪而崩溃。

## 22. 第十一课：Memory 跨会话记忆

状态：已完成。

### 22.1 本课目标

s08 的 transcript 是当前会话归档；本课的 Memory 是跨会话仍然有用的少量信息：用户偏好、项目事实、工作反馈和参考线索。

```text
remember 保存记忆
    ↓
.memory/*.md + MEMORY.md 索引
    ↓
新会话根据请求检索
    ↓
相关记忆进入 system prompt
```

### 22.2 存储格式

每条记忆是 `.memory/` 下的 Markdown 文件，frontmatter 包含 `name`、`description` 和 `type`。类型有 `user`、`feedback`、`project`、`reference`。

`MEMORY.md` 只是索引，不把所有正文自动放入 system prompt。正文仍然存放在独立文件中。

### 22.3 两个记忆工具

- `remember`：保存一条长期记忆，需要写入权限；当前不会自动保存所有聊天内容。
- `recall_memory`：按关键词检索相关记忆，只返回匹配记录。

CLI 在每次新会话启动时也会根据当前用户请求做一次轻量关键词召回，并把结果标记为背景知识。记忆不是新的用户命令；如果它和当前请求冲突，以当前请求为准。

当前实现使用确定性的关键词匹配，没有额外调用 DeepSeek 做向量检索或自动提取，便于理解和测试。后续可以再加入 embedding、模型提取和重复记忆整理。

### 22.4 第十一课自测命令

```powershell
python -m personal_agent.cli agent "请记住：我希望项目始终直接使用 DeepSeek API，不要切换到 Claude 或 OpenAI。"
```

```powershell
python -m personal_agent.cli agent "下次开发这个项目时，我的模型 API 偏好是什么？"
```

```powershell
Get-ChildItem .memory
Get-Content .memory\MEMORY.md
```

观察重点：是否生成独立记忆文件；索引是否更新；新会话是否只召回与当前问题相关的记忆；当前用户的新要求是否优先于旧记忆。

## 23. 第十二课：Task System 持久化任务系统

状态：已完成。

### 23.1 本课目标

s05 的 `todo_write` 只保存当前 Agent 实例的执行清单。本课加入 `.tasks/` 任务系统，让任务拥有独立 ID、描述、负责人、状态和依赖关系，程序退出后仍然可以恢复。

```text
create_task → 得到 task_id
update_task → 建立 blocked_by 依赖
claim_task → pending → in_progress
complete_task → in_progress → completed
```

### 23.2 TodoWrite 与 Task System 的区别

```text
todo_write：当前会话的整张执行清单，内存状态，无依赖
Task System：跨会话的独立任务，.tasks/{id}.json，有 owner 和依赖图
```

两者暂时并存：TodoWrite 适合 Agent 自己规划几步；Task System 适合多个可恢复、可认领、互相阻塞的开发任务。

### 23.3 任务依赖和状态机

任务状态只能按以下方式变化：

```text
pending ──claim──→ in_progress ──complete──→ completed
```

如果任务的 `blocked_by` 中有任何任务不是 `completed`，它不能被认领。这样 `create API` 可以依赖 `setup schema`，测试任务可以依赖 API 任务。

任务 ID 在创建时生成，例如：

```text
task_a1b2c3d4
```

任务文件保存在：

```text
.tasks/task_a1b2c3d4.json
```

### 23.4 六个任务工具

- `create_task`：创建任务并返回运行时生成的 ID。
- `list_tasks`：列出所有任务及状态。
- `get_task`：读取一个任务的完整 JSON。
- `update_task`：使用已存在的 ID 设置依赖。
- `claim_task`：检查依赖后认领任务。
- `complete_task`：由负责人完成任务。

先创建节点、再建立依赖，是因为模型一次回复可能同时创建多个任务；在工具结果返回前，一个创建调用无法安全引用另一个调用刚生成的 ID。

### 23.5 第十二课自测命令

```powershell
python -m personal_agent.cli agent "请创建三个持久化任务：准备项目结构、编写核心代码、运行测试；让编写核心代码依赖项目结构，让运行测试依赖核心代码。"
```

```powershell
python -m personal_agent.cli agent "请列出当前所有持久化任务，并说明哪些任务可以认领。"
```

```powershell
Get-ChildItem .tasks
Get-Content .tasks\*.json
```

观察重点：任务 ID 是否写入 `.tasks/`；依赖未完成时是否拒绝 claim；完成前置任务后，下游任务是否可以认领；重新启动 Agent 后任务是否仍然存在。

## 24. 第十三课：Background Tasks 后台任务

状态：已完成。

### 24.1 本课目标

s10 让任务状态可以持久化，但命令仍然是同步执行的。安装依赖、完整测试或构建可能需要很久，如果 AgentLoop 一直等待，模型就不能继续处理其他工作。本课让模型显式请求后台执行：

```text
run_command(run_in_background=true)
    ↓
BackgroundManager 启动 daemon 线程
    ↓
立即返回 bg_id
    ↓
AgentLoop 继续下一轮
    ↓
后续轮次收集 task_notification
```

### 24.2 显式后台策略

只有模型明确传入：

```json
{"command": "python -m pytest", "run_in_background": true}
```

才会进入后台。默认仍然同步执行，不根据 `test`、`build` 或 `install` 等关键词猜测，避免意外改变行为。

### 24.3 任务生命周期

`BackgroundManager` 为每个后台命令生成 `bg_xxxxxxxx`，保存运行状态、命令和结果。命令结束后状态变为 `completed` 或 `failed`，结果进入 ready 队列。

原始工具调用先返回：

```text
[Background task bg_xxxxxxxx started]
```

后续 AgentLoop 请求 DeepSeek 前，收集结果并追加独立通知：

```text
<task_notification id='bg_xxxxxxxx' status='completed'>
exit_code: 0
...
</task_notification>
```

通知不复用原始 tool_call_id，因为原始调用已经有一个合法的占位 tool result。

### 24.4 与 Task System 的区别

```text
Task System：持久化的业务任务，跨会话保存依赖和负责人
Background Task：运行时的异步命令，等待进程结束并收集输出
```

当前后台任务保存在内存中，程序退出后不恢复；后续可把它与 `.tasks/` 或更完整的后台作业数据库结合。

### 24.5 第十三课自测命令

```powershell
python -m personal_agent.cli agent "请在后台运行一个短暂的 Python 等待命令，同时读取 README.md，等后台任务完成后再汇报结果。"
```

```powershell
python -m personal_agent.cli agent "请明确使用 run_in_background=true 在后台运行项目测试，之后检查项目目录，最后汇报后台测试结果。"
```

观察重点：是否先返回 `bg_id`；Agent 是否继续执行其他工具；后续轮次是否出现 `<task_notification>`；未设置 `run_in_background` 时是否仍然同步执行。

## 25. 第十四课：Cron Scheduler 定时任务

状态：已完成。

### 25.1 本课目标

s11 的后台任务解决“命令启动后不阻塞”，但它不会记住命令什么时候启动。本课增加定时 Prompt 调度：到达指定时间后，把一条新的任务消息放入 Agent 的待处理队列。

```text
schedule_cron
    ↓
.scheduled_tasks.json
    ↓
调度线程每秒检查本地时间
    ↓
匹配 Cron 表达式
    ↓
加入待交付队列
    ↓
AgentLoop 下一轮消费
    ↓
[Scheduled] prompt
```

### 25.2 Cron 表达式

当前支持五段式：

```text
分钟 小时 日 月 星期
*     *    *  *  *
0     9    *  *  *       每天 09:00
*/5   *    *  *  *       每 5 分钟
0     9    *  *  1-5     工作日 09:00
```

支持 `*`、`*/N`、单个数字、范围和逗号列表。调度器使用本机本地时间。

### 25.3 三个工具

- `schedule_cron`：保存 cron、prompt、是否重复和是否持久化。
- `list_crons`：查看当前定时任务。
- `cancel_cron`：按生成的 `cron_xxxxxxxx` ID 取消任务。

持久化任务写入 `.scheduled_tasks.json`。`durable` 只保存任务定义；当前 CLI 进程退出后调度线程也会停止，重启 CLI 才会重新加载并继续调度。它不是 Windows 任务计划程序的替代品。

### 25.4 调度与 AgentLoop 的边界

调度线程只负责判断时间和入队，不直接调用 DeepSeek。AgentLoop 每一轮开始时消费队列，把任务变成：

```text
[Scheduled cron_xxxxxxxx] run tests
```

这样定时任务仍然经过现有 AgentLoop、权限、Hooks、Memory、Task System 和工具执行流程。一次性任务交付后删除；周期任务清除 pending 标记，等待下一次匹配。

### 25.5 第十四课自测命令

```powershell
python -m personal_agent.cli agent "请创建一个每5分钟触发的定时任务，prompt 是‘检查项目测试状态’，然后列出当前定时任务。"
```

```powershell
Get-Content .scheduled_tasks.json
```

```powershell
python -m personal_agent.cli agent "请列出当前定时任务，并取消刚才创建的任务。"
```

要观察实际触发，需要保持一个长期运行的 Agent 进程；当前一次性 CLI 命令结束后，调度线程也会停止。

