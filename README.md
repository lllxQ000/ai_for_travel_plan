<div align="center">

# AI 旅行路线规划师 (AI for Travel Plan)

**基于 AIGC 与 RAG 技术的全流程个性化旅游写作辅助工具**

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/Version-v1.0.0-green.svg)](https://github.com/your-username/your-repo)
[![Interests](https://img.shields.io/badge/Interests-8+-orange.svg)](#)
[![Tech](https://img.shields.io/badge/Stack-Python%20|%20Vue-blueviolet.svg)](#)
[![GitHub stars](https://img.shields.io/github/stars/your-username/your-repo?style=social)](https://github.com/your-username/your-repo)

---
</div>



## 目录

1. [项目概述](#1-项目概述)
2. [技术栈说明](#2-技术栈说明)
3. [项目目录结构](#3-项目目录结构)
4. [整体架构图](#4-整体架构图)
5. [前端模块详解](#5-前端模块详解)
6. [后端模块详解](#6-后端模块详解)
7. [完整调用流程](#7-完整调用流程)
8. [关键技术点解析](#8-关键技术点解析)

---

## 1. 项目概述

### 1.1 项目背景

这是一个基于 AIGC 的旅游路线规划系统。用户选择目的地、游玩天数和偏好标签后，后端先通过 RAG（检索增强生成）从向量知识库中检索匹配的旅游路线，再调用大语言模型结合联网搜索，为用户生成详细的行程规划和小红书风格的种草文案。

### 1.2 核心功能

| 功能 | 说明 |
|------|------|
| 目的地选择 | 卡片式 UI，支持/暂未支持一目了然 |
| 天数与偏好 | 大按钮天数选择器 + 不规则标签云 |
| RAG 智能检索 | 从 CSV 知识库中向量检索相关旅游路线 |
| AI 路线详情生成 | 调用大模型 + 联网搜索，生成细化到分钟的行程 |
| 小红书风格概览 | 生成爆款标题、开头抓眼、亮点、互动引导等种草文案 |

### 1.3 用户使用流程

```
用户打开网页
      |
      v
选择目的地（点击桂林卡片）
      |
      v
选择游玩天数（2/3/5/7 天）
      |
      v
勾选偏好标签（山水、美食、拍照...）
      |
      v
点击"生成逃离计划"
      |
      v
看到 RAG 检索出的路线卡片
      |
      v
点击卡片 -> 等待 LLM 生成 -> 看到完整行程 + 小红书概览
```

---

## 2. 技术栈说明

### 2.1 前端

| 技术 | 作用 |
|------|------|
| HTML5 | 页面结构 |
| CSS3 | 反主流美学风格（硬阴影、不对称圆角、弹簧动画） |
| 原生 JavaScript | 交互逻辑，Fetch API 调用后端 |
| Iconify | 图标库（CDN 加载） |

### 2.2 后端

| 技术 | 用途 | 版本 |
|------|------|------|
| Python | 编程语言 | 3.10+ |
| Flask | Web 框架，提供 RESTful API | 3.0 |
| flask-cors | 跨域支持 | 5.0 |
| ChromaDB | 向量数据库 | 0.5 |
| LangChain | Document 对象、文本分割 | 0.3 |
| jieba | 中文分词 | 0.42 |
| python-dotenv | 环境变量加载 | 1.0 |

### 2.3 AI 服务（阿里云百炼 / DashScope）

| 服务 | 模型 | 用途 |
|------|------|------|
| 大语言模型 | qwen3.5-plus-2026-02-15 | 路线详情生成 + 小红书文案 |
| 文本向量化 | text-embedding-v2 | 1536 维向量 |
| 联网搜索 | enable_search=true | 实时搜索当地餐厅、酒店 |

---

## 3. 项目目录结构

```
AI_for_travel_plan/
├── frontend/                        # 前端代码
│   ├── index.html                   # 单页面应用
│   ├── styles.css                   # 反主流美学样式（25KB）
│   └── app.js                       # 交互逻辑（660 行）
│
├── backend/                         # 后端代码
│   ├── app.py                       # Flask 中枢（228 行）— 伪 OpenCLaw
│   ├── llm_service.py               # LLM 生成服务（227 行）
│   ├── rag_pipeline.py              # RAG 检索 Pipeline（200 行）
│   ├── chroma_client.py             # ChromaDB 客户端（343 行）
│   ├── embedding.py                 # 向量化服务（218 行）
│   ├── csv_loader.py                # CSV 知识库加载器（314 行）
│   ├── import_knowledge.py          # 知识库导入脚本（207 行）
│   ├── rag_utils.py                 # RAG 工具函数集合（169 行）
│   ├── utils.py                     # 通用工具（47 行）
│   ├── __init__.py
│   ├── .env                         # 环境变量（API Key，已 gitignore）
│   ├── examples/                    # 示例代码
│   └── logs/                        # 日志目录（gitignore）
│
├── data/                            # 数据目录（gitignore）
├── .gitignore
└── requirements.txt
```

---

## 4. 整体架构图

### 4.1 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户浏览器                            │
│               frontend/index.html                       │
│            (原生 HTML + CSS + JS)                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ POST /api/generate    (RAG 检索)
                     │ POST /api/route-detail (LLM 生成)
                     ▼
┌─────────────────────────────────────────────────────────┐
│                Flask 后端 (app.py)                       │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  /api/generate    → rag_pipeline.search_routes() │   │
│  │  /api/route-detail → llm_service.generate_*()    │   │
│  └─────────────────────────────────────────────────┘   │
└──────┬──────────────────────────┬───────────────────────┘
       │                          │
       ▼                          ▼
┌──────────────────┐  ┌──────────────────────────┐
│  RAG 检索层       │  │  LLM 生成层               │
│  (rag_pipeline)   │  │  (llm_service)            │
│                  │  │                          │
│  1.构建查询文本   │  │  1.路线详情生成            │
│  2.向量化(1536维) │  │    - 细化到分钟的行程      │
│  3.ChromaDB 检索  │  │    - 美食/住宿推荐         │
│  4.目的地过滤     │  │    - 预算估算              │
│  5.天数过滤+排序  │  │                          │
│                  │  │  2.小红书风格概览           │
└────────┬─────────┘  │    - 爆款标题              │
         │            │    - 开头抓眼              │
         ▼            │    - 互动引导              │
┌──────────────────┐  └────────────┬─────────────┘
│  向量数据库层     │               │
│  (chroma_client) │               ▼
│                  │  ┌──────────────────────────┐
│  ChromaDB        │  │  DashScope API            │
│  - 跨集合查询    │  │  - qwen3.5-plus           │
│  - 元数据过滤    │  │  - enable_search=true     │
│                  │  │  - 联网搜索实时信息        │
└──────────────────┘  └──────────────────────────┘
```

### 4.2 数据流

```
用户输入
   │
   ▼
选择目的地+天数+偏好
   │
   ▼
POST /api/generate → RAGPipeline.search_routes()
   │
   ├─ 构建查询："我想去桂林旅游；喜欢美食、拍照"
   ├─ 向量化查询 → 1536 维
   ├─ ChromaDB 跨集合检索 → 10 条结果
   ├─ 目的地匹配过滤 + 天数匹配过滤
   └─ 三级排序 → 返回最佳路线
   │
   ▼
前端展示路线卡片 → 用户点击
   │
   ▼
POST /api/route-detail
   │
   ├─ generate_xiaohongshu_overview()  (~14s)
   ├─ generate_route_detail()          (~34s)
   ├─ 合并：detail['overview'] = 小红书格式化文本
   └─ 降级模板（LLM 失败时）
   │
   ▼
前端显示完整行程
```


---

## 5. 前端模块详解

### 5.1 文件说明

| 文件 | 大小 | 职责 |
|------|------|------|
| index.html | 8.6KB | 页面结构，卡片式 UI，标签云，弹窗 |
| styles.css | 25KB | 设计系统（CSS 变量、硬阴影、弹簧动画） |
| app.js | 24KB / 660 行 | 交互逻辑、API 调用、DOM 渲染 |

### 5.2 状态管理

不使用任何框架，全局变量管理状态：

```javascript
let selectedDestination = '';   // 选中的目的地
let selectedDays = 3;           // 选中的天数（默认 3）
let selectedTags = [];          // 已选偏好标签
const SUPPORTED_DESTINATIONS = ['桂林'];
```

### 5.3 目的地卡片

```javascript
destinationCards.forEach(card => {
    card.addEventListener('click', () => {
        if (card.classList.contains('unsupported')) {
            showToast('该目的地暂未支持，请选择桂林');
            return;
        }
        destinationCards.forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedDestination = card.dataset.destination;
    });
});
```

### 5.4 核心 API 调用

```javascript
// RAG 检索
async function handleGenerate() {
    const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            destination: selectedDestination,
            days: selectedDays,
            preferences: selectedTags
        })
    });
    const data = await response.json();
    displayRoutes(data.routes);
}

// LLM 详情生成
async function showRouteDetail(route) {
    const response = await fetch('/api/route-detail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ route, preferences: selectedTags })
    });
    const detail = await response.json();
    displayRouteDetail(detail);
}
```

### 5.5 设计系统

```css
:root {
    --bg-primary: #FDFCF0;                    /* 米白底 */
    --industrial-black: #1A1A1A;              /* 工业黑 */
    --warning-yellow: #F4DB4D;                /* 警示黄 */
    --rust-red: #D32F2F;                      /* 锈红 */
    --concrete-gray: #8B8B8B;                 /* 水泥灰 */
    --hard-shadow: 4px 4px 0px var(--industrial-black);
    --spring-easing: cubic-bezier(0.34, 1.56, 0.64, 1);
    --radius-tl: 16px; --radius-tr: 8px;      /* 不对称圆角 */
    --radius-br: 12px; --radius-bl: 6px;
}
```

核心设计理念：硬阴影、不对称圆角、弹簧动画、噪点纹理——"打破常规"的工业反主流感。


---

## 6. 后端模块详解

### 6.1 Flask 中枢 (app.py) — 228 行

设计理念：app.py 作为"伪 OpenCLaw"，仅路由分发和模块调用，不含业务逻辑。

| 路由 | 方法 | 功能 | 调用模块 |
|------|------|------|---------|
| `/` | GET | 前端首页 | Flask static |
| `/api/health` | GET | 健康检查 | — |
| `/api/generate` | POST | RAG 检索路线 | `rag_pipeline.search_routes()` |
| `/api/route-detail` | POST | LLM 生成详情+概览 | `llm_service.generate_*()` |

核心路由 `/api/route-detail`：

```python
@app.route('/api/route-detail', methods=['POST'])
def get_route_detail():
    route = request.get_json()['route']

    # 1. 优先生成小红书概览（核心展示内容）
    xiaohongshu = llm_service.generate_xiaohongshu_overview(...)

    # 2. 生成路线详情
    detail = llm_service.generate_route_detail(...)

    # 3. 合并：用小红书内容覆盖 overview 字段
    if xiaohongshu and detail:
        overview_text = LLMService.format_overview(xiaohongshu)
        if overview_text:
            detail['overview'] = overview_text
        detail['route_overview'] = xiaohongshu

    # 4. LLM 失败时降级到本地模板
    if not detail:
        detail = generate_template_route(destination, days, preferences)

    return jsonify(detail)
```

### 6.2 LLM 服务 (llm_service.py) — 227 行

所有 LLM 生成任务统一入口：API 调用 + prompt 工程 + 结果解析。

```python
class LLMService:
    def _call_llm(...)                       # 通用 LLM 调用
    def generate_route_detail(...)           # 路线详情生成
    def generate_xiaohongshu_overview(...)   # 小红书风格概览
    @staticmethod
    def format_overview(...)                 # 格式化概览文本
```

#### 通用调用方法

```python
def _call_llm(self, system_prompt, user_prompt,
              temperature=0.7, max_tokens=None,
              enable_search=True, timeout=60):
    payload = {
        "model": self.model,              # qwen3.5-plus-2026-02-15
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
        "extra_body": {"enable_search": enable_search}  # ★ 联网搜索
    }
    response = self.session.post(
        f"{self.base_url}/chat/completions", json=payload, timeout=timeout
    )
    content = response.json()['choices'][0]['message']['content']
    # 自动清理 markdown 标记，解析 JSON
    return json.loads(content.replace('```json', '').replace('```', '').strip())
```

#### 路线详情 Prompt 要点

- 时间细化到分钟（09:00-11:00）
- 每个景点含交通方式、门票信息、游玩贴士
- ★标注必体验，？标注避坑指南
- 美食推荐基于路线地点搜索当地热门餐厅
- 住宿推荐基于路线区域搜索真实酒店/民宿

#### 小红书概览 Prompt 要点

- 爆款标题：3-5 个备选，含数字、对比、疑问、情感词
- 开头抓眼：前 3 行足够吸引，悬念或强烈情感
- 内容价值：结构化呈现路线亮点和实用干货
- 人情共鸣：口语化 + emoji + 感叹号
- 结合联网搜索获取最新热门玩法、网红打卡点


#### 小红书概览格式化

```python
@staticmethod
def format_overview(overview: Dict) -> str:
    parts = []
    titles = overview.get('titles', [])
    if titles:
        parts.append(f"🔥 {titles[0]}")

    opening = overview.get('opening', '')
    if opening:
        parts.append(opening)

    highlights = overview.get('highlights', [])
    if highlights:
        parts.append("✨ 路线亮点")
        icons = ["❶", "❷", "❸", "❹", "❺"]
        for i, h in enumerate(highlights):
            if i < len(icons):
                parts.append(f"{icons[i]} {h}")

    tips = overview.get('tips', [])
    if tips:
        parts.append("💡 实用贴士")
        for tip in tips:
            parts.append(f"• {tip}")

    cta = overview.get('call_to_action', '')
    if cta:
        parts.append(cta)

    return "\n".join(parts)
```

格式化输出示例：

```
🔥 3天2晚私家团实测！桂林阳朔美到我连夜删掉所有滤镜！！

救命！！这真的是我人生拍过最多九宫格的一次旅行😭

✨ 路线亮点
❶ 象鼻山 → 桂林城徽，必打卡
❷ 游船游漓江 → 九马画山绝美
❸ 遇龙河竹筏漂流 → 体验感拉满
❹ 阳朔西街 → 夜生活+美食天堂

💡 实用贴士
• 建议穿防滑鞋，芦笛岩洞内湿滑
• 旺季需提前 3 天预约门票

评论区扣【路线】，我把完整行程发你！👇
```

### 6.3 RAG 检索 Pipeline (rag_pipeline.py) — 200 行

从 ChromaDB 向量知识库检索匹配的旅游路线。

```python
class RAGPipeline:
    def search_routes(self, destination, days, preferences):
        # 1. 构建查询："我想去桂林旅游；喜欢美食、拍照"
        query_text = self._build_query_text(destination, preferences)

        # 2. 向量化查询 → 1536 维向量
        query_embedding = self.embedding_service.get_embedding(query_text)

        # 3. 跨所有知识库集合检索 → 最多 10 条
        results = self.chroma_client.query_knowledge_across_all(
            query_embedding=query_embedding, n_results=10
        )

        # 4. 过滤 + 排序 → 返回最佳路线
        return self._process_results(results, destination, days, preferences)
```

**过滤策略**：
- 目的地匹配：product_name 或 route 中必须包含目的地名
- 天数匹配：route['days'] == 用户选择的天数
- 三级排序：匹配度 → 向量距离 → 销量

### 6.4 ChromaDB 客户端 (chroma_client.py) — 343 行

- 持久化存储：`data/chroma/chroma.sqlite3`
- 集合命名：`knowledge_{CSV文件名}`
- 核心方法：`query_knowledge_across_all()` 跨集合检索
- 去重机制：添加时自动检查已有 ID

### 6.5 向量化服务 (embedding.py) — 218 行

三层降级策略：

```python
if dashscope_api_key:
    → 使用 DashScope API（阿里云百炼）★ 当前使用
elif ollama_available:
    → 使用本地 Ollama
else:
    → 使用 sentence-transformers 本地模型
```

关键细节：通过 `session.trust_env = False` 绕过系统代理。

### 6.6 CSV 知识库加载器 (csv_loader.py) — 314 行

将旅游线路 CSV 转为 LangChain Document：
- `page_content`：产品名称 + 轨迹路线（检索匹配）
- `metadata`：sales, reviews, days（过滤排序）

### 6.7 知识库导入 (import_knowledge.py) — 207 行

```bash
python backend/import_knowledge.py
python backend/import_knowledge.py --files data/knowledge_1.csv
python backend/import_knowledge.py --batch-size 100
```

### 6.8 环境变量 (.env)

```bash
ARK_API_KEY=sk-xxx
MODEL=qwen3.5-plus-2026-02-15
MAX_TOKENS=1500
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v2
```

> `.env` 已加入 `.gitignore`，API Key 不会泄露到 GitHub。


---

## 7. 完整调用流程

### 7.1 函数调用栈

```
用户点击"生成逃离计划"
      │
      ▼
1. app.js: handleGenerate()
      │ POST /api/generate
      ▼
2. app.py: generate_route()
      │
      └─→ rag_pipeline.search_routes()
           ├─ _build_query_text()               → 构建查询
           ├─ embedding_service.get_embedding()  → 向量化(1536维)
           ├─ chroma_client.query_across_all()   → ChromaDB 检索
           └─ _process_results()                → 过滤+排序
      │
      ▼
3. 前端展示路线卡片
      │ 用户点击路线
      ▼
4. app.js: showRouteDetail()
      │ POST /api/route-detail
      ▼
5. app.py: get_route_detail()
      │
      ├─ generate_xiaohongshu_overview()  (~14s, enable_search=true)
      ├─ generate_route_detail()          (~34s, enable_search=true)
      ├─ format_overview() + 合并到 detail['overview']
      └─ 失败 → generate_template_route() → 降级模板
      │
      ▼
6. app.js: displayRouteDetail()
      ├─ 路线概览 (小红书风格文案)
      ├─ 每日行程 (时间/景点/交通/贴士)
      ├─ 美食推荐 + 住宿推荐
      └─ 旅行贴士 + 预算
```

### 7.2 时序图

```
浏览器           Flask            RAGPipeline    LLMService     DashScope
  │                │                  │              │              │
  │─POST generate─→│                  │              │              │
  │                │─search_routes()─→│              │              │
  │                │                  │─embedding()─→│              │
  │                │                  │              │─embeddings──→│
  │                │                  │              │←─1536维──────│
  │                │                  │─query()─────→│              │
  │                │                  │←─10条────────│              │
  │                │                  │─过滤+排序────│              │
  │                │←─2条路线─────────│              │              │
  │←─{routes}──────│                  │              │              │
  │                │                  │              │              │
  │  用户点击路线   │                  │              │              │
  │─POST detail───→│                  │              │              │
  │                │─gen_xiaohongshu()──────────────→│              │
  │                │                  │              │─chat API────→│
  │                │                  │              │  +search=true│
  │                │                  │              │←─小红书JSON───│
  │                │←─{titles,opening,highlights...} │              │
  │                │─gen_route_detail()─────────────→│              │
  │                │                  │              │─chat API────→│
  │                │                  │              │←─行程JSON─────│
  │                │  合并overview    │              │              │
  │←─{overview,schedule,food...}     │              │              │
  │                │                  │              │              │
  │  渲染完整行程   │                  │              │              │
```


---

## 8. 关键技术点解析

### 8.1 RAG 检索增强生成

```
用户查询 "桂林 3 天 美食拍照"
        │
        ▼
┌──────────────┐
│ 向量化查询    │ text-embedding-v2 → 1536 维
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 向量相似检索  │ ChromaDB cosine similarity，跨 3 个集合
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 元数据过滤    │ 目的地包含"桂林" + days == 3
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 三级排序      │ 匹配度 → 向量距离 → 销量
└──────┬───────┘
       │
       ▼
 返回匹配路线 → 传给 LLM → 联网搜索增强 → 生成详细行程
```

### 8.2 联网搜索

通过 `extra_body: {"enable_search": true}` 让模型实时搜索互联网：

- 美食推荐基于当地最新热门餐厅和评价
- 住宿推荐基于真实可预订的酒店，含区域和优势
- 避坑指南基于近期游客真实反馈

### 8.3 性能优化

| 指标 | qwen3.5-plus (旧) | qwen3.5-plus-2026-02-15 (新) | 提升 |
|------|-------------------|------------------------------|------|
| 小红书概览生成 | ~48s | ~14s | 70% |
| 路线详情生成 | ~66s | ~34s | 48% |
| 总计耗时 | ~114s | ~48s | 58% |

### 8.4 降级策略

三层降级确保服务可用：

```python
# 第一层：LLM 调用失败 → 本地模板
if not detail:
    detail = generate_template_route(destination, days, preferences)

# 第二层：向量化失败 → 零向量
except Exception:
    query_embedding = [0.0] * 768

# 第三层：ChromaDB 查询异常 → 空结果
except Exception:
    return {'ids': [], 'documents': [], 'metadatas': []}
```

### 8.5 单例模式

避免重复初始化 LLMService，节省资源：

```python
_llm_service_instance = None

def get_llm_service():
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
```

### 8.6 代理绕过

DashScope API 不需要通过代理访问，项目在多个层面确保直连：

```python
# 清除系统代理环境变量
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(proxy_var, None)

# requests Session 级别绕过
session = requests.Session()
session.trust_env = False
session.proxies = {'http': '', 'https': ''}
```


---


项目架构图（一览）

```
frontend/                    backend/
┌────────────┐              ┌──────────────────────┐
│ index.html │──fetch()────→│ app.py (中枢)         │
│ styles.css │              │   ├─ rag_pipeline.py  │→ ChromaDB
│ app.js     │              │   └─ llm_service.py   │→ DashScope API
└────────────┘              └──────────────────────┘
```

---

## License

MIT © 2024
