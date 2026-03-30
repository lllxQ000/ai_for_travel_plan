from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class TravelPreferences(BaseModel):
    """
    旅游偏好 Schema - 对应前端表单字段
    技术原理：Pydantic 在运行时进行类型验证和 JSON 序列化
    面试考点：数据验证、类型提示、嵌套模型
    """
    # 必填字段
    duration_days: int = Field(..., ge=1, le=30, description="旅行天数 (1-30 天)")
    
    trip_type: str = Field(
        ...,
        pattern="^(personal|family|couple|friends)$",
        description="出行类型"
    )
    
    style: str = Field(
        ...,
        pattern="^(relaxed|intensive|cultural|adventure)$",
        description="旅行风格"
    )
    
    origin_city: str = Field(..., min_length=1, max_length=50, description="出发城市")
    destination: str = Field(..., min_length=1, max_length=50, description="目的地")
    
    # 选填字段
    budget_level: str = Field(
        default="medium",
        pattern="^(budget|medium|luxury)$",
        description="预算等级"
    )
    
    interests: List[str] = Field(default_factory=list, description="兴趣标签列表")
    
    travel_date: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="出行日期 (YYYY-MM-DD)"
    )


class ChatRequest(BaseModel):
    """
    聊天请求 Schema - 接收前端完整 JSON 请求体
    嵌套结构包含用户偏好
    """
    user_id: str = Field(..., min_length=1, description="用户 ID")
    session_id: Optional[str] = Field(None, description="会话 ID")
    preferences: TravelPreferences  # 嵌套的表单数据结构
    message: Optional[str] = Field(default="", max_length=500, description="用户补充说明")
    stream: bool = Field(default=True)


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    chunks_processed: int


class SessionInfo(BaseModel):
    session_id: str
    title: str
    created_at: str