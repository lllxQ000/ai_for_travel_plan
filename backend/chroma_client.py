import chromadb
from chromadb.config import Settings
from .utils import get_env, logger

class ChromaClient:
    def __init__(self):
        self.persist_dir = get_env("CHROMA_PERSIST_DIR", "./data/chroma")
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self._init_collections()

    def _init_collections(self):
        # 文档分块集合（含向量）
        self.chunks_collection = self.client.get_or_create_collection(
            name="doc_chunks",
            metadata={"hnsw:space": "cosine"}
        )
        # 父块集合（无向量）
        self.parent_chunks_collection = self.client.get_or_create_collection(
            name="parent_chunks",
            metadata={"hnsw:space": "cosine"}
        )
        # 会话集合
        self.sessions_collection = self.client.get_or_create_collection(
            name="sessions"
        )
        # 消息集合
        self.messages_collection = self.client.get_or_create_collection(
            name="messages"
        )
        # 用户集合
        self.users_collection = self.client.get_or_create_collection(
            name="users"
        )

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

    def add_parent_chunk(self, chunk_id, text, metadata):
        """添加父块（无向量）"""
        self.parent_chunks_collection.add(
            ids=[chunk_id],
            documents=[text],
            metadatas=[metadata]
        )

    def get_parent_chunk(self, chunk_id):
        """获取父块"""
        result = self.parent_chunks_collection.get(ids=[chunk_id])
        if result['documents']:
            return {
                'chunk_id': chunk_id,
                'text': result['documents'][0],
                'metadata': result['metadatas'][0]
            }
        return None

    # 会话和消息操作类似
    def add_session(self, session_id, user_id, title, created_at):
        self.sessions_collection.add(
            ids=[session_id],
            metadatas=[{"user_id": user_id, "title": title, "created_at": created_at}]
        )

    def get_sessions(self, user_id):
        return self.sessions_collection.get(where={"user_id": user_id})

    def add_message(self, msg_id, session_id, role, content, timestamp, extra=None):
        metadata = {
            "session_id": session_id,
            "role": role,
            "timestamp": timestamp
        }
        if extra:
            metadata.update(extra)
        self.messages_collection.add(
            ids=[msg_id],
            documents=[content],
            metadatas=[metadata]
        )

    def get_messages(self, session_id, limit=50):
        return self.messages_collection.get(
            where={"session_id": session_id},
            limit=limit
        )