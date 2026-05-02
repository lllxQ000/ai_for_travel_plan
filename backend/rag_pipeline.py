"""
RAG 检索 pipeline
技术原理：结合向量检索和元数据过滤，从知识库中检索相关旅游路线
面试考点：检索策略、排序算法、混合检索
"""
import os
from typing import List, Dict, Optional
from chroma_client import ChromaClient
from embedding import EmbeddingService
from utils import logger


class RAGPipeline:
    """
    RAG 检索 pipeline
    负责接收用户查询，检索知识库中的旅游路线
    """

    def __init__(self):
        self.chroma_client = ChromaClient()
        self.embedding_service = EmbeddingService()

    def search_routes(
        self,
        destination: str,
        days: int = 5,
        preferences: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        根据用户查询检索旅游路线

        Args:
            destination: 目的地
            days: 游玩天数
            preferences: 偏好标签列表

        Returns:
            路线列表，每个路线包含 product_name, route, sales, reviews
        """
        logger.info(f"开始检索：目的地={destination}, 天数={days}, 偏好={preferences}")

        # 1. 构建查询文本
        query_text = self._build_query_text(destination, preferences)

        # 2. 获取查询向量
        try:
            query_embedding = self.embedding_service.get_embedding(query_text)
        except Exception as e:
            logger.error(f"向量化失败：{e}")
            query_embedding = [0.0] * 768  # 降级为零向量

        # 3. 查询知识库
        results = self._query_knowledge_base(query_embedding, destination)

        # 4. 处理和排序结果
        routes = self._process_results(results, destination, days, preferences)

        logger.info(f"检索完成，返回 {len(routes)} 条路线")
        return routes

    def _build_query_text(self, destination: str, preferences: Optional[List[str]]) -> str:
        """
        构建查询文本（用于向量化）

        将用户输入转换为自然语言描述，提升向量检索效果
        """
        parts = [f"我想去{destination}旅游"]

        if preferences:
            pref_text = "、".join(preferences)
            parts.append(f"喜欢{pref_text}")

        return "；".join(parts)

    def _query_knowledge_base(
        self,
        query_embedding: List[float],
        destination: str,
        n_results: int = 10
    ) -> Dict:
        """
        查询 Chroma 知识库

        策略：跨所有知识库集合查询，获取最相关的路线
        """
        try:
            # 跨所有知识库查询
            results = self.chroma_client.query_knowledge_across_all(
                query_embedding=query_embedding,
                n_results=n_results
            )
            logger.info(f"知识库查询结果：{len(results.get('ids', []))} 条")
            return results
        except Exception as e:
            logger.error(f"知识库查询失败：{e}")
            return {'ids': [], 'documents': [], 'metadatas': [], 'distances': []}

    def _process_results(
        self,
        results: Dict,
        destination: str,
        days: int,
        preferences: Optional[List[str]]
    ) -> List[Dict]:
        """
        处理检索结果，转换为前端需要的格式

        1. 解析元数据
        2. 过滤目的地匹配的路线
        3. 过滤天数匹配的路线
        4. 按相关性和销量排序
        """
        routes = []

        ids = results.get('ids', [])
        documents = results.get('documents', [])
        metadatas = results.get('metadatas', [])
        distances = results.get('distances', [])

        if not ids:
            return []

        for i in range(len(ids)):
            metadata = metadatas[i] if i < len(metadatas) else {}
            document = documents[i] if i < len(documents) else ""
            distance = distances[i] if i < len(distances) else None

            # 提取元数据
            route_data = {
                'product_name': metadata.get('product_name', ''),
                'route': metadata.get('route', ''),
                'sales': metadata.get('sales', 0),
                'reviews': metadata.get('reviews', 0),
                'distance': distance,
                'days': metadata.get('days'),
            }

            # 目的地匹配检查：必须包含目的地关键词
            if destination and route_data['product_name']:
                # 检查产品名称或轨迹中是否包含目的地
                if destination not in route_data['product_name'] and \
                   destination not in route_data['route']:
                    # 不包含目的地，过滤掉
                    continue

            # 天数匹配检查：只返回与用户选择天数匹配的路线
            if days and route_data['days']:
                if route_data['days'] != days:
                    # 天数不匹配，过滤掉
                    continue

            routes.append(route_data)

        # 排序：优先按目的地匹配度，再按距离（相关性），最后按销量
        def sort_key(x):
            # 目的地匹配分数：产品名称中包含目的地得最高分
            name_match = 1 if destination in x.get('product_name', '') else 0
            route_match = 1 if destination in x.get('route', '') else 0
            return (
                -(name_match + route_match),  # 匹配度越高越优先（负数排序）
                x.get('distance') or float('inf'),  # 距离越小越相关
                -(x.get('sales') or 0)  # 销量越高越优先
            )

        routes.sort(key=sort_key)

        return routes


# 便捷函数
def search_routes(
    destination: str,
    days: int = 5,
    preferences: Optional[List[str]] = None
) -> List[Dict]:
    """便捷函数：检索旅游路线"""
    pipeline = RAGPipeline()
    return pipeline.search_routes(destination, days, preferences)


if __name__ == "__main__":
    # 测试代码
    pipeline = RAGPipeline()

    print("=== 测试 RAG 检索 ===")

    test_cases = [
        {"destination": "桂林", "days": 5, "preferences": ["山水"]},
        {"destination": "阳朔", "days": 3, "preferences": ["美食", "徒步"]},
        {"destination": "云南", "days": 7, "preferences": ["文化", "古镇"]},
    ]

    for test in test_cases:
        print(f"\n查询：{test}")
        routes = pipeline.search_routes(**test)
        print(f"找到 {len(routes)} 条路线")

        for i, route in enumerate(routes[:3]):  # 只显示前 3 条
            print(f"  {i + 1}. {route['product_name']} (销量：{route['sales']})")
