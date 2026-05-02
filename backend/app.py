"""
Flask 应用 - 后端 API 服务
技术原理：提供 RESTful API 接口，连接前端与 RAG pipeline
面试考点：API 设计、CORS 处理、错误处理

架构说明：
- app.py: 中枢调用模块（伪 OpenCLaw），仅负责路由和模块调用
- llm_service.py: LLM 生成服务（路线详情、小红书概览）
- rag_pipeline.py: RAG 检索 Pipeline（旅游路线检索）
"""
import os
import sys
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 清除代理环境变量
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(proxy_var, None)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 添加 backend 目录到 Python 路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from utils import logger
from llm_service import get_llm_service, LLMService
from rag_pipeline import RAGPipeline

# 使用绝对路径指向 frontend 目录
frontend_dir = os.path.join(backend_dir, '..', 'frontend')
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
CORS(app)

# 初始化服务（单例模式）
rag_pipeline = RAGPipeline()
llm_service = get_llm_service()


# ==================== 工具函数 ====================

def extract_destination(product_name: str) -> str:
    """从产品名称中提取目的地"""
    if not product_name:
        return '目的地'

    destinations = [
        "桂林", "阳朔", "昆明", "大理", "丽江", "香格里拉", "西双版纳",
        "北京", "上海", "广州", "深圳", "成都", "重庆", "西安",
        "杭州", "南京", "苏州", "厦门", "三亚", "海口", "长沙",
        "张家界", "九寨沟", "黄山", "拉萨", "乌鲁木齐"
    ]

    for dest in destinations:
        if dest in product_name:
            return dest

    return product_name.split()[0] if product_name else '目的地'


def generate_template_route(destination: str, days: int, preferences: list = None) -> dict:
    """降级方案：返回通用模板（当 LLM 失败时使用）"""
    return {
        "overview": f"{destination}{days}天深度游，体验当地核心景点与特色美食。",
        "schedule": [
            {
                "day": i+1,
                "theme": f"第{i+1}天探索",
                "items": [
                    {"time": "09:00-11:30", "activity": f"{destination}核心景点 A", "type": "sightseeing", "transport": "打车/公交", "ticket_info": "需提前预约", "is_must": True},
                    {"time": "12:00-13:30", "activity": "当地特色餐厅", "type": "food", "avg_cost": "50-80 元"},
                    {"time": "14:00-17:00", "activity": f"{destination}核心景点 B", "type": "sightseeing", "is_must": False}
                ]
            } for i in range(days)
        ],
        "food_recommendations": [
            {"name": "当地老字号", "type": "特色菜", "avg_cost": "60 元", "signature_dish": "招牌菜"}
        ],
        "accommodation": [
            {"name": "市中心酒店", "location": "市区", "advantage": "交通便利，靠近景点"}
        ],
        "travel_tips": [
            "建议提前预订门票",
            "注意防晒和补水"
        ],
        "estimated_budget": {"total": "600-1000 元/人"}
    }


# ==================== API 路由 ====================

@app.route('/')
def serve_index():
    """提供前端首页"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "message": "AI 旅游路线规划师服务运行中"
    })


@app.route('/api/generate', methods=['POST'])
def generate_route():
    """
    生成旅游路线 API
    调用 RAG Pipeline 检索知识库中的路线
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体不能为空"}), 400

        destination = data.get('destination', '').strip()
        days = data.get('days', 5)
        preferences = data.get('preferences', [])

        if not destination:
            return jsonify({"error": "目的地不能为空"}), 400

        logger.info(f"收到路线生成请求：目的地={destination}, 天数={days}, 偏好={preferences}")

        # 调用 RAG Pipeline 检索
        routes = rag_pipeline.search_routes(destination=destination, days=days, preferences=preferences)
        logger.info(f"RAG Pipeline 检索返回 {len(routes)} 条路线")

        if not routes:
            logger.warning(f"未找到匹配的路线：{destination}")
            return jsonify({
                "routes": [],
                "message": f"暂未找到关于{destination}的路线，试试其他目的地吧"
            }), 200

        return jsonify({"routes": routes})

    except Exception as e:
        logger.error(f"生成路线失败：{e}")
        return jsonify({"error": f"服务器内部错误：{str(e)}"}), 500


@app.route('/api/route-detail', methods=['POST'])
def get_route_detail():
    """
    获取路线详情 API
    调用 LLM 服务生成路线详情和小红书风格概览
    """
    try:
        data = request.get_json()
        if not data or not data.get('route'):
            return jsonify({"error": "请求体缺少路线信息"}), 400

        route = data['route']
        preferences = data.get('preferences', [])

        logger.info(f"收到路线详情生成请求：{route.get('product_name', 'unknown')}")

        # 提取参数
        days = route.get('days', 3)
        product_name = route.get('product_name', '精选路线')
        route_path = route.get('route', '')
        destination = extract_destination(product_name)

        # 优先调用 LLM 服务生成小红书风格概览（核心展示内容）
        logger.info("正在生成小红书风格概览...")
        xiaohongshu_overview = llm_service.generate_xiaohongshu_overview(
            destination=destination,
            days=days,
            product_name=product_name,
            route_path=route_path,
            preferences=preferences
        )

        # 调用 LLM 服务生成路线详情
        logger.info("正在生成详细行程规划...")
        detail = llm_service.generate_route_detail(
            destination=destination,
            days=days,
            product_name=product_name,
            route_path=route_path,
            preferences=preferences
        )

        # 格式化概览并合并到详情
        if xiaohongshu_overview and detail:
            overview_text = LLMService.format_overview(xiaohongshu_overview)
            if overview_text:
                detail['overview'] = overview_text
                logger.info("小红书风格概览生成成功")
            else:
                logger.warning("小红书风格概览格式化失败，使用默认概览")
            detail['route_overview'] = xiaohongshu_overview
        elif detail:
            # 小红书概览生成失败，但 detail 成功，记录日志
            logger.warning("小红书风格概览生成失败（可能超时），使用默认概览")

        # LLM 失败时降级到模板
        if not detail:
            logger.warning(f"路线详情生成失败，降级到模板：{destination}")
            detail = generate_template_route(destination, days, preferences)
            # 如果有小红书概览，仍然使用
            if xiaohongshu_overview:
                overview_text = LLMService.format_overview(xiaohongshu_overview)
                if overview_text:
                    detail['overview'] = overview_text
                detail['route_overview'] = xiaohongshu_overview

        return jsonify(detail)

    except Exception as e:
        logger.error(f"生成路线详情失败：{e}")
        return jsonify({"error": f"服务器内部错误：{str(e)}"}), 500


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5001'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    logger.info(f"启动 Flask 服务：http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
