# ============================================================
# Pydantic 模式包初始化文件
# 功能：统一导出所有请求/响应模型，方便路由层直接引用
# ============================================================

from backend.app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    PasswordChange,
    TokenResponse,
    UserInfo,
)
from backend.app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    AssignmentListItem,
)
from backend.app.schemas.submission import (
    SubmissionResponse,
    SubmissionStatusResponse,
)
from backend.app.schemas.chat import (
    ChatRequest,
    ChatResponse,
)

__all__ = [
    # 用户相关
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "PasswordChange",
    "TokenResponse",
    "UserInfo",
    # 作业相关
    "AssignmentCreate",
    "AssignmentUpdate",
    "AssignmentResponse",
    "AssignmentListItem",
    # 提交相关
    "SubmissionResponse",
    "SubmissionStatusResponse",
    # 聊天相关
    "ChatRequest",
    "ChatResponse",
]
