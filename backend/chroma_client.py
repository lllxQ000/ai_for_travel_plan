import chromadb
from chromadb.config import Settings
from utils import logger
from typing import List, Dict, Optional, Any


class ChromaClient:
    """
    Chroma 向量数据库客户端
    支持多种类型知识库的可扩展设计

    集合设计：
    - knowledge_{source_name}: 动态创建的知识库集合（按 CSV 源文件命名）
    - doc_chunks: 文档分块集合（含向量）- 用于非结构化文档
    """

    def __init__(self):
        # 使用项目根目录的 data 目录（backend 的上一级）
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.persist_dir = os.path.join(project_root, "data", "chroma")
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self._knowledge_collections: Dict[str, Any] = {}  # 缓存知识库集合引用
        self._init_base_collections()

    def _init_base_collections(self):
        """初始化基础集合（非知识库相关）"""
        # 文档分块集合（含向量）- 用于 PDF/DOCX 等非结构化文档
        self.chunks_collection = self.client.get_or_create_collection(
            name="doc_chunks",
            metadata={"hnsw:space": "cosine"}
        )

    def get_knowledge_collection(self, source_name: str) -> Any:
        """
        获取或创建知识库集合

        扩展性设计：
        - 每个 CSV 源文件对应一个独立的 collection
        - 按需创建，自动缓存

        Args:
            source_name: 知识库来源标识（通常是 CSV 文件名不含扩展名）

        Returns:
            Chroma Collection 对象
        """
        if source_name not in self._knowledge_collections:
            collection_name = f"knowledge_{source_name}"
            self._knowledge_collections[source_name] = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"创建/获取知识库集合：{collection_name}")
        return self._knowledge_collections[source_name]

    def list_knowledge_collections(self) -> List[str]:
        """列出所有知识库集合名称"""
        all_collections = self.client.list_collections()
        return [c.name for c in all_collections if c.name.startswith("knowledge_")]

    # ========== 知识库操作方法 ==========

    def add_knowledge_records(
        self,
        source_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        documents: List[str]
    ) -> int:
        """
        添加知识库记录到指定集合

        Args:
            source_name: 知识库来源标识
            ids: 记录 ID 列表
            embeddings: 向量列表
            metadatas: 元数据列表
            documents: 文档内容列表

        Returns:
            成功添加的记录数
        """
        collection = self.get_knowledge_collection(source_name)

        # 过滤掉已存在的 ID，避免重复添加
        existing = collection.get(ids=ids)
        existing_ids = set(existing['ids']) if existing['ids'] else set()

        new_ids = []
        new_embeddings = []
        new_metadatas = []
        new_documents = []

        for i, record_id in enumerate(ids):
            if record_id not in existing_ids:
                new_ids.append(record_id)
                new_embeddings.append(embeddings[i])
                new_metadatas.append(metadatas[i])
                new_documents.append(documents[i])

        if new_ids:
            collection.add(
                ids=new_ids,
                embeddings=new_embeddings,
                metadatas=new_metadatas,
                documents=new_documents
            )
            logger.info(f"向知识库 {source_name} 添加 {len(new_ids)} 条新记录")

        # 返回实际添加的数量（包括之前已存在的）
        return len(new_ids)

    def add_knowledge_records_batch(
        self,
        source_name: str,
        records: List[Dict],
        embeddings: List[List[float]],
        batch_size: int = 100
    ) -> int:
        """
        批量添加知识库记录（支持大数据量）

        Args:
            source_name: 知识库来源标识
            records: 记录列表，每个记录包含 {'id', 'document', 'metadata'}
            embeddings: 向量列表
            batch_size: 批次大小

        Returns:
            成功添加的记录数
        """
        collection = self.get_knowledge_collection(source_name)
        total_added = 0

        for i in range(0, len(records), batch_size):
            batch_end = min(i + batch_size, len(records))
            batch_records = records[i:batch_end]
            batch_embeddings = embeddings[i:batch_end]

            batch_ids = [r['id'] for r in batch_records]
            batch_documents = [r['document'] for r in batch_records]
            batch_metadatas = [r['metadata'] for r in batch_records]

            collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                documents=batch_documents
            )
            total_added += len(batch_ids)
            logger.info(f"批量添加 {len(batch_ids)} 条记录，累计 {total_added}/{len(records)}")

        return total_added

    def query_knowledge(
        self,
        source_name: str,
        query_embedding: List[float],
        n_results: int = 10,
        where_filter: Optional[Dict] = None
    ) -> Dict:
        """
        查询知识库

        Args:
            source_name: 知识库来源标识
            query_embedding: 查询向量
            n_results: 返回结果数量
            where_filter: 元数据过滤条件

        Returns:
            查询结果字典
        """
        collection = self.get_knowledge_collection(source_name)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )

    def query_knowledge_across_all(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where_filter: Optional[Dict] = None
    ) -> Dict:
        """
        跨所有知识库集合查询

        Args:
            query_embedding: 查询向量
            n_results: 每个集合返回的结果数量
            where_filter: 元数据过滤条件

        Returns:
            合并后的查询结果
        """
        all_results = {
            'ids': [],
            'documents': [],
            'metadatas': [],
            'distances': [],
            'sources': []
        }

        knowledge_sources = self.list_knowledge_collections()

        for source in knowledge_sources:
            source_name = source.replace("knowledge_", "", 1)
            collection = self.get_knowledge_collection(source_name)

            try:
                result = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where_filter
                )

                if result['ids'] and result['ids'][0]:
                    for i in range(len(result['ids'][0])):
                        all_results['ids'].append(result['ids'][0][i])
                        all_results['documents'].append(result['documents'][0][i] if result['documents'] else "")
                        all_results['metadatas'].append(result['metadatas'][0][i] if result['metadatas'] else {})
                        all_results['distances'].append(result['distances'][0][i] if result['distances'] else None)
                        all_results['sources'].append(source_name)
            except Exception as e:
                logger.error(f"查询知识库 {source} 失败：{e}")
                continue

        # 按距离排序（如果有距离信息）
        if all_results['distances'] and all_results['distances'][0] is not None:
            sorted_indices = sorted(range(len(all_results['distances'])),
                                   key=lambda i: all_results['distances'][i] or float('inf'))
            all_results = {k: [v[i] for i in sorted_indices][:n_results]
                          for k, v in all_results.items()}

        return all_results

    def delete_knowledge_collection(self, source_name: str):
        """删除指定知识库集合"""
        collection_name = f"knowledge_{source_name}"
        self.client.delete_collection(name=collection_name)
        if source_name in self._knowledge_collections:
            del self._knowledge_collections[source_name]
        logger.info(f"已删除知识库集合：{collection_name}")

    def get_knowledge_count(self, source_name: str) -> int:
        """获取知识库中的记录数量"""
        collection = self.get_knowledge_collection(source_name)
        return collection.count()

    # ========== 原有方法保持不变（向后兼容） ==========

    def add_chunks(self, ids, embeddings, metadatas, documents):
        """添加叶子块（带向量）"""
        self.chunks_collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

    def query_chunks(self, query_embedding, n_results=10, where=None):
        """语义检索"""
        return self.chunks_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )


    # 会话和消息操作


