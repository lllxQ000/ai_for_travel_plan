# `agent.py` 模块详解

`agent.py` 是整个项目的核心模块，负责**管理对话、构建 LangChain Agent、处理流式/非流式对话**，并与存储、工具等模块协作。下面逐部分解析其功能、设计思路和潜在问题。

---

## 一、模块整体职责

- **对话持久化**：使用 `ConversationStorage` 类将用户会话（消息历史）保存到本地 JSON 文件。
- **Agent 构建**：通过 `create_agent_instance` 初始化 LangChain Agent，绑定工具（天气、知识库检索），设置系统提示词。
- **对话处理**：提供同步（`chat_with_agent`）和异步流式（`chat_with_agent_stream`）两种接口，供 API 层调用。
- **记忆管理**：当历史消息超过 50 条时，调用 LLM 生成摘要，压缩上下文。
- **RAG 过程整合**：通过 `get_last_rag_context` 和 `reset_tool_call_guards` 与 RAG 工具联动，确保检索上下文在请求间隔离，并实现实时步骤推送。

---

## 二、核心类与函数详解

### 1. `ConversationStorage` 类
负责将对话存储到本地 JSON 文件，支持用户/会话维度。

**关键方法**：
- `save(user_id, session_id, messages, extra_message_data)`：将 `messages`（LangChain 消息对象）序列化保存。`extra_message_data` 用于附加 `rag_trace` 等额外信息。
- `load(user_id, session_id)`：从文件加载历史消息，并还原为 LangChain 的 `HumanMessage`、`AIMessage`、`SystemMessage` 对象。
- `list_sessions`、`delete_session`：管理会话列表。

**设计亮点**：
- 使用 JSON 文件持久化，简单可靠，适合学生项目初期。
- 支持为每条消息附加自定义数据（如 `rag_trace`），便于前端展示检索过程。

**潜在问题**：
- 并发写入可能导致数据损坏（多请求同时写同一个会话）。可以考虑使用文件锁或切换到 SQLite。
- 每次保存都全量写入文件，会话越长效率越低。

---

### 2. `create_agent_instance` 函数
```python
def create_agent_instance():
    model = init_chat_model(...)   # 配置 Qwen3.5
    agent = create_agent(
        model=model,
        tools=[get_current_weather, search_knowledge_base],
        system_prompt="...",
    )
    return agent, model
```
- **作用**：创建 LangChain Agent 实例和 LLM 模型实例。
- **配置要点**：
  - `init_chat_model` 通过 OpenAI 兼容接口调用阿里云 Qwen3.5。
  - `create_agent` 是 LangChain 1.0+ 的新 API（替代 `create_react_agent`），直接返回一个可调用的 Agent 对象。
  - `system_prompt` 包含了明确的工具使用规则（如“每个回合最多调用一次知识库工具”，“收到检索结果后必须立即生成最终答案”），这有助于减少 Agent 的无效重复调用。

---

### 3. `summarize_old_messages` 函数
当消息数超过 50 条时调用，将较早的 40 条消息压缩为摘要，保留最近 10 条完整对话。

**优点**：
- 控制 token 消耗，避免超出模型上下文限制。
- 保留关键信息，同时让 Agent 能够继续对话。

**潜在问题**：
- 摘要可能丢失细节，影响后续问答准确性。可考虑使用更先进的摘要策略（如迭代摘要、滑动窗口）。

---

### 4. `chat_with_agent`（同步版本）
- 加载历史消息，若超长则先压缩。
- 调用 `agent.invoke` 获得完整回答。
- 保存新消息及 `rag_trace` 到存储。
- 返回响应内容及 trace。

**注意**：
- 使用 `agent.invoke` 而非 `agent.astream`，适合非流式场景（如调试）。

---

### 5. `chat_with_agent_stream`（异步流式版本）—— 核心难点

这是整个模块最复杂、最关键的部分。它实现了**实时 RAG 步骤推送**和**流式生成**。

#### 设计思路
- **统一输出队列**：创建一个 `asyncio.Queue`，所有事件（`content` token 或 `rag_step`）都放入该队列。
- **后台任务**：`_agent_worker` 协程运行 Agent 的流式生成，将 token 放入队列。
- **主循环**：主生成器从队列中取事件，通过 SSE 推送给前端。
- **跨线程事件调度**：工具函数（如 `search_knowledge_base`）运行在线程池中，通过 `call_soon_threadsafe` 将 `rag_step` 事件放入队列（详见 `tools.py` 中的 `emit_rag_step`）。这里通过 `_RagStepProxy` 将 `emit_rag_step` 的调用重定向到队列的 `put_nowait`。

