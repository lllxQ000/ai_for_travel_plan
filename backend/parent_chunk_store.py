"""
父块存储模块
技术原理：存储和管理文档的层级分块（L1/L2）
面试考点：父子块索引策略、RAG 中的 Auto-merging
"""
import json
import os
from typing import List, Dict, Optional
from .utils import get_env, logger


class ParentChunkStore:
    """
    父块存储器
    
    用途：
    1. 存储 L1/L2 层级的文档块（不向量化）
    2. 在检索时用于 Auto-merging（将多个 L3 子块合并为 L2/L1 父块）
    3. 提升上下文完整性
    
    面试考点：为什么要分层存储？
    答：
    - L3（小 chunk）：语义精确，适合向量检索
    - L1/L2（大 chunk）：上下文完整，适合生成答案
    - 检索 L3，返回 L1：兼顾精度和完整性
    """
    
    def __init__(self, storage_file: str = None):
        """
        初始化父块存储
        
        参数：
        - storage_file: JSON 文件路径，默认从环境变量读取
        """
        if storage_file is None:
            storage_file = get_env("PARENT_CHUNK_FILE", "./data/parent_chunks.json")
        
        self.storage_file = storage_file
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """确保存储文件存在"""
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False)
    
    def add_parent_chunk(self, chunk_id: str, text: str, metadata: Dict):
        """
        添加父块到存储
        
        参数：
        - chunk_id: 唯一标识
        - text: 块文本内容
        - metadata: 元数据（level, parent_id 等）
        
        技术原理：JSON 键值对存储，chunk_id 作为 key
        """
        data = self._load_data()
        
        data[chunk_id] = {
            "chunk_id": chunk_id,
            "text": text,
            "metadata": metadata
        }
        
        self._save_data(data)
        logger.debug(f"添加父块：{chunk_id}")
    
    def get_parent_chunk(self, chunk_id: str) -> Optional[Dict]:
        """
        根据 ID 获取父块
        
        返回：
        - 成功：{"chunk_id": ..., "text": ..., "metadata": ...}
        - 失败：None
        """
        data = self._load_data()
        return data.get(chunk_id)
    
    def get_documents_by_ids(self, chunk_ids: List[str]) -> List[Dict]:
        """
        批量获取父块
        
        参数：
        - chunk_ids: ID 列表
        
        返回：
        - 文档列表（可能少于请求数量，如果某些 ID 不存在）
        
        面试考点：为什么不用数据库？
        答：
        - 父块数量少（<1000），JSON 足够
        - 简单快速，无需额外依赖
        - 便于调试和版本控制
        """
        data = self._load_data()
        results = []
        
        for chunk_id in chunk_ids:
            if chunk_id in data:
                results.append(data[chunk_id])
        
        return results
    
    def _load_data(self) -> Dict:
        """从 JSON 文件加载数据"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载父块数据失败：{e}")
            return {}
    
    def _save_data(self, data: Dict):
        """保存数据到 JSON 文件"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存父块数据失败：{e}")
            raise


# 便捷函数
def create_parent_chunk_store() -> ParentChunkStore:
    """创建父块存储实例"""
    return ParentChunkStore()
