from typing import List, Dict
import dashscope
# 你的代码 → dashscope 库 (HTTP 客户端) → 阿里云百炼 API → 向量模型 → 返回结果
from dashscope import TextEmbedding
from .utils import get_env, logger

class EmbeddingService:
    def __init__(self):
        self.api_key = get_env("DASHSCOPE_API_KEY")
        self.model = get_env("EMBED_MODEL", "text-embedding-v2")
        dashscope.api_key = self.api_key

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取文本的稠密向量"""
        results = []
        for text in texts:
            resp = TextEmbedding.call(
                model=self.model,
                input=text
            )
            if resp.status_code == 200:
                embedding = resp.output['embeddings'][0]['embedding']
                results.append(embedding)
            else:
                logger.error(f"Embedding failed: {resp.message}")
                # 返回零向量作为降级
                results.append([0.0] * 1024)
        return results

    def get_sparse_embedding(self, text: str) -> Dict[int, float]:
        """生成 BM25 稀疏向量（需预建词表）"""
        # 简化实现：使用 jieba 分词，这里仅示意
        import jieba
        from collections import Counter
        tokens = jieba.lcut(text)
        tf = Counter(tokens)
        # 实际应使用全局 idf，这里仅返回词频
        sparse = {hash(token): count for token, count in tf.items()}
        return sparse