# RAG 在“AI 定制出行规划助手”中的工作机制

你设想的“去哪儿”式 AI 定制出行规划助手，本质上是一个**基于用户偏好的个性化行程生成器**。RAG（检索增强生成）在这里扮演了**核心知识引擎**的角色：它让大模型不再仅凭训练时的通用知识回答，而是能实时检索你准备好的最新、最详细的旅游信息（景点介绍、交通方式、酒店推荐、用户评价等），然后基于这些具体内容生成定制化行程。下面详细拆解 RAG 在你的项目中的工作流程。

---

## 一、用户输入 → 后端接收

前端用户填写出行偏好选项，例如：
- 目的地：**桂林**
- 出行天数：**3天2晚**
- 出行人数：**2人**
- 预算：**中等**
- 兴趣偏好：**自然风光、摄影、美食**
- 出行时间：**暑假**

这些选项通过表单提交到后端 Flask 接口 `/plan/stream`（可复用之前的 `/chat/stream` 结构）。

后端接收后，将这些偏好信息**结构化**并构造一个“自然语言问题”：
> “帮我规划一个桂林3天2晚的行程，2人，中等预算，偏好自然风光、摄影和美食，时间是暑假。”

---

## 二、RAG 检索阶段

### 2.1 查询重写（可选）
系统可能会根据偏好对原始查询进行**扩展或细化**，例如：
- 若用户没有明确景点，可以通过 **Step‑Back** 生成更通用的“桂林自然风光推荐”。
- 若用户提及“摄影”，可能通过 **HyDE** 生成一段假设性描述：“桂林有哪些适合摄影的日出观景点、梯田、漓江倒影等”，然后用这段描述去检索。

### 2.2 向量化与混合检索
- 将最终查询文本通过嵌入模型（阿里云 text-embedding-v2）转化为稠密向量。
- 在 Chroma 的 `doc_chunks` 集合中执行语义检索，返回与查询最相似的 **top_k** 文档块（例如 top_k=20）。
- 可选：同时使用 BM25 稀疏检索（关键词匹配），两路结果通过 RRF 融合。

检索出的文档块可能包含：
- 景点介绍（如“象鼻山是桂林的城徽，位于漓江与桃花江交汇处……”）
- 行程建议（“第一天上午游览象鼻山，下午去芦笛岩……”）
- 美食推荐（“桂林米粉、啤酒鱼、田螺酿……”）
- 住宿推荐（“桂林两江四湖附近民宿，价格200-400元/晚……”）
- 交通信息（“桂林站到阳朔可乘坐高铁约30分钟”）

### 2.3 精排与 Auto‑merging
- 使用 Rerank API（如 Jina）对初筛的 20 个块重新打分，选出最相关的 5~8 个块。
- **Auto‑merging**：如果某个叶子块（L3）分数较低，但它的父块（L2 或 L1）包含更完整的段落，则用父块替换，避免信息碎片化。

### 2.4 上下文组装
将最终选出的文档块（可能 5~8 段）拼接成一个上下文字符串，并附带来源信息。

---

## 三、生成定制行程

### 3.1 提示词构建
将用户偏好 + 检索到的上下文 + 对话历史（如多轮对话）组装成系统提示词。例如：

```
你是一个专业的旅行规划助手。请根据以下用户偏好和提供的旅游信息，生成一份详细的桂林3天2晚行程规划。

用户偏好：
- 目的地：桂林
- 天数：3天2晚
- 人数：2人
- 预算：中等
- 兴趣：自然风光、摄影、美食
- 时间：暑假

提供的相关信息：
[检索到的文档块1]
[检索到的文档块2]
...

请按天规划行程，包含景点、餐饮、交通建议，并突出摄影点。
```

### 3.2 流式生成
LLM（Qwen3.5）根据提示词生成行程规划，并逐 token 通过 SSE 推送到前端，前端实现打字机效果。

