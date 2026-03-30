import requests
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .embedding import EmbeddingService
from .chroma_client import ChromaClient
from .parent_chunk_store import ParentChunkStore
from .csv_loader import load_csv_knowledge_base
from .utils import get_env, logger

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

def _merge_to_parent_level(docs: List[dict], threshold: int) -> Tuple[List[dict], int]:
    """将满足阈值条件的子块替换为父块"""
    groups = defaultdict(list)
    for doc in docs:
        parent_id = doc.get("parent_chunk_id")
        if parent_id:
            groups[parent_id].append(doc)

    parent_ids = [pid for pid, children in groups.items() if len(children) >= threshold]
    if not parent_ids:
        return docs, 0

    parent_docs = parent_store.get_documents_by_ids(parent_ids)
    parent_map = {doc['chunk_id']: doc for doc in parent_docs}

    merged = []
    replaced = 0
    for doc in docs:
        parent_id = doc.get("parent_chunk_id")
        if parent_id and parent_id in parent_map:
            parent_doc = parent_map[parent_id].copy()
            parent_doc['score'] = max(parent_doc.get('score', 0), doc.get('score', 0))
            parent_doc['merged_from_children'] = True
            merged.append(parent_doc)
            replaced += 1
        else:
            merged.append(doc)
    return merged, replaced

def _auto_merge_documents(docs: List[dict], top_k: int) -> Tuple[List[dict], Dict]:
    if not AUTO_MERGE_ENABLED or not docs:
        return docs[:top_k], {"auto_merge_applied": False}

    # 第一次合并 L3->L2
    merged, replaced1 = _merge_to_parent_level(docs, AUTO_MERGE_THRESHOLD)
    # 第二次合并 L2->L1
    merged, replaced2 = _merge_to_parent_level(merged, AUTO_MERGE_THRESHOLD)

    merged.sort(key=lambda x: x.get('score', 0), reverse=True)
    merged = merged[:top_k]

    return merged, {
        "auto_merge_applied": (replaced1 + replaced2) > 0,
        "auto_merge_replaced_chunks": replaced1 + replaced2,
        "auto_merge_steps": (1 if replaced1 else 0) + (1 if replaced2 else 0)
    }

def _rerank_documents(query: str, docs: List[dict], top_k: int) -> Tuple[List[dict], Dict]:
    meta = {
        "rerank_enabled": bool(RERANK_MODEL and RERANK_API_KEY and RERANK_BINDING_HOST),
        "rerank_applied": False
    }
    if not meta["rerank_enabled"] or not docs:
        return docs[:top_k], meta

    payload = {
        "model": RERANK_MODEL,
        "query": query,
        "documents": [doc.get("text", "") for doc in docs],
        "top_n": min(top_k, len(docs)),
        "return_documents": False
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RERANK_API_KEY}"
    }
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

def initialize_csv_knowledge_base():
    """
    初始化 CSV 知识库（一次性操作）
    将 CSV 中的景点数据向量化并存入 Chroma
    
    技术原理：
    1. 加载 CSV 并转换为 Document
    2. 批量向量化
    3. 存入 Chroma（带元数据）
    
    面试考点：为什么需要预向量化？
    答：避免每次查询时都向量化所有文档，提升效率
    """
    global _csv_kb_initialized
    
    if _csv_kb_initialized:
        logger.info("CSV 知识库已初始化")
        return
    
    try:
        # 1. 加载 CSV
        csv_path = "data/knowledge_base.csv"
        docs = load_csv_knowledge_base(csv_path)
        logger.info(f"从 CSV 加载了 {len(docs)} 个景点")
        
        # 2. 批量向量化
        texts = [doc.page_content for doc in docs]
        embeddings = embedding_service.get_embeddings(texts)
        logger.info(f"完成向量化，共 {len(embeddings)} 个向量")
        
        # 3. 存入 Chroma
        ids = [f"attraction_{doc.metadata['attraction_name']}" for doc in docs]
        metadatas = [doc.metadata for doc in docs]
        
        chroma_client.add_chunks(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        
        _csv_kb_initialized = True
        logger.info("CSV 知识库初始化完成")
        
    except Exception as e:
        logger.error(f"CSV 知识库初始化失败：{e}")
        raise


def retrieve_documents(query: str, top_k: int = 5, filters: Dict = None) -> Dict:
    """
    主检索入口：混合检索 -> Rerank -> Auto-merging
    
    参数说明：
    - query: 自然语言查询（由表单转换而来）
    - top_k: 返回的文档数量
    - filters: 元数据过滤器（可选）
      示例：{"city": "北京", "suitable_for": ["家庭"]}
    
    技术原理：
    1. 先通过元数据过滤缩小范围（精确匹配）
    2. 再进行语义检索（模糊匹配）
    3. 提升检索效率和精度
    
    面试考点：为什么结合元数据过滤？
    答：纯向量检索可能召回不相关结果（如用户要去北京，却检索到上海景点）
        元数据过滤可以确保基本相关性，向量检索负责语义匹配
    """
    candidate_k = max(top_k * 3, top_k)
    
    # 构建过滤器：如果没有传入，使用默认级别过滤
    filter_expr = {"chunk_level": LEAF_RETRIEVE_LEVEL}
    if filters:
        filter_expr.update(filters)
    
    try:
        # 向量化查询
        dense_vec = embedding_service.get_embeddings([query])[0]
        
        # 语义检索（带过滤）
        result = chroma_client.query_chunks(dense_vec, n_results=candidate_k, where=filter_expr)
        
        docs = []
        if result['documents']:
            for i, doc in enumerate(result['documents'][0]):
                docs.append({
                    "chunk_id": result['ids'][0][i],
                    "text": doc,
                    "score": result['distances'][0][i] if result['distances'] else 1.0,
                    "metadata": result['metadatas'][0][i]
                })
        
        # Rerank
        reranked, rerank_meta = _rerank_documents(query, docs, top_k)
        
        # Auto-merge
        merged, merge_meta = _auto_merge_documents(reranked, top_k)
        
        meta = {
            "retrieval_mode": "dense",
            "candidate_k": candidate_k,
            "leaf_retrieve_level": LEAF_RETRIEVE_LEVEL,
            "filters_used": filters,
            **rerank_meta,
            **merge_meta
        }
        return {"docs": merged, "meta": meta}
        
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {"docs": [], "meta": {"error": str(e)}}