#### 关键代码片段
```python
class _RagStepProxy:
    def put_nowait(self, step):
        output_queue.put_nowait({"type": "rag_step", "step": step})

set_rag_step_queue(_RagStepProxy())
```
这样，工具中调用 `emit_rag_step` 时，实际是将步骤事件直接放入 `output_queue`，无需额外线程协调。

#### 异常处理与终止
- 当客户端断开（如用户点击“终止回答”），Flask 生成器会收到 `GeneratorExit`，此时主循环捕获后立即取消 `agent_task`，并等待任务结束，确保 LLM 推理被中断，节省资源。

#### 最终保存
- 在生成器结束时，从 `get_last_rag_context` 获取本次检索的 trace，发送给前端，并将完整对话保存到存储。

---

## 三、模块间的协作关系

- **`tools.py`**：提供 `search_knowledge_base`、`get_current_weather` 等工具。工具内部使用 `emit_rag_step` 实时推送步骤，并通过 `get_last_rag_context` 与 `reset_tool_call_guards` 管理 RAG 上下文。
- **`api.py`**：调用 `chat_with_agent_stream` 并包装成 SSE 响应。
- **`rag_pipeline.py`**：被 `search_knowledge_base` 调用，执行完整的检索流程。
- **存储**：`ConversationStorage` 将对话持久化到 JSON 文件。

---

## 四、潜在问题与改进建议

| 问题                                    | 影响                                                         | 改进建议                                                     |
| --------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **并发写 JSON 文件**                    | 多个请求同时保存同一会话可能导致数据损坏或丢失。             | 使用 SQLite 替代 JSON，或添加文件锁（如 `fcntl`）确保原子写入。 |
| **摘要策略单一**                        | 固定阈值 50 条消息，且摘要可能丢失重要信息。                 | 改为按 token 数动态触发摘要；使用 `ConversationSummaryBufferMemory` 自动管理。 |
| **Agent 工具调用可能重复**              | 虽然 prompt 限制一次，但 Agent 有时仍会重复调用。            | 在工具内部增加“已调用”标志，防止同一轮多次执行（已在 `tools.py` 中实现 `reset_tool_call_guards`）。 |
| **`agent.astream` 异常未充分处理**      | 若 Agent 内部抛出异常，`_agent_worker` 会捕获并放入错误事件，但主循环可能继续等待。 | 增加超时机制，避免队列永久阻塞。                             |
| **`output_queue.get()` 可能永久阻塞**   | 若后台任务异常退出且未放入 `None`，主循环会永远等待。        | 使用 `asyncio.wait_for` 设置超时，或增加健康检查。           |
| **全局 `_RagStepProxy` 可能跨请求干扰** | 每个请求都会设置新的 proxy，但若上一个请求未清理，可能造成混乱。 | 确保每次调用 `chat_with_agent_stream` 前都调用 `set_rag_step_queue(None)` 清理，且函数退出时也清理。代码中已在 `finally` 中调用，但最好在入口处也重置。 |

---

## 五、总结

`agent.py` 是整个系统的**大脑**，它利用 LangChain 强大的 Agent 能力，结合自定义工具和存储，实现了完整的对话智能体。流式版本通过精妙的队列+后台任务设计，解决了同步工具实时推送步骤的难题，使得前端能实时展示检索过程。

该模块结构清晰，职责分明，但也存在一些学生项目常见的简化设计（如 JSON 存储、固定摘要阈值），在答辩时可以提及这些权衡，并说明未来优化方向（如引入数据库、使用更智能的摘要等），展现对系统可扩展性的思考。

# 使用 LangChain 提供的 Prompt 构建 system_prompt

完全可以利用 LangChain 提供的 Prompt 模板来构建更丰富、动态的 system prompt，而不仅仅是硬编码字符串。LangChain 的 `create_agent` 函数（或其他 Agent 构建方法）通常支持直接传入 `system_prompt` 字符串，但我们可以通过其他方式将复杂的 Prompt 模板整合进去。

---

## 一、为什么使用 LangChain Prompt 模板？

- **动态内容**：可以根据用户信息、会话上下文、时间等变量动态生成 system prompt。
- **结构化**：使用 `ChatPromptTemplate` 或 `SystemMessagePromptTemplate` 可以清晰组织消息结构，方便维护。
- **可组合**：可以轻松添加 few-shot 示例、格式化指令等。

---

## 二、如何在当前项目中应用

### 方法一：将模板渲染为字符串（最简单）
如果 `create_agent` 只接受字符串，可以先构建 `ChatPromptTemplate`，然后渲染成字符串传入。