# ========== 便捷函数 ==========

def import_csv_to_knowledge_base(
    csv_paths: List[str],
    embedding_service,
    collection_name: Optional[str] = None
) -> Dict[str, int]:
    """
    便捷函数：将 CSV 文件导入知识库

    Args:
        csv_paths: CSV 文件路径列表
        embedding_service: 向量化服务
        collection_name: 可选的集合名称前缀，默认为 knowledge_{source_name}

    Returns:
        字典，key 为文件名，value 为导入的记录数
    """
    from csv_loader import load_csv_knowledge_base

    chroma_client = ChromaClient()
    results = {}

    for csv_path in csv_paths:
        logger.info(f"正在导入：{csv_path}")

        # 加载 CSV
        docs = load_csv_knowledge_base(csv_path)

        # 获取向量化结果
        contents = [doc.page_content for doc in docs]
        embeddings = embedding_service.get_embeddings(contents)

        # 提取元数据和 ID
        source_name = collection_name or csv_path.split('/')[-1].replace('.csv', '')
        ids = [f"{source_name}_{doc.metadata.get('record_id', i)}" for i, doc in enumerate(docs)]
        metadatas = [doc.metadata for doc in docs]

        # 导入到 Chroma
        count = chroma_client.add_knowledge_records(
            source_name=source_name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=contents
        )

        results[csv_path] = count
        logger.info(f"导入完成：{csv_path}, 新增 {count} 条记录")

    return results


if __name__ == "__main__":
    # 测试代码
    client = ChromaClient()

    print("=== 当前知识库集合 ===")
    collections = client.list_knowledge_collections()
    for c in collections:
        print(f"  {c}")

    print("\n=== 测试完成 ===")
