import asyncio
from langchain.tools import tool
from .rag_pipeline import run_rag_pipeline
from .utils import get_env
import requests

# 全局队列用于步骤推送（由 agent.py 设置）
_rag_step_queue = None
_rag_step_loop = None

def set_rag_step_queue(queue):
    global _rag_step_queue, _rag_step_loop
    _rag_step_queue = queue
    _rag_step_loop = asyncio.get_running_loop()

def emit_rag_step(icon, label, detail=""):
    if _rag_step_loop and _rag_step_queue:
        _rag_step_loop.call_soon_threadsafe(
            _rag_step_queue.put_nowait,
            {"type": "rag_step", "step": {"icon": icon, "label": label, "detail": detail}}
        )

@tool
def search_knowledge_base(query: str) -> str:
    """当用户询问关于已上传文档的问题时，使用此工具检索知识库。"""
    emit_rag_step("🔍", "开始检索知识库...")
    result = run_rag_pipeline(query)
    context = result.get("context", "")
    # 将 RAG trace 存储到全局，供后续保存
    global _last_rag_trace
    _last_rag_trace = result.get("rag_trace")
    return context if context else "未找到相关信息。"

@tool
def get_current_weather(city: str) -> str:
    """获取指定城市的当前天气。"""
    api_key = get_env("AMAP_API_KEY")
    if not api_key:
        return "天气服务未配置"
    url = f"https://restapi.amap.com/v3/weather/weatherInfo?city={city}&key={api_key}&output=JSON"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data['status'] == '1':
            weather = data['lives'][0]
            return f"{city}天气：{weather['weather']}，温度{weather['temperature']}℃"
        else:
            return "查询失败"
    except:
        return "天气服务异常"

def get_last_rag_context(clear=False):
    global _last_rag_trace
    if clear:
        trace = _last_rag_trace
        _last_rag_trace = None
        return {"rag_trace": trace}
    return {"rag_trace": _last_rag_trace}

def reset_tool_call_guards():
    # 用于重置工具调用计数器（如有）
    pass