import requests
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from embedding import EmbeddingService
from chroma_client import ChromaClient
from parent_chunk_store import ParentChunkStore
from csv_loader import load_csv_knowledge_base, load_multiple_csv_files
from utils import get_env, logger
import os
import glob

# 初始化服务
embedding_service = EmbeddingService()
chroma_client = ChromaClient()
parent_store = ParentChunkStore()

# CSV 知识库是否已加载的标志
_csv_kb_initialized = False

# 配置
AUTO_MERGE_ENABLED = get_env("AUTO_MERGE_ENABLED", "true").lower() == "true"
AUTO_MERGE_THRESHOLD = int(get_env("AUTO_MERGE_THRESHOLD", "2"))
LEAF_RETRIEVE_LEVEL = int(get_env("LEAF_RETRIEVE_LEVEL", "3"))
RERANK_MODEL = get_env("RERANK_MODEL")
RERANK_BINDING_HOST = get_env("RERANK_BINDING_HOST")
RERANK_API_KEY = get_env("RERANK_API_KEY")

def _get_rerank_endpoint():
    if not RERANK_BINDING_HOST:
        return ""
    host = RERANK_BINDING_HOST.strip().rstrip("/")
    return host if host.endswith("/v1/rerank") else f"{host}/v1/rerank"

def _merge_to_parent_level(docs, threshold):
    groups = defaultdict(list)
    for doc in docs:
        parent_id = doc.get("parent_chunk_id")
        if parent_id:
            groups[parent_id].append(doc)
    parent_ids = [pid for pid, children in groups.items() if len(children) >= threshold]
    if not parent_ids:
        return docs, 0
    parent_docs = parent_store.get_documents_by_ids(parent_ids)
    parent_map = {doc["chunk_id"]: doc for doc in parent_docs}
    merged = []
    replaced = 0
    for doc in docs:
        parent_id = doc.get("parent_chunk_id")
        if parent_id and parent_id in parent_map:
            parent_doc = parent_map[parent_id].copy()
            parent_doc["score"] = max(parent_doc.get("score", 0), doc.get("score", 0))
            parent_doc["merged_from_children"] = True
            merged.append(parent_doc)
            replaced += 1
        else:
            merged.append(doc)
    return merged, replaced

def _auto_merge_documents(docs, top_k):
    if not AUTO_MERGE_ENABLED or not docs:
        return docs[:top_k], {"auto_merge_applied": False}
    merged, replaced1 = _merge_to_parent_level(docs, AUTO_MERGE_THRESHOLD)
    merged, replaced2 = _merge_to_parent_level(merged, AUTO_MERGE_THRESHOLD)
    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    merged = merged[:top_k]
    return merged, {
        "auto_merge_applied": (replaced1 + replaced2) > 0,
        "auto_merge_replaced_chunks": replaced1 + replaced2,
        "auto_merge_steps": (1 if replaced1 else 0) + (1 if replaced2 else 0)
    }

def _rerank_documents(query, docs, top_k):
    meta = {"rerank_enabled": bool(RERANK_MODEL and RERANK_API_KEY and RERANK_BINDING_HOST), "rerank_applied": False}
    if not meta["rerank_enabled"] or not docs:
        return docs[:top_k], meta
    payload = {"model": RERANK_MODEL, "query": query, "documents": [doc.get("text", "") for doc in docs], "top_n": min(top_k, len(docs)), "return_documents": False}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {RERANK_API_KEY}"}
    try:
        resp = requests.post(_get_rerank_endpoint(), json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            items = resp.json().get("results", [])
            reranked = []
            for item in items:
                idx = item.get("index")
                if isinstance(idx, int) and 0 <= idx < len(docs):
                    doc = docs[idx].copy()
                    doc["rerank_score"] = item.get("relevance_score")
                    reranked.append(doc)
            if reranked:
                meta["rerank_applied"] = True
                return reranked[:top_k], meta
    except Exception as e:
        logger.error(f"Rerank failed: {e}")
    return docs[:top_k], meta

def _get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def initialize_csv_knowledge_base():
    global _csv_kb_initialized
    if _csv_kb_initialized:
        logger.info("CSV 知识库已初始化")
        return
    try:
        project_root = _get_project_root()
        data_dir = os.path.join(project_root, "data")
        csv_pattern = os.path.join(data_dir, "knowledge_*.csv")
        csv_files = sorted(glob.glob(csv_pattern))
        if not csv_files:
            logger.warning(f"未找到 CSV 知识库文件：{csv_pattern}")
            _csv_kb_initialized = True
            return
        logger.info(f"发现 {len(csv_files)} 个 CSV 知识库文件")
        from import_knowledge import import_knowledge_files
        results = import_knowledge_files(csv_files, batch_size=50)
        logger.info(f"CSV 知识库初始化完成：共导入 {results['imported_records']} 条记录")
        _csv_kb_initialized = True
    except Exception as e:
        logger.error(f"CSV 知识库初始化失败：{e}")
        raise

def retrieve_documents(query, top_k=5, filters=None):
    candidate_k = max(top_k * 3, top_k)
    filter_expr = {"chunk_level": LEAF_RETRIEVE_LEVEL}
    if filters:
        filter_expr.update(filters)
    try:
        dense_vec = embedding_service.get_embeddings([query])[0]
        result = chroma_client.query_chunks(dense_vec, n_results=candidate_k, where=filter_expr)
        docs = []
        if result["documents"]:
            for i, doc in enumerate(result["documents"][0]):
                docs.append({"chunk_id": result["ids"][0][i], "text": doc, "score": result["distances"][0][i] if result["distances"] else 1.0, "metadata": result["metadatas"][0][i]})
        reranked, rerank_meta = _rerank_documents(query, docs, top_k)
        merged, merge_meta = _auto_merge_documents(reranked, top_k)
        meta = {"retrieval_mode": "dense", "candidate_k": candidate_k, "leaf_retrieve_level": LEAF_RETRIEVE_LEVEL, "filters_used": filters, **rerank_meta, **merge_meta}
        return {"docs": merged, "meta": meta}
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {"docs": [], "meta": {"error": str(e)}}

def step_back_expand(question):
    from utils import get_env
    from langchain.chat_models import init_chat_model
    API_KEY = get_env("ARK_API_KEY")
    MODEL = get_env("MODEL")
    BASE_URL = get_env("BASE_URL")
    model = init_chat_model(model=MODEL, model_provider="openai", api_key=API_KEY, base_url=BASE_URL, temperature=0)
    prompt = "请为以下问题提供一个更一般性、概念性的解释，然后结合原问题给出答案。\n问题：" + question + "\n\n请先解释相关概念，再回答问题。"
    try:
        response = model.invoke([{"role": "user", "content": prompt}])
        return {"step_back_question": question, "step_back_answer": response.content, "expanded_query": response.content}
    except Exception as e:
        return {"step_back_question": question, "step_back_answer": "", "expanded_query": question}

def generate_hypothetical_document(question):
    from utils import get_env
    from langchain.chat_models import init_chat_model
    API_KEY = get_env("ARK_API_KEY")
    MODEL = get_env("MODEL")
    BASE_URL = get_env("BASE_URL")
    model = init_chat_model(model=MODEL, model_provider="openai", api_key=API_KEY, base_url=BASE_URL, temperature=0.7)
    prompt = "请为以下问题生成一个假设性的答案文档。\n问题：" + question
    try:
        response = model.invoke([{"role": "user", "content": prompt}])
        return response.content
    except Exception as e:
        return ""
