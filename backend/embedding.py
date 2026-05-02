"""
向量化服务
技术原理：使用嵌入模型将文本转换为向量表示
面试考点：嵌入模型选择、API 调用、批量处理
"""
import os
import requests
from typing import List
from utils import get_env, logger

# 清除代理环境变量，避免 Dashscope API 通过本地代理连接
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(proxy_var, None)


class EmbeddingService:
    """
    向量化服务 - 调用本地或远程嵌入模型 API
    支持多种嵌入模型后端

    支持的嵌入服务：
    1. Dashscope（阿里云百炼）- 默认
    2. Ollama（本地）
    3. sentence-transformers（本地降级方案）
    """

    def __init__(self):
        # 优先使用 Dashscope
        self.dashscope_api_key = get_env("DASHSCOPE_API_KEY")
        self.dashscope_model = get_env("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v2")

        # Ollama 配置
        self.ollama_api_url = get_env("EMBEDDING_API_URL", "http://localhost:11434/api/embeddings")
        self.ollama_model = get_env("EMBEDDING_MODEL", "mxbai-embed-large")
        self.timeout = int(get_env("EMBEDDING_TIMEOUT", "30"))

        # 本地模型配置
        self._use_local_model = False
        self._local_model = None

        # 初始化嵌入服务（优先级：Dashscope > Ollama > sentence-transformers）
        if self.dashscope_api_key:
            logger.info("使用 Dashscope 嵌入服务")
            self._service_type = "dashscope"
        elif self._check_ollama_available():
            logger.info("使用 Ollama 嵌入服务")
            self._service_type = "ollama"
        else:
            logger.warning("Ollama 不可用，切换到 sentence-transformers 本地模型")
            self._use_local_model = True
            self._service_type = "local"
            self._init_local_model()

    def _check_ollama_available(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            response = requests.get("http://localhost:11434/api/version", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _init_local_model(self):
        """初始化本地 sentence-transformers 模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("本地嵌入模型加载成功")
        except ImportError:
            logger.error("sentence-transformers 未安装，请运行：pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"本地模型加载失败：{e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        """
        获取单条文本的向量

        Args:
            text: 输入文本

        Returns:
            向量表示（浮点数列表）
        """
        if self._service_type == "dashscope":
            return self._get_dashscope_embedding(text)
        elif self._service_type == "ollama":
            return self._get_ollama_embedding(text)
        else:
            return self._get_local_embedding(text)

    def _get_dashscope_embedding(self, text: str) -> List[float]:
        """调用 Dashscope API 获取向量 - 使用 requests 直接调用，绕过 SDK 代理问题"""
        try:
            # 使用 requests 直接调用 Dashscope API，不使用 dashscope SDK
            # 这样可以更好地控制代理设置
            url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {self.dashscope_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.dashscope_model,
                "input": [text]
            }

            # 使用 session 并明确设置不通过代理
            session = requests.Session()
            session.trust_env = False  # 不使用环境变量中的代理
            session.proxies = {
                'http': '',
                'https': ''
            }

            response = session.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            return result['data'][0]['embedding']

        except Exception as e:
            logger.error(f"Dashscope 向量化失败：{e}")
            return [0.0] * 768

    def _get_ollama_embedding(self, text: str) -> List[float]:
        """调用 Ollama API 获取向量"""
        response = requests.post(
            self.ollama_api_url,
            json={"model": self.ollama_model, "prompt": text},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json().get("embedding", [])

    def _get_local_embedding(self, text: str) -> List[float]:
        """使用本地 sentence-transformers 模型获取向量"""
        embedding = self._local_model.encode(text).tolist()
        return embedding

    def get_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        批量获取向量

        Args:
            texts: 文本列表
            batch_size: 批次大小

        Returns:
            向量列表
        """
        if self._service_type == "dashscope":
            return self._get_dashscope_embeddings(texts, batch_size)
        elif self._service_type == "ollama":
            return self._get_ollama_embeddings(texts, batch_size)
        else:
            return self._get_local_embeddings(texts, batch_size)

    def _get_dashscope_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """批量调用 Dashscope API 获取向量"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = []
            for text in batch_texts:
                embedding = self._get_dashscope_embedding(text)
                batch_embeddings.append(embedding)
            all_embeddings.extend(batch_embeddings)
            logger.info(f"完成 Dashscope 批次 {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}")
        return all_embeddings

    def _get_ollama_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """批量调用 Ollama API 获取向量"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = []
            for text in batch_texts:
                try:
                    embedding = self._get_ollama_embedding(text)
                    batch_embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"向量化失败：{text[:50]}... 错误：{e}")
                    batch_embeddings.append([0.0] * 768)
            all_embeddings.extend(batch_embeddings)
            logger.info(f"完成 Ollama 批次 {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size}")
        return all_embeddings

    def _get_local_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """使用本地 sentence-transformers 模型批量获取向量"""
        embeddings = self._local_model.encode(texts, show_progress_bar=True)
        return embeddings.tolist()


# 便捷函数
def get_embeddings(texts: List[str]) -> List[List[float]]:
    """便捷函数：获取文本列表的向量"""
    service = EmbeddingService()
    return service.get_embeddings(texts)


if __name__ == "__main__":
    # 测试代码
    service = EmbeddingService()

    test_texts = [
        "桂林山水甲天下",
        "阳朔西街美食",
        "龙脊梯田徒步"
    ]

    print("=== 测试向量化服务 ===")
    embeddings = service.get_embeddings(test_texts)

    for i, (text, emb) in enumerate(zip(test_texts, embeddings)):
        print(f"\n{i + 1}. {text}")
        print(f"   向量维度：{len(emb)}")
        print(f"  前 5 个值：{emb[:5]}")
