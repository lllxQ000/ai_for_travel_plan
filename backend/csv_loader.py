"""
CSV 知识库加载器
技术原理：将结构化 CSV 数据转换为带元数据的 Document 对象
面试考点：数据预处理、元数据提取、向量化策略
"""
import csv
from typing import List, Dict
from langchain.schema import Document


class CSVKnowledgeBaseLoader:
    """
    CSV 格式知识库加载器
    将旅游景点 CSV 转换为可用于 RAG 检索的 Document 列表
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    def load(self) -> List[Document]:
        """
        加载 CSV 并转换为 Document 列表
        
        每个 Document 包含：
        - page_content: 景点的完整描述文本（用于向量化）
        - metadata: 结构化元数据（用于过滤和排序）
        
        技术原理：
        1. 将结构化字段拼接为自然语言描述
        2. 提取可用于过滤的元数据（城市、适合人群、价格等）
        3. 便于后续语义检索 + 元数据过滤的混合检索
        """
        documents = []
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # 1. 构建自然语言描述（用于向量化）
                content = self._build_description(row)
                
                # 2. 提取结构化元数据（用于过滤）
                metadata = self._extract_metadata(row)
                
                # 3. 创建 Document 对象
                doc = Document(page_content=content, metadata=metadata)
                documents.append(doc)
        
        return documents
    
    def _build_description(self, row: Dict[str, str]) -> str:
        """
        将 CSV 行转换为自然语言描述
        
        面试考点：为什么要转为自然语言？
        答：向量模型对自然语言的理解更好，语义更丰富
        """
        parts = [
            f"【{row.get('景点名称', '')}】",
            f"位于{row.get('城市', '')}",
            f"适合{row.get('适合人群', '')}游客游玩",
            f"建议游玩时长{row.get('游玩时长', '')}",
            f"门票价格{row.get('门票价格', '0')}元",
            f"最佳游览季节为{row.get('最佳季节', '')}",
            f"特色标签：{row.get('标签', '')}",
            f"详细介绍：{row.get('描述', '')}",
            f"推荐游览顺序：第{row.get('推荐游览顺序', '')}站"
        ]
        
        return "；".join(parts)
    
    def _extract_metadata(self, row: Dict[str, str]) -> Dict:
        """
        提取结构化元数据
        
        用途：
        1. 支持精确过滤（如只检索北京的景点）
        2. 支持排序（按推荐顺序）
        3. 支持范围查询（如门票<=100 元）
        
        面试考点：元数据在向量检索中的作用
        答：先通过元数据过滤缩小范围，再进行语义检索，提升效率和精度
        """
        # 处理分号分隔的列表字段
        suitable_for = row.get('适合人群', '').split(';')
        tags = row.get('标签', '').split(';')
        
        # 解析门票价格（处理空值和非数字）
        try:
            price = int(row.get('门票价格', '0') or '0')
        except ValueError:
            price = 0
        
        return {
            "city": row.get('城市', ''),
            "attraction_name": row.get('景点名称', ''),
            "suitable_for": suitable_for,  # 列表，方便 $in 查询
            "duration": row.get('游玩时长', ''),
            "price": price,  # 数字，方便范围查询
            "season": row.get('最佳季节', ''),
            "tags": tags,  # 列表
            "description": row.get('描述', ''),
            "order": int(row.get('推荐游览顺序', '99') or '99'),
            "source": "knowledge_base.csv"
        }


def load_csv_knowledge_base(csv_path: str) -> List[Document]:
    """
    便捷函数：加载 CSV 知识库
    
    使用示例：
    ```python
    from document_loader import load_csv_knowledge_base
    
    docs = load_csv_knowledge_base('data/knowledge_base.csv')
    
    # 向量化
    embeddings = embedding_service.get_embeddings([doc.page_content for doc in docs])
    
    # 存入 Chroma
    chroma_client.add_chunks(
        ids=[doc.metadata['attraction_name'] for doc in docs],
        embeddings=embeddings,
        metadatas=[doc.metadata for doc in docs],
        documents=[doc.page_content for doc in docs]
    )
    ```
    """
    loader = CSVKnowledgeBaseLoader(csv_path)
    return loader.load()


if __name__ == "__main__":
    # 测试代码
    docs = load_csv_knowledge_base("data/knowledge_base.csv")
    print(f"成功加载 {len(docs)} 个景点")
    
    # 打印第一个景点示例
    if docs:
        print("\n=== 第一个景点示例 ===")
        print(f"内容：{docs[0].page_content[:200]}...")
        print(f"元数据：{docs[0].metadata}")