### 3.3 输出示例
```
第一天：
- 上午：游览象鼻山（最佳拍摄点：观景台、爱情岛），建议8点前到达避开人流。
- 中午：在正阳步行街品尝桂林米粉（推荐“崇善米粉”）。
- 下午：前往芦笛岩，欣赏溶洞奇观（洞内灯光适合摄影）。
- 晚上：夜游两江四湖，拍摄日月双塔倒影。

第二天：
- 上午：乘船游览漓江精华段（杨堤-兴坪），打卡20元人民币背景图。
- 中午：在兴坪古镇吃啤酒鱼（“刘姐啤酒鱼”）。
- 下午：租电动车骑行遇龙河，拍摄田园风光。
- 晚上：观看《印象·刘三姐》实景演出。

第三天：
- 上午：登相公山，拍摄漓江第一湾日出。
- 中午：返回桂林市区，购买伴手礼（桂花糕、辣椒酱）。
- 下午：结束行程。
```

---

## 四、为什么 RAG 能让规划更“聪明”？

| 传统 LLM 生成              | RAG 增强生成                         |
| -------------------------- | ------------------------------------ |
| 依赖训练数据（可能过时）   | 基于你上传的最新旅游资料             |
| 无法知道具体餐厅、交通细节 | 从文档中提取具体商家、路线           |
| 生成内容泛泛，缺乏针对性   | 可根据用户偏好（摄影、美食）精准推荐 |
| 容易产生“幻觉”             | 内容有据可查，来源可溯源             |

---

## 五、在代码层面，RAG 是如何嵌入的？

在你的项目中，RAG 工作流位于 `rag_pipeline.py`（通过 LangGraph 实现），调用关系为：

1. 用户输入 → Flask 路由 `/plan/stream`
2. Flask 调用 `agent.chat_with_agent_stream`，Agent 内部决定调用工具 `search_knowledge_base`
3. `search_knowledge_base` 触发 `run_rag_pipeline(question)`，其中：
   - `retrieve_initial`：执行混合检索 + 精排 + 合并，返回上下文。
   - `grade_documents`：LLM 判断上下文是否足够（避免无意义重写）。
   - 若不足，`rewrite_question` 生成扩展查询。
   - `retrieve_expanded`：再次检索。
4. 最终上下文和用户偏好一起作为生成提示词，由 Agent 的 LLM 生成答案。

因此，RAG 的作用位置是**在 Agent 调用知识库工具时**，完成“检索 → 精排 → 合并 → 重写（可选）”的全流程，然后将高质量上下文交给 LLM 生成最终规划。

---

## 六、你需要准备的知识库内容

为了让 RAG 发挥最大效果，你需要预先构建旅游知识库，可以包含：
- **景点库**：名称、介绍、门票、开放时间、最佳拍摄点、交通方式。
- **行程库**：经典路线、当地向导推荐的行程。
- **美食库**：特色菜品、推荐餐厅、人均消费。
- **住宿库**：酒店/民宿名称、位置、价格、特色。
- **交通库**：机场/火车站到景区的交通方式、城市间交通时长。
- **用户评价**：从马蜂窝、携程爬取的点评片段（注意版权）。

这些信息通过文档上传接口入库，经过分块、向量化后存入 Chroma。这样，当用户提问时，就能检索到最匹配的旅游信息。

---

通过以上设计，你的“AI 定制出行规划助手”不再是简单的模板化回复，而是一个能利用海量旅游数据、根据个人偏好精准生成的智能助手。在答辩时，你可以强调 RAG 如何解决信息时效性、个性化推荐和内容可信度三大痛点，展现项目的技术深度。



是的，你可以利用 LangChain 的 **Prompt 模板**（`ChatPromptTemplate`）来构造 Step‑Back 和 HyDE 的提示词，并调用 LLM 生成扩展查询或假设文档。但需要注意：这里的“动态扩展”不是直接修改 Agent 的 `system_prompt`，而是通过 LangChain 的 **Chain** 或 **工具内部的 LLM 调用**来实现。下面分别说明两种扩展方式在 LangChain 中的实现。

---

## 一、Step‑Back 扩展

Step‑Back 需要两步：生成退步问题 → 回答退步问题。这两个步骤都可以用 LangChain 的 `ChatPromptTemplate` 配合 `LLMChain` 轻松完成。

