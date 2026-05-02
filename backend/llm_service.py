"""
LLM 服务模块
负责所有 LLM 相关的生成任务：
- 路线详情生成
- 小红书风格概览生成
- 营销文案生成
"""
import os
import json
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
from utils import logger

# 加载 .env 文件
load_dotenv()

# 清除代理环境变量
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(proxy_var, None)

# LLM 配置
LLM_API_KEY = os.getenv("ARK_API_KEY")
LLM_MODEL = os.getenv("MODEL", "qwen-plus")
LLM_BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))

if not LLM_API_KEY:
    raise ValueError("请在 .env 文件中配置 ARK_API_KEY")


class LLMService:
    """LLM 服务类，提供统一的 LLM 调用接口"""

    def __init__(self):
        self.api_key = LLM_API_KEY
        self.model = LLM_MODEL
        self.base_url = LLM_BASE_URL
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建绕过代理的 session"""
        session = requests.Session()
        session.trust_env = False
        return session

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.7,
                  max_tokens: int = None, enable_search: bool = True, timeout: int = 60) -> Optional[Dict]:
        """通用 LLM 调用方法"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens or LLM_MAX_TOKENS,
                "extra_body": {"enable_search": enable_search}
            }

            response = self.session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                content = content.replace('```json', '').replace('```', '').strip()
                return json.loads(content)
            else:
                logger.error(f"LLM 请求失败：{response.status_code}")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}")
            return None
        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return None

    def generate_route_detail(self, destination: str, days: int, product_name: str,
                              route_path: str, preferences: Optional[List[str]] = None) -> Optional[Dict]:
        """
        生成详细行程规划
        基于联网搜索推荐沿途地点的热门美食和住宿
        """
        pref_text = ', '.join(preferences) if preferences else '无特定偏好'

        prompt = f"""你是一位专业的旅游规划师。请基于以下真实路线数据，为游客生成一份详细的{days}天行程规划。

【路线信息】
- 产品名称：{product_name}
- 目的地：{destination}
- 行程路线：{route_path}
- 游玩天数：{days}天
- 用户偏好：{pref_text}

【重要要求】
1. 时间颗粒度：细化到分钟（如 09:00-11:00）
2. 每个景点包含：交通方式、门票信息、游玩贴士
3. 用★标注必体验，用？标注避坑指南
4. 【美食推荐】必须基于行程路线中提到的具体地点/区域，搜索当地热门餐厅和特色小吃，不要推荐全国连锁品牌
5. 【住宿推荐】必须基于行程路线中提到的具体住宿区域（如"西街附近"、"两江四湖周边"等），搜索真实存在的酒店/民宿

【JSON 格式】请只返回纯 JSON，不要其他文字：
{{
    "overview": "50 字内亮点介绍",
    "schedule": [
        {{"day": 1, "theme": "主题", "items": [
            {{"time": "09:00-11:00", "activity": "景点名", "type": "sightseeing", "transport": "交通", "ticket_info": "门票", "tips": "贴士", "is_must": true}}
        ]}},
        {{"day": 2, "theme": "主题", "items": []}}
    ],
    "food_recommendations": [{{"name": "真实餐厅名", "type": "美食类型", "avg_cost": "人均价格", "signature_dish": "招牌菜", "location": "具体位置"}}],
    "accommodation": [{{"name": "真实酒店/民宿名", "location": "具体区域", "advantage": "优势特色"}}],
    "travel_tips": ["提示 1", "提示 2"],
    "estimated_budget": {{"total": "总预算"}}
}}"""

        return self._call_llm("你是旅游规划师，只返回纯 JSON，不要 markdown 格式。", prompt, 0.7, 2000, True, 90)

    def generate_xiaohongshu_overview(self, destination: str, days: int, product_name: str,
                                       route_path: str, preferences: Optional[List[str]] = None) -> Optional[Dict]:
        """
        生成小红书爆款风格的路线概览笔记
        基于 RAG 检索的轨迹、销量、评论数以及用户偏好，创作高互动率的种草笔记
        """
        pref_text = ', '.join(preferences) if preferences else '无特定偏好'

        prompt = f"""你是一位专业的小红书旅游内容创作专家，深度了解平台算法机制和用户偏好，擅长创作高互动率的爆款笔记。

请基于以下【主题信息】，创作一篇小红书爆款路线推荐笔记：

【主题信息】
- 路线名称：{product_name}
- 目的地：{destination}
- 行程路线：{route_path}
- 游玩天数：{days}天
- 用户偏好：{pref_text}

【输出要求】
1. **爆款标题**：3-5 个备选，包含数字、对比、疑问或情感词汇
2. **开头抓眼**：前 3 行必须足够吸引，包含悬念或强烈情感
3. **核心内容**：结构化呈现路线亮点，包含实用干货
4. **互动引导**：巧妙设置互动点，促进点赞评论收藏
5. **热门标签**：10-15 个精准标签

【写作要求】
- 语言风格：亲切自然，口语化表达，多用感叹号和 emoji
- 内容价值：必须包含实用干货或独特见解
- 情感共鸣：触发用户的痛点、爽点或痒点
- 结合联网搜索：获取该目的地最新热门玩法、当季特色、网红打卡点

【JSON 格式】请只返回纯 JSON，不要其他文字，不要 markdown 格式：
{{
    "titles": ["标题 1", "标题 2", "标题 3"],
    "opening": "开头抓眼文案（前 3 行，约 50-100 字）",
    "highlights": ["亮点 1", "亮点 2", "亮点 3", "亮点 4"],
    "tips": ["实用贴士 1", "实用贴士 2"],
    "call_to_action": "互动引导文案",
    "hashtags": ["#标签 1", "#标签 2", "..."]
}}"""

        return self._call_llm("你是小红书旅游内容创作专家，只返回纯 JSON，不要 markdown 格式。", prompt, 0.8, 600, True, 90)

    @staticmethod
    def format_overview(overview: Dict) -> str:
        """
        将小红书风格概览格式化为前端显示文本
        输出格式适合直接在前端"路线概览"窗口中显示
        """
        if not overview:
            return None

        try:
            parts = []

            # 标题（取第一个）
            titles = overview.get('titles', [])
            if titles:
                parts.append(f"🔥 {titles[0]}")
                parts.append("")

            # 开头抓眼
            opening = overview.get('opening', '')
            if opening:
                parts.append(opening)
                parts.append("")

            # 路线亮点
            highlights = overview.get('highlights', [])
            if highlights:
                parts.append("✨ 路线亮点")
                icons = ["❶", "❷", "❸", "❹", "❺"]
                for i, h in enumerate(highlights, 0):
                    if i < len(icons):
                        parts.append(f"{icons[i]} {h}")
                parts.append("")

            # 实用贴士
            tips = overview.get('tips', [])
            if tips:
                parts.append("💡 实用贴士")
                for tip in tips:
                    parts.append(f"• {tip}")
                parts.append("")

            # 互动引导
            cta = overview.get('call_to_action', '')
            if cta:
                parts.append(cta)

            return "\n".join(parts)
        except Exception as e:
            logger.error(f"格式化概览失败：{e}")
            return None


# 单例模式
_llm_service_instance = None

def get_llm_service() -> LLMService:
    """获取 LLMService 单例"""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
