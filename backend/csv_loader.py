"""
CSV 知识库加载器
技术原理：将结构化 CSV 数据转换为带元数据的 Document 对象
面试考点：数据预处理、元数据提取、向量化策略
"""
import csv
import os
import re
from typing import List, Dict, Optional
from langchain.schema import Document


def extract_days_from_product_name(product_name: str) -> Optional[int]:
    """
    从产品名称中提取天数（"X 日"或"X 日 X 晚"格式）

    示例：
    - "广西桂林 5 日 4 晚跟团游" -> 5
    - "桂林 + 阳朔 2 日 1 晚跟团游" -> 2
    - "桂林 4 日 3 晚半自助游" -> 4
    """
    # 匹配 "X 日"或"X 日 X 晚"格式（无空格）
    match = re.search(r'(\d+)日', product_name)
    if match:
        return int(match.group(1))
    return None


class CSVKnowledgeBaseLoader:
    """
    CSV 格式知识库加载器 - 支持可扩展的列配置
    将旅游产品/线路 CSV 转换为可用于 RAG 检索的 Document 列表

    支持的 CSV 格式：
    - 第一列：记录序号（空值列名，作为 ID）
    - 线路名称：产品名称
    - 轨迹：行程路线
    - 销量：销售数量
    - 评论数：用户评论数量

    扩展方式：通过 column_config 配置不同 CSV 的列映射
    """

    # 默认列配置 - 针对当前旅游产品 CSV
    DEFAULT_COLUMN_CONFIG = {
        "id_column": "",  # 第一列为空值列名，记录序号
        "name_column": "线路名称",
        "route_column": "轨迹",
        "sales_column": "销量",
        "reviews_column": "评论数",
    }

    def __init__(self, file_path: str, column_config: Optional[Dict] = None):
        """
        初始化加载器

        Args:
            file_path: CSV 文件路径
            column_config: 列配置字典，支持自定义不同 CSV 的列映射
                          默认使用 DEFAULT_COLUMN_CONFIG
        """
        self.file_path = file_path
        self.column_config = column_config or self.DEFAULT_COLUMN_CONFIG
        # 从文件名提取知识库来源标识
        self.source_name = os.path.basename(file_path).replace('.csv', '')

    def load(self) -> List[Document]:
        """
        加载 CSV 并转换为 Document 列表

        每个 Document 包含：
        - page_content: 旅游产品的完整描述文本（用于向量化）
        - metadata: 结构化元数据（用于过滤和排序）

        技术原理：
        1. 将结构化字段拼接为自然语言描述
        2. 提取可用于过滤的元数据（销量、评论数等）
        3. 便于后续语义检索 + 元数据过滤的混合检索
        """
        documents = []

        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            for idx, row in enumerate(reader):
                # 1. 构建自然语言描述（用于向量化）
                content = self._build_description(row)

                # 2. 提取结构化元数据（用于过滤）
                metadata = self._extract_metadata(row, idx)

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
        name = row.get(self.column_config["name_column"], "")
        route = row.get(self.column_config["route_column"], "")
        sales = row.get(self.column_config["sales_column"], "0")
        reviews = row.get(self.column_config["reviews_column"], "0")

        # 构建自然语言描述
        parts = [
            f"【旅游产品】{name}",
            f"行程轨迹：{route}",
            f"销量：{sales}件",
            f"评论数：{reviews}条",
        ]

        return "；".join(parts)

    def _extract_metadata(self, row: Dict[str, str], row_index: int) -> Dict:
        """
        提取结构化元数据

        用途：
        1. 支持精确过滤（如只检索某条线路）
        2. 支持排序（按销量、评论数）
        3. 支持范围查询（如销量>=10000）

        面试考点：元数据在向量检索中的作用
        答：先通过元数据过滤缩小范围，再进行语义检索，提升效率和精度
        """
        # 处理数值字段
        try:
            sales = int(row.get(self.column_config["sales_column"], "0") or "0")
        except ValueError:
            sales = 0

        try:
            reviews = int(row.get(self.column_config["reviews_column"], "0") or "0")
        except ValueError:
            reviews = 0

        # 获取记录序号（第一列）
        id_column_name = self.column_config["id_column"]
        if id_column_name and id_column_name in row:
            record_id = row.get(id_column_name, str(row_index))
        else:
            # 如果第一列为空值列名，使用行索引 +1 作为记录序号
            record_id = str(row_index + 1)

        # 提取天数，如果为 None 则设为 0
        days = extract_days_from_product_name(row.get(self.column_config["name_column"], ""))
        if days is None:
            days = 0

        # 处理产品名称和路线，确保不为 None
        product_name = row.get(self.column_config["name_column"], "") or ""
        route = row.get(self.column_config["route_column"], "") or ""

        return {
            "product_name": product_name,
            "route": route,
            "sales": sales,
            "reviews": reviews,
            "record_id": record_id,
            "source": self.source_name,
            "row_index": row_index,
            "days": days,
        }


