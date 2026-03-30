import uuid
from datetime import datetime
from .chroma_client import ChromaClient

class ConversationStorage:
    def __init__(self):
        self.client = ChromaClient()

    def save_message(self, session_id, role, content, extra=None):
        msg_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        self.client.add_message(msg_id, session_id, role, content, timestamp, extra)
        return msg_id

    def load_messages(self, session_id, limit=50):
        result = self.client.get_messages(session_id, limit)
        messages = []
        if result['documents']:
            for i, doc in enumerate(result['documents']):
                metadata = result['metadatas'][i]
                messages.append({
                    "role": metadata['role'],
                    "content": doc,
                    "timestamp": metadata['timestamp'],
                    "msg_id": result['ids'][i],
                    "extra": {k:v for k,v in metadata.items() if k not in ['role','timestamp','session_id']}
                })
        # 按时间排序
        messages.sort(key=lambda x: x['timestamp'])
        return messages

    def create_session(self, user_id, title):
        session_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        self.client.add_session(session_id, user_id, title, created_at)
        return session_id

    def list_sessions(self, user_id):
        result = self.client.get_sessions(user_id)
        sessions = []
        if result['metadatas']:
            for meta in result['metadatas']:
                sessions.append({
                    "session_id": meta['session_id'],
                    "title": meta['title'],
                    "created_at": meta['created_at']
                })
        return sessions

    def delete_session(self, session_id):
        # Chroma 不支持直接删除，需实现删除逻辑（略）
        pass