```python
from langchain.prompts import ChatPromptTemplate

# 定义模板（可包含变量）
system_template = ChatPromptTemplate.from_messages([
    ("system", "You are a {role} that loves to help users."),
    ("system", "When responding, you may use tools to assist. Use search_knowledge_base when users ask document/knowledge questions."),
    ("system", "Do not call the same tool repeatedly in one turn. At most one knowledge tool call per turn.")
])

# 渲染字符串
rendered_system = system_template.format_messages(role="cute cat bot")
# 但 format_messages 返回的是消息列表，我们需要提取其中 system 消息的内容并拼接
system_content = "\n".join([msg.content for msg in rendered_system if msg.type == "system"])

# 然后传入 create_agent
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=system_content,  # 传入字符串
    ...
)
```

### 方法二：使用 `ChatPromptTemplate` 作为 Agent 的提示词（高级）
LangChain 的新版 `create_agent` 可能支持直接传入 `prompt` 参数，该参数可以是 `ChatPromptTemplate` 或消息列表。如果支持，则可以直接使用模板，无需转换为字符串。

查阅 LangChain 文档，`create_agent` 的签名通常为：
```python
def create_agent(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    prompt: Optional[Union[PromptTemplate, ChatPromptTemplate, str]] = None,
    ...
) -> Runnable:
```

你可以这样写：
```python
from langchain.prompts import ChatPromptTemplate

system_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a {role} that loves to help users."),
    ("system", "When responding, you may use tools to assist."),
    ("system", "Use search_knowledge_base when users ask document/knowledge questions."),
    ("system", "Do not call the same tool repeatedly in one turn."),
    ("system", "Once you call search_knowledge_base and receive its result, you MUST immediately produce the Final Answer based on that result."),
    # 其他规则...
])

agent = create_agent(
    model=model,
    tools=tools,
    prompt=system_prompt,  # 直接传入 ChatPromptTemplate
    # 注意：可能需要额外传递变量值，如 role
)
```

但 `create_agent` 的 `prompt` 参数通常期望一个最终可格式化的对象。如果模板包含变量，你需要在运行时通过 `invoke` 的 `config` 或 `kwargs` 传入。LangChain 的 Agent 在调用时会自动处理这些变量吗？可能需要根据实际版本测试。

### 方法三：在 Agent 构建后动态注入 system message
另一种灵活的方式是：在调用 Agent 之前，将系统提示作为第一条消息插入到历史消息中。这样你可以完全控制提示的构建，并且可以使用任何 LangChain 的 Prompt 工具。

```python
from langchain.prompts import ChatPromptTemplate

system_prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are a {role} that loves to help users."),
    ("system", "Additional instructions: ...")
])

# 在每次对话前，构建 system message
system_messages = system_prompt_template.format_messages(role="cute cat bot")
# 注意：format_messages 返回的是消息列表，我们需要取出 system 消息的内容，或者直接将它们插入到消息列表开头

# 在 chat_with_agent_stream 中，将 system_messages 插入到 messages 列表开头
messages = storage.load(user_id, session_id)
messages = system_messages + messages
```

这种方法最灵活，完全不受 Agent 构建时 prompt 参数的限制，但需要确保 system 消息不会在每次调用时重复累积（只加一次）。

---

## 三、注意事项

1. **变量注入**：如果使用带变量的模板，需要确保变量在运行时可用。例如，你可能需要从用户信息中获取 `role` 或 `user_name` 来个性化提示。
2. **版本兼容性**：LangChain 1.0+ 中 `create_agent` 的参数可能有所不同，建议查阅官方文档或查看源码确认 `prompt` 是否支持 `ChatPromptTemplate`。
3. **流式与同步的一致性**：无论采用哪种方式，确保同步版本（`chat_with_agent`）和流式版本（`chat_with_agent_stream`）使用相同的 system prompt。
4. **避免重复**：如果通过 `create_agent` 的 `system_prompt` 参数设置，则系统提示会在 Agent 内部自动注入，无需手动处理。如果采用方法三，需注意不要重复添加。

---

## 四、建议

对于你的项目，建议**使用方法一或方法三**，因为它们简单可控，且不依赖 `create_agent` 对模板的具体支持情况。如果你希望 system prompt 能动态变化（例如根据用户角色、会话时间等），方法三是最灵活的；如果 system prompt 是静态的，方法一就足够了。

如果你决定使用方法三，记得在 `chat_with_agent_stream` 和 `chat_with_agent` 中一致地添加 system messages，并且避免在历史消息中累积多条 system 消息（例如，只在会话开始时添加一次）。可以修改 `storage.load` 后判断如果当前会话没有 system 消息，则插入。

这样，你就可以充分利用 LangChain 强大的 Prompt 模板功能，同时保持 Agent 结构的简洁。