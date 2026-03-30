"""
CSV 知识库与表单交互完整流程示例

技术原理总结：
1. 用户输入（JSON）vs 知识库（CSV）是两种不同用途的数据格式
2. JSON 用于动态查询，CSV 用于静态知识存储
3. 通过向量化和元数据过滤将两者结合

面试考点：
- 为什么要用 CSV 而不是直接存数据库？
  答：CSV 便于编辑维护，可版本控制，适合中小规模知识（<10 万条）
  
- JSON 和 CSV 如何协作？
  答：JSON 查询 → 向量化 → 语义检索 CSV → 返回匹配景点 → LLM 生成个性化行程
"""

# ==================== 步骤 1: CSV 知识库加载 ====================

from backend.csv_loader import load_csv_knowledge_base

# 加载 CSV
docs = load_csv_knowledge_base("data/knowledge_base.csv")

print(f"加载了 {len(docs)} 个景点")
print(f"\n第一个景点内容:")
print(docs[0].page_content)
print(f"\n元数据:")
print(docs[0].metadata)

# ==================== 步骤 2: 向量化并存入 Chroma ====================

from backend.rag_utils import initialize_csv_knowledge_base

# 初始化（应用启动时一次性操作）
initialize_csv_knowledge_base()

# ==================== 步骤 3: 前端表单提交 JSON ====================

# 前端发送的 JSON 数据（示例）
form_json = {
    "user_id": "user_123",
    "preferences": {
        "duration_days": 5,
        "trip_type": "family",
        "style": "relaxed",
        "origin_city": "上海",
        "destination": "北京",
        "budget_level": "medium",
        "interests": ["美食", "拍照"]
    },
    "message": "希望安排适合老人的行程"
}

# ==================== 步骤 4: 后端处理表单 ====================

from backend.schema import ChatRequest

# Pydantic 自动验证 JSON 结构
req = ChatRequest(**form_json)

print(f"\n验证通过的请求:")
print(f"目的地：{req.preferences.destination}")
print(f"出行类型：{req.preferences.trip_type}")

# ==================== 步骤 5: 构建查询和过滤器 ====================

from backend.app import build_query_from_preferences, build_metadata_filters

# 5.1 构建自然语言查询（用于向量检索）
query = build_query_from_preferences(req.preferences)
print(f"\n生成的查询:\n{query}")

# 5.2 构建元数据过滤器（用于精确过滤）
filters = build_metadata_filters(req.preferences)
print(f"\n生成的过滤器:\n{filters}")
# 输出示例：{'city': '北京', 'suitable_for': {'$in': ['家庭', '所有人']}, 'price': {'$lte': 300}}

# ==================== 步骤 6: 执行检索 ====================

from backend.rag_utils import retrieve_documents

# 带过滤器的语义检索
result = retrieve_documents(query, top_k=5, filters=filters)

print(f"\n检索到的景点:")
for doc in result['docs']:
    print(f"- {doc['metadata']['attraction_name']} (门票：¥{doc['metadata']['price']})")

# ==================== 步骤 7: 格式化上下文 ====================

def _format_docs(docs):
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.get("metadata", {}).get("attraction_name", "Unknown")
        text = doc.get("text", "")
        parts.append(f"[{i}] {source}:\n{text}")
    return "\n\n---\n\n".join(parts)

context = _format_docs(result['docs'])
print(f"\n格式化的上下文:\n{context[:500]}...")

# ==================== 步骤 8: LLM 生成个性化行程 ====================

from langchain.chat_models import init_chat_model
from backend.utils import get_env

# 初始化模型
model = init_chat_model(
    model=get_env("MODEL"),
    model_provider="openai",
    api_key=get_env("ARK_API_KEY"),
    base_url=get_env("BASE_URL"),
    temperature=0.7
)

# 构建 Prompt
prompt = f"""你是一位专业的旅行规划师。请根据以下信息为用户规划行程：

【用户需求】
{query}
用户补充：{req.message}

【检索到的景点信息】
{context}

请生成一个详细的{req.preferences.duration_days}天行程规划，包括：
1. 每天的行程安排（上午、下午、晚上）
2. 景点之间的交通建议
3. 餐饮推荐
4. 注意事项（特别是针对{req.preferences.trip_type}游客）

请用友好的语气，以清晰的 Markdown 格式输出。"""

# 调用 LLM
response = model.invoke(prompt)
print(f"\n=== AI 生成的行程规划 ===\n{response.content}")

# ==================== 完整流程总结 ====================

"""
完整数据流：

1. CSV 知识库
   └─> 加载 → Document 列表
       └─> 向量化 → 存入 Chroma

2. 用户提交表单
   └─> JSON → Pydantic 验证
       └─> 构建查询 + 过滤器
           └─> 检索 Chroma（向量 + 元数据）
               └─> 格式化上下文
                   └─> LLM 生成个性化行程
                       └─> SSE 流式返回前端

关键技术点：
- JSON vs CSV：动态查询 vs 静态知识
- 向量化：将文本转为语义向量
- 元数据过滤：精确匹配（城市、价格等）
- 语义检索：模糊匹配（兴趣、风格等）
- RAG：检索增强生成，避免 LLM 幻觉
"""
