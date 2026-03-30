"""
后端模块测试脚本
技术原理：验证所有模块导入和初始化是否正常
面试考点：Python 模块系统、依赖注入
"""

print("=" * 60)
print("开始测试后端模块...")
print("=" * 60)

# 测试 1: 基础工具模块
print("\n[1/10] 测试 utils 模块...")
try:
    from backend.utils import get_env, logger
    print("✅ utils 模块导入成功")
    logger.info("日志系统正常")
except Exception as e:
    print(f"❌ utils 模块失败：{e}")

# 测试 2: Schema 定义
print("\n[2/10] 测试 schema 模块...")
try:
    from backend.schema import ChatRequest, TravelPreferences
    print("✅ schema 模块导入成功")
    
    # 测试 Pydantic 验证
    test_prefs = TravelPreferences(
        duration_days=5,
        trip_type="family",
        style="relaxed",
        origin_city="上海",
        destination="北京",
        budget_level="medium",
        interests=["美食", "拍照"]
    )
    print(f"   ✓ Pydantic 验证正常：{test_prefs.destination}")
except Exception as e:
    print(f"❌ schema 模块失败：{e}")

# 测试 3: CSV 加载器
print("\n[3/10] 测试 csv_loader 模块...")
try:
    from backend.csv_loader import load_csv_knowledge_base
    docs = load_csv_knowledge_base("data/knowledge_base.csv")
    print(f"✅ CSV 加载成功：{len(docs)} 个景点")
    if docs:
        print(f"   ✓ 示例：{docs[0].metadata['attraction_name']}")
except Exception as e:
    print(f"❌ csv_loader 模块失败：{e}")

# 测试 4: 嵌入服务
print("\n[4/10] 测试 embedding 模块...")
try:
    from backend.embedding import EmbeddingService
    emb_service = EmbeddingService()
    print(f"✅ EmbeddingService 初始化成功")
    print(f"   ✓ 模型：{emb_service.model}")
except Exception as e:
    print(f"❌ embedding 模块失败：{e}")

# 测试 5: Chroma 客户端
print("\n[5/10] 测试 chroma_client 模块...")
try:
    from backend.chroma_client import ChromaClient
    client = ChromaClient()
    print(f"✅ ChromaClient 初始化成功")
    print(f"   ✓ 持久化目录：{client.persist_dir}")
except Exception as e:
    print(f"❌ chroma_client 模块失败：{e}")

# 测试 6: 父块存储
print("\n[6/10] 测试 parent_chunk_store 模块...")
try:
    from backend.parent_chunk_store import ParentChunkStore
    store = ParentChunkStore()
    print(f"✅ ParentChunkStore 初始化成功")
    print(f"   ✓ 存储文件：{store.storage_file}")
except Exception as e:
    print(f"❌ parent_chunk_store 模块失败：{e}")

# 测试 7: RAG 工具
print("\n[7/10] 测试 rag_utils 模块...")
try:
    from backend.rag_utils import (
        embedding_service, 
        chroma_client, 
        parent_store,
        initialize_csv_knowledge_base
    )
    print(f"✅ rag_utils 模块导入成功")
    print(f"   ✓ 嵌入服务：{type(embedding_service).__name__}")
    print(f"   ✓ Chroma 客户端：{type(chroma_client).__name__}")
except Exception as e:
    print(f"❌ rag_utils 模块失败：{e}")

# 测试 8: 查询构建函数
print("\n[8/10] 测试 app 模块的查询构建...")
try:
    from backend.app import build_query_from_preferences, build_metadata_filters
    from backend.schema import TravelPreferences
    
    prefs = TravelPreferences(
        duration_days=5,
        trip_type="family",
        style="relaxed",
        origin_city="上海",
        destination="北京"
    )
    
    query = build_query_from_preferences(prefs)
    filters = build_metadata_filters(prefs)
    
    print(f"✅ 查询构建成功")
    print(f"   ✓ 查询语句：{query[:50]}...")
    print(f"   ✓ 过滤器：{filters}")
except Exception as e:
    print(f"❌ app 模块查询构建失败：{e}")

# 测试 9: Tools 模块
print("\n[9/10] 测试 tools 模块...")
try:
    from backend.tools import search_knowledge_base, get_current_weather
    print(f"✅ tools 模块导入成功")
    print(f"   ✓ 可用工具：search_knowledge_base, get_current_weather")
except Exception as e:
    print(f"❌ tools 模块失败：{e}")

# 测试 10: Agent 模块
print("\n[10/10] 测试 agent 模块...")
try:
    from backend.agent import agent, model
    print(f"✅ agent 模块导入成功")
    print(f"   ✓ Agent 类型：{type(agent).__name__}")
    print(f"   ✓ 模型：{model}")
except Exception as e:
    print(f"❌ agent 模块失败：{e}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)

# 总结
print("""
✅ 如果所有测试通过，说明后端模块配置正确！

下一步：
1. 确保 .env 文件中的 API Key 已配置
2. 启动 Flask 应用：python backend/app.py
3. 访问前端页面测试表单提交

常见错误排查：
- ModuleNotFoundError: 检查是否安装了 requirements.txt
- API Key 错误：检查 .env 配置
- Chroma 错误：删除 ./data/chroma 目录重新启动
""")