class MultiCSVKnowledgeBaseLoader:
    """
    多 CSV 文件知识库加载器
    支持一次性加载多个 CSV 文件，并可扩展支持不同列配置

    扩展性设计：
    - 通过 register_loader_config() 注册不同 CSV 的列配置
    - 自动根据文件名匹配预定义配置
    """

    def __init__(self):
        self.loaders = []
        self.config_registry = {}  # 文件名模式 -> 列配置映射

    def register_loader_config(self, file_pattern: str, column_config: Dict):
        """
        注册不同 CSV 文件的列配置

        Args:
            file_pattern: 文件名匹配模式（如 'knowledge_*' 或 'product_*.csv'）
            column_config: 该类型 CSV 的列配置
        """
        self.config_registry[file_pattern] = column_config

    def add_csv_file(self, file_path: str, column_config: Optional[Dict] = None) -> 'MultiCSVKnowledgeBaseLoader':
        """
        添加 CSV 文件到加载队列

        Args:
            file_path: CSV 文件路径
            column_config: 可选的列配置，不提供则自动匹配注册的配置

        Returns:
            self，支持链式调用
        """
        if column_config is None:
            # 尝试匹配已注册的配置
            filename = os.path.basename(file_path)
            column_config = self._match_config(filename)

        loader = CSVKnowledgeBaseLoader(file_path, column_config)
        self.loaders.append(loader)
        return self

    def _match_config(self, filename: str) -> Dict:
        """根据文件名匹配列配置"""
        import fnmatch
        for pattern, config in self.config_registry.items():
            if fnmatch.fnmatch(filename, pattern):
                return config
        # 默认配置
        return CSVKnowledgeBaseLoader.DEFAULT_COLUMN_CONFIG

    def load_all(self) -> List[Document]:
        """
        加载所有已添加的 CSV 文件

        Returns:
            所有 Document 对象的列表
        """
        all_documents = []
        for loader in self.loaders:
            docs = loader.load()
            all_documents.extend(docs)
        return all_documents

    def load_by_file(self) -> Dict[str, List[Document]]:
        """
        按文件分别加载，返回文件名 -> Document 列表的映射

        Returns:
            字典，key 为文件名，value 为该文件的 Document 列表
        """
        result = {}
        for loader in self.loaders:
            filename = os.path.basename(loader.file_path)
            result[filename] = loader.load()
        return result


def load_csv_knowledge_base(csv_path: str, column_config: Optional[Dict] = None) -> List[Document]:
    """
    便捷函数：加载单个 CSV 知识库

    使用示例：
    ```python
    from csv_loader import load_csv_knowledge_base

    docs = load_csv_knowledge_base('data/knowledge_1.csv')
    ```
    """
    loader = CSVKnowledgeBaseLoader(csv_path, column_config)
    return loader.load()


def load_multiple_csv_files(file_paths: List[str]) -> List[Document]:
    """
    便捷函数：加载多个 CSV 文件

    使用示例：
    ```python
    from csv_loader import load_multiple_csv_files

    files = ['data/knowledge_1.csv', 'data/knowledge_2.csv', 'data/knowledge_3.csv']
    docs = load_multiple_csv_files(files)
    ```
    """
    multi_loader = MultiCSVKnowledgeBaseLoader()
    for path in file_paths:
        multi_loader.add_csv_file(path)
    return multi_loader.load_all()


if __name__ == "__main__":
    # 测试代码 - 加载多个 CSV 文件
    import sys
    sys.path.append('..')

    print("=== 测试单个 CSV 加载 ===")
    docs = load_csv_knowledge_base("../data/knowledge_1.csv")
    print(f"knowledge_1.csv: 成功加载 {len(docs)} 条记录")

    if docs:
        print("\n=== 第一条记录示例 ===")
        print(f"内容：{docs[0].page_content[:300]}...")
        print(f"元数据：{docs[0].metadata}")

    print("\n=== 测试多个 CSV 文件加载 ===")
    files = [
        "../data/knowledge_1.csv",
        "../data/knowledge_2.csv",
        "../data/knowledge_3.csv",
    ]
    all_docs = load_multiple_csv_files(files)
    print(f"总共加载 {len(all_docs)} 条记录")

    # 按来源统计
    from collections import Counter
    sources = Counter(doc.metadata.get('source', 'unknown') for doc in all_docs)
    print(f"\n按来源统计:")
    for source, count in sources.items():
        print(f"  {source}: {count} 条")
