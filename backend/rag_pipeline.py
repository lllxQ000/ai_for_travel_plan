from typing import TypedDict, Literal, List, Optional
from langgraph.graph import StateGraph, END
from langchain.chat_models import init_chat_model
from langchain_core.pydantic_v1 import BaseModel, Field
from .utils import get_env, logger
from .rag_utils import retrieve_documents, step_back_expand, generate_hypothetical_document
from .tools import emit_rag_step

# 模型初始化
API_KEY = get_env("ARK_API_KEY")
MODEL = get_env("MODEL")
BASE_URL = get_env("BASE_URL")
GRADE_MODEL = get_env("GRADE_MODEL", MODEL)

def _get_model(model_name):
    return init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0
    )

# 评分模型
class GradeDocuments(BaseModel):
    binary_score: Literal["yes", "no"] = Field(description="Relevance score")

# 路由模型
class RewriteStrategy(BaseModel):
    strategy: Literal["step_back", "hyde", "complex"]

# 状态定义
class RAGState(TypedDict):
    question: str
    query: str
    context: str
    docs: List[dict]
    route: Optional[str]
    expansion_type: Optional[str]
    expanded_query: Optional[str]
    step_back_question: Optional[str]
    step_back_answer: Optional[str]
    hypothetical_doc: Optional[str]
    rag_trace: Optional[dict]

def _format_docs(docs: List[dict]) -> str:
    if not docs:
        return ""
    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.get("metadata", {}).get("source", "Unknown")
        text = doc.get("text", "")
        parts.append(f"[{i}] {source}:\n{text}")
    return "\n\n---\n\n".join(parts)

# 节点函数
def retrieve_initial(state: RAGState) -> RAGState:
    query = state["question"]
    emit_rag_step("🔍", "正在检索知识库...")
    result = retrieve_documents(query, top_k=5)
    docs = result.get("docs", [])
    meta = result.get("meta", {})
    context = _format_docs(docs)
    emit_rag_step("✅", f"检索完成，找到 {len(docs)} 个片段")
    rag_trace = {
        "tool_used": True,
        "query": query,
        "retrieved_chunks": docs,
        "retrieval_meta": meta
    }
    return {
        "query": query,
        "docs": docs,
        "context": context,
        "rag_trace": rag_trace
    }

def grade_documents(state: RAGState) -> RAGState:
    emit_rag_step("📊", "正在评估文档相关性...")
    grader = _get_model(GRADE_MODEL).with_structured_output(GradeDocuments)
    prompt = f"""You are a grader assessing relevance of a retrieved document to a user question.
Here is the retrieved document: {state['context']}
Here is the user question: {state['question']}
Give a binary score 'yes' or 'no' to indicate whether the document is relevant."""
    try:
        response = grader.invoke([{"role": "user", "content": prompt}])
        score = response.binary_score
    except Exception as e:
        logger.error(f"Grading failed: {e}")
        score = "no"
    route = "generate_answer" if score == "yes" else "rewrite_question"
    emit_rag_step("✅" if score == "yes" else "⚠️", f"评分结果: {score}")
    rag_trace = state.get("rag_trace", {})
    rag_trace.update({"grade_score": score, "grade_route": route})
    return {"route": route, "rag_trace": rag_trace}

def rewrite_question(state: RAGState) -> RAGState:
    emit_rag_step("✏️", "正在重写查询...")
    router = _get_model(MODEL).with_structured_output(RewriteStrategy)
    prompt = f"""请根据用户问题选择最合适的查询扩展策略，仅输出策略名。
- step_back：包含具体名称、日期、代码等细节，需要先理解通用概念的问题。
- hyde：模糊、概念性、需要解释或定义的问题。
- complex：多步骤、需要分解或综合多种信息的复杂问题。
用户问题：{state['question']}"""
    try:
        decision = router.invoke([{"role": "user", "content": prompt}])
        strategy = decision.strategy
    except:
        strategy = "step_back"

    expanded_query = state["question"]
    step_back_question = ""
    step_back_answer = ""
    hypothetical_doc = ""

    if strategy in ("step_back", "complex"):
        step_back = step_back_expand(state["question"])
        step_back_question = step_back.get("step_back_question", "")
        step_back_answer = step_back.get("step_back_answer", "")
        expanded_query = step_back.get("expanded_query", state["question"])
    if strategy in ("hyde", "complex"):
        hypothetical_doc = generate_hypothetical_document(state["question"])

    emit_rag_step("🧠", f"使用策略: {strategy}")
    rag_trace = state.get("rag_trace", {})
    rag_trace.update({
        "rewrite_strategy": strategy,
        "rewrite_query": expanded_query
    })
    return {
        "expansion_type": strategy,
        "expanded_query": expanded_query,
        "step_back_question": step_back_question,
        "step_back_answer": step_back_answer,
        "hypothetical_doc": hypothetical_doc,
        "rag_trace": rag_trace
    }

def retrieve_expanded(state: RAGState) -> RAGState:
    emit_rag_step("🔄", "使用扩展查询重新检索...")
    strategy = state.get("expansion_type", "step_back")
    all_docs = []

    if strategy in ("hyde", "complex"):
        hyde_doc = state.get("hypothetical_doc") or generate_hypothetical_document(state["question"])
        res = retrieve_documents(hyde_doc, top_k=5)
        all_docs.extend(res.get("docs", []))
    if strategy in ("step_back", "complex"):
        expanded_query = state.get("expanded_query", state["question"])
        res = retrieve_documents(expanded_query, top_k=5)
        all_docs.extend(res.get("docs", []))

    # 去重
    seen = set()
    deduped = []
    for doc in all_docs:
        key = (doc.get("text"), doc.get("metadata", {}).get("source"))
        if key not in seen:
            seen.add(key)
            deduped.append(doc)

    context = _format_docs(deduped)
    emit_rag_step("✅", f"扩展检索完成，共 {len(deduped)} 个片段")
    rag_trace = state.get("rag_trace", {})
    rag_trace.update({
        "expanded_retrieved_chunks": deduped,
        "retrieval_stage": "expanded"
    })
    return {"docs": deduped, "context": context, "rag_trace": rag_trace}

# 构建图
def build_rag_graph():
    graph = StateGraph(RAGState)
    graph.add_node("retrieve_initial", retrieve_initial)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("rewrite_question", rewrite_question)
    graph.add_node("retrieve_expanded", retrieve_expanded)

    graph.set_entry_point("retrieve_initial")
    graph.add_edge("retrieve_initial", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        lambda state: state.get("route"),
        {
            "generate_answer": END,
            "rewrite_question": "rewrite_question"
        }
    )
    graph.add_edge("rewrite_question", "retrieve_expanded")
    graph.add_edge("retrieve_expanded", END)
    return graph.compile()

rag_graph = build_rag_graph()

def run_rag_pipeline(question: str) -> dict:
    result = rag_graph.invoke({
        "question": question,
        "query": question,
        "context": "",
        "docs": [],
        "route": None,
        "expansion_type": None,
        "expanded_query": None,
        "step_back_question": None,
        "step_back_answer": None,
        "hypothetical_doc": None,
        "rag_trace": None
    })
    return result