```python
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain

# 1. 生成退步问题的提示词
step_back_prompt = ChatPromptTemplate.from_messages([
    ("system", "请将用户的具体问题抽象成更高层次、更概括的‘退步问题’，用于探寻背后的通用原理或核心概念。只输出退步问题一句话，不要解释。"),
    ("human", "{query}")
])

step_back_chain = LLMChain(llm=model, prompt=step_back_prompt)

# 2. 回答退步问题的提示词
answer_step_back_prompt = ChatPromptTemplate.from_messages([
    ("system", "请简要回答以下退步问题，提供通用原理/背景知识，控制在120字以内。只输出答案，不要列出推理过程。"),
    ("human", "{step_back_question}")
])
answer_chain = LLMChain(llm=model, prompt=answer_step_back_prompt)

def step_back_expand(query):
    step_back_question = step_back_chain.run(query=query)
    step_back_answer = answer_chain.run(step_back_question=step_back_question)
    expanded_query = f"{query}\n\n退步问题：{step_back_question}\n退步问题答案：{step_back_answer}"
    return expanded_query, step_back_question, step_back_answer
```

然后，在 RAG 检索时，你可以选择使用 `expanded_query` 替代原始查询进行检索。

---

## 二、HyDE 扩展

HyDE 只需要一步：生成一段假设性文档（不要求真实性，只要求与问题语义相关）。

```python
hyde_prompt = ChatPromptTemplate.from_messages([
    ("system", "请基于用户问题生成一段‘假设性文档’，内容应像真实资料片段，用于帮助检索相关信息。文档可以包含合理推测，但需与问题语义相关。只输出文档正文，不要标题或解释。"),
    ("human", "{query}")
])
hyde_chain = LLMChain(llm=model, prompt=hyde_prompt)

def generate_hypothetical_document(query):
    return hyde_chain.run(query=query)
```

生成的假设文档可以直接作为检索查询（向量化后去检索），或与原始问题结合使用。

---

## 三、动态选择策略

你可以在 RAG 流程中，根据用户输入的关键词（如“摄影”、“预算”）或通过一个轻量级 LLM 分类来决定使用哪种策略。LangChain 的 `RunnableBranch` 或简单的 `if-else` 均可。

```python
def choose_strategy(query):
    # 可调用 LLM 进行策略选择，或基于规则
    if "摄影" in query or "拍照" in query:
        return "hyde"
    elif "是什么" in query or "概念" in query:
        return "step_back"
    else:
        return "none"
```

然后在 RAG 的 `retrieve_initial` 或 `retrieve_expanded` 中调用相应函数生成扩展查询。

---

## 四、关于 Agent 的 `system_prompt`

你的 Agent 的 `system_prompt` 是全局指令，用来告诉 Agent 如何行为（例如“使用知识库工具”、“不要重复调用”等）。它**不直接参与**查询扩展，因为查询扩展发生在工具内部，而不是 Agent 决策时。你不需要在 `system_prompt` 里写扩展逻辑，只需在工具函数内部利用 LangChain 的 Chain 完成即可。

但你可以**在系统提示中给 Agent 增加一个指示**，例如：“如果用户问题比较模糊，你可以考虑先进行查询扩展”，但这只是给 Agent 的提示，真正的扩展实现仍在工具代码中。

---

## 五、完整流程整合

在 `tools.py` 中，你的 `search_knowledge_base` 工具可以这样设计：

```python
@tool
def search_knowledge_base(query: str) -> str:
    emit_rag_step("🔍", "开始检索知识库...")
    # 1. 可选：根据 query 选择扩展策略
    if "摄影" in query:
        hypothetical = generate_hypothetical_document(query)
        # 用假设文档去检索
        result = retrieve_documents(hypothetical, top_k=5)
    elif "是什么" in query:
        expanded_query, _, _ = step_back_expand(query)
        result = retrieve_documents(expanded_query, top_k=5)
    else:
        result = retrieve_documents(query, top_k=5)
    context = "\n\n".join([doc['text'] for doc in result.get('docs', [])])
    return context if context else "未找到相关信息。"
```

这样，你就利用 LangChain 的 Prompt 模板和 LLMChain 实现了动态扩展，同时保持了 Agent 的简洁。

---

## 总结

- **LangChain 提供了完整的工具**（`ChatPromptTemplate`、`LLMChain`）来实现 Step‑Back 和 HyDE，无需额外引入其他框架。
- 这些扩展逻辑应放在 **工具内部**，而不是 Agent 的 `system_prompt`。
- 你可以根据用户输入的关键词或使用一个轻量级 LLM 分类器来动态选择扩展策略，实现更智能的检索增强。

通过这种方式，你的 RAG 系统就能根据用户提问的特点，灵活地调整查询方式，提升检索质量和最终答案的准确性。