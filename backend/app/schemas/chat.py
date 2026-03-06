# ============================================================
# 智能问答（AI Chat）相关 Pydantic 模型
# 功能：定义 AI 对话模块的请求体与响应体
# 说明：
#   - 学生端右下角全局悬浮对话框使用此接口
#   - student_id 绝不允许前端传递，必须从 JWT Token 解析
#   - session_id 用于支持多轮对话的记忆管理
# ============================================================

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    AI 对话请求体
    接口：POST /api/chat/ask
    说明：
      - message 为用户输入的问题文本
      - session_id 用于标识对话会话，支持多轮追问
        首次对话可不传，后端会自动生成并在响应中返回
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户输入的问题",
        examples=["我还有哪些作业没交？"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="对话会话 ID（首次可不传，后端自动生成）",
    )


class ChatResponse(BaseModel):
    """
    AI 对话响应体
    接口：POST /api/chat/ask
    """
    reply: str = Field(
        ...,
        description="AI 助手的回复内容",
    )
    session_id: str = Field(
        ...,
        description="对话会话 ID，前端需保存用于后续多轮追问",
    )
