# ============================================================
# AI 智能问答路由模块
# 功能：处理学生端的 AI 对话请求
# 接口：
#   POST /api/chat/ask - 发送问题，获取 AI 智能回复
# 安全说明：
#   - student_id 绝不从请求体中获取
#   - 必须从 JWT Token 中解析学生身份
#   - 在 Agent 层面通过闭包将 student_id 硬性注入给 Tool
# 架构说明：
#   路由层仅负责：
#     1. 身份验证（从 Token 解析 student_id）
#     2. 会话管理（生成/维护 session_id）
#     3. 调用 Agent 服务并返回结果
#   实际 AI 推理逻辑全部在 agent_service.py 中实现
# ============================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_student
from backend.app.models.user import User
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.agent_service import run_agent

# 创建 AI 对话路由器
router = APIRouter(prefix="/chat", tags=["AI 智能问答"])


@router.post(
    "/ask",
    response_model=ChatResponse,
    summary="AI 智能问答",
    description=(
        "学生端全局悬浮对话框使用此接口。\n\n"
        "**功能**：\n"
        "- 使用 LangChain ReAct Agent + 通义千问 智能回答学生问题\n"
        "- 支持查询未交作业、作业详情、提交状态等\n"
        "- 支持多轮对话（通过 session_id 维持上下文记忆）\n\n"
        "**安全基线**：\n"
        "- student_id 从 JWT Token 解析，绝不由前端或大模型提供\n"
        "- Agent 的 Tool 通过闭包绑定 student_id，只能查询当前学生的数据\n"
        "- 即使恶意用户在对话中声称自己是另一个学生，\n"
        "  Tool 实际操作的仍然是 JWT Token 对应的学生数据\n\n"
        "**支持的问题类型**：\n"
        "- 「我还有哪些作业没交？」\n"
        "- 「数据库作业的要求是什么？」\n"
        "- 「我操作系统实验交了没？」\n"
        "- 以及基于上下文的多轮追问"
    ),
)
async def ask_ai(
    chat_request: ChatRequest,
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    AI 智能问答接口

    完整处理流程：
        1. 从 JWT Token 解析 student_id（安全上下文）
        2. 获取或生成 session_id（支持多轮追问）
        3. 调用 Agent 服务（run_agent）：
           a. 创建绑定了 student_id 的 Tools（闭包安全注入）
           b. 创建通义千问 LLM 实例
           c. 加载对话历史（Memory）
           d. Agent Executor 进行推理：
              - 分析学生问题
              - 决定调用哪个 Tool
              - 获取 Tool 返回的数据
              - 生成自然语言回复
           e. 保存对话到 Memory
        4. 返回 AI 回复和 session_id

    安全架构：
        ┌─────────────────────────────────┐
        │  前端发送: { message, session_id } │
        │  ❌ 不包含 student_id              │
        └──────────────┬──────────────────┘
                       │
                       ▼
        ┌─────────────────────────────────┐
        │  chat.py 路由层                   │
        │  ✅ 从 JWT Token 解析 student_id  │
        │  ✅ 调用 require_student 验证角色  │
        └──────────────┬──────────────────┘
                       │ student_id (安全值)
                       ▼
        ┌─────────────────────────────────┐
        │  agent_service.run_agent()       │
        │  ✅ 通过闭包将 student_id 注入 Tool│
        │  ✅ 大模型无法篡改此值             │
        └─────────────────────────────────┘

    请求体：
        message    - 学生的问题文本（1-2000 字符）
        session_id - 对话会话 ID（首次可不传，后端自动生成）

    响应：
        reply      - AI 助手的回复内容
        session_id - 对话会话 ID（前端需保存用于后续追问）

    错误响应：
        403 - 非学生角色
        500 - Agent 执行异常
    """
    # ---- 第 1 步：生成或使用已有的 session_id ----
    # 首次对话：前端不传 session_id，后端自动生成
    # 后续追问：前端传入之前返回的 session_id，维持上下文
    session_id = chat_request.session_id or str(uuid.uuid4())

    try:
        # ---- 第 2 步：调用 Agent 服务处理问题 ----
        # student.id 从 JWT Token 安全解析，作为上下文注入给 Agent
        reply = await run_agent(
            question=chat_request.message,
            student_id=student.id,    # ✅ 来自 JWT Token，非前端传递
            session_id=session_id,
            db=db,
        )

        # ---- 第 3 步：返回 AI 回复 ----
        return ChatResponse(
            reply=reply,
            session_id=session_id,
        )

    except Exception as e:
        # Agent 服务内部已做了异常处理并返回友好提示
        # 此处捕获的是 Agent 服务本身的严重错误
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 助手服务异常：{str(e)}",
        )
