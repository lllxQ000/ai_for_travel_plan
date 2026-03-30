import os
from flask import Flask, request, Response, jsonify, send_from_directory, stream_with_context
from flask_cors import CORS
import asyncio
from pydantic import ValidationError
from agent import chat_with_agent_stream
from document_loader import DocumentLoader
from rag_utils import embedding_service, chroma_client, parent_store, initialize_csv_knowledge_base
from conversation_storage import ConversationStorage

storage = ConversationStorage()
from schema import ChatRequest, DocumentUploadResponse
from utils import logger


app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# 初始化文档处理器
doc_loader = DocumentLoader()

# 初始化 CSV 知识库（应用启动时一次性操作）
with app.app_context():
    try:
        initialize_csv_knowledge_base()
        logger.info("CSV 知识库初始化成功")
    except Exception as e:
        logger.error(f"CSV 知识库初始化失败：{e}")

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    """
    接收前端表单 JSON 并流式返回 AI 生成的行程
    
    请求体示例：
    {
        "user_id": "user_123",
        "preferences": {
            "duration_days": 5,
            "trip_type": "family",
            "style": "relaxed",
            "origin_city": "上海",
            "destination": "北京",
            "interests": ["美食", "拍照"]
        },
        "message": "希望安排适合老人的行程"
    }
    
    响应格式：SSE (text/event-stream)
    data: {"text": "第一天：抵达北京...\n"}
    
    data: {"text": "第二天：参观故宫...\n"}
    
    data: [DONE]
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "需要 JSON 格式的请求体"}), 400
    
    try:
        # Pydantic 自动验证数据结构
        req = ChatRequest(**data)
        
        # 从表单构建查询（关键步骤！）
        query = build_query_from_preferences(req.preferences)
        
        # 合并用户补充说明
        full_query = f"{query}\n\n用户补充要求：{req.message}" if req.message else query
        
        async def generate():
            async for chunk in chat_with_agent_stream(
                full_query,
                user_id=req.user_id,
                session_id=req.session_id
            ):
                yield chunk
        
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
        
    except ValidationError as e:
        # 返回详细验证错误（前端可定位到具体字段）
        return jsonify({
            "error": "数据验证失败",
            "details": e.errors()
        }), 422


def build_query_from_preferences(prefs):
    """
    将结构化表单转为向量检索查询
    技术原理：Query Rewriting 提升检索效果
    面试考点：如何将结构化数据映射到非结构化检索
    """
    style_map = {
        "relaxed": "轻松休闲",
        "intensive": "紧凑高效",
        "cultural": "文化深度",
        "adventure": "冒险探索"
    }
    
    interests_str = ", ".join(prefs.interests) if prefs.interests else "无特殊要求"
    
    query = f"""为{prefs.trip_type}游客规划{prefs.destination}{prefs.duration_days}天的行程
风格：{style_map.get(prefs.style, '休闲')}
预算：{prefs.budget_level}
兴趣点：{interests_str}
出发地：{prefs.origin_city}""".strip()
    
    return query


def build_metadata_filters(prefs):
    """
    从表单构建元数据过滤器
    用途：精确过滤目的地、适合人群等
    
    面试考点：为什么需要元数据过滤？
    答：避免向量检索召回不相关的结果（如用户要去北京却检索到上海）
    """
    filters = {}
    
    # 1. 目的地过滤（必须）
    filters["city"] = prefs.destination
    
    # 2. 根据出行类型过滤适合人群
    trip_type_map = {
        "family": "家庭",
        "couple": "情侣",
        "friends": "朋友",
        "personal": None  # 个人游不限
    }
    suitable = trip_type_map.get(prefs.trip_type)
    if suitable:
        filters["suitable_for"] = {"$in": [suitable, "所有人"]}
    
    # 3. 根据预算过滤价格范围
    price_limits = {
        "budget": 100,
        "medium": 300,
        "luxury": 999999
    }
    max_price = price_limits.get(prefs.budget_level, 300)
    filters["price"] = {"$lte": max_price}
    
    logger.info(f"构建的元数据过滤器：{filters}")
    return filters

@app.route('/documents/upload', methods=['POST'])
def upload_document():
    file = request.files['file']
    if not file:
        return jsonify({"error": "No file provided"}), 400
    filename = file.filename
    filepath = os.path.join('./data/uploads', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)

    try:
        result = doc_loader.process_document(filepath)
        leaf_chunks = result['leaf_chunks']
        parent_chunks = result['parent_chunks']

        # 向量化叶子块
        texts = [chunk['text'] for chunk in leaf_chunks]
        embeddings = embedding_service.get_embeddings(texts)

        # 存入 Chroma
        ids = [chunk['chunk_id'] for chunk in leaf_chunks]
        metadatas = [{"level": chunk['level'], "parent_id": chunk['parent_id']} for chunk in leaf_chunks]
        chroma_client.add_chunks(ids, embeddings, metadatas, texts)

        # 存入父块
        for parent in parent_chunks:
            parent_store.add_parent_chunk(
                parent['chunk_id'],
                parent['text'],
                {"level": parent['level'], "parent_id": parent['parent_id']}
            )

        return jsonify(DocumentUploadResponse(
            doc_id=os.path.basename(filepath),
            filename=filename,
            chunks_processed=len(leaf_chunks)
        ).dict())
    except Exception as e:
        logger.exception("Document upload failed")
        return jsonify({"error": str(e)}), 500

@app.route('/sessions/<user_id>', methods=['GET'])
def list_sessions(user_id):
    sessions = storage.list_sessions(user_id)
    return jsonify(sessions)

@app.route('/sessions/<user_id>/<session_id>', methods=['GET'])
def get_session_messages(user_id, session_id):
    messages = storage.load_messages(session_id)
    return jsonify(messages)

@app.route('/sessions/<user_id>/<session_id>', methods=['DELETE'])
def delete_session(user_id, session_id):
    storage.delete_session(session_id)
    return jsonify({"status": "deleted"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)