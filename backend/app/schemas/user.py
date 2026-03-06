# ============================================================
# 用户相关 Pydantic 模型
# 功能：定义用户模块所有 API 的请求体与响应体
# 包含：登录、创建学生、更新学生信息、修改密码、Token 响应等
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# -------------------- 登录相关 --------------------

class UserLogin(BaseModel):
    """
    登录请求体
    接口：POST /api/auth/login
    """
    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="登录用户名（学生填学号，教师填工号）",
        examples=["2024001"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="登录密码",
        examples=["123456"],
    )


class UserInfo(BaseModel):
    """
    登录成功后返回的用户基本信息（嵌套在 TokenResponse 中）
    """
    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名（学号/工号）")
    full_name: str = Field(..., description="真实姓名")
    role: str = Field(..., description="角色：student / teacher")

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    登录成功响应体
    接口：POST /api/auth/login
    返回 JWT access_token 及用户基本信息
    """
    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型，固定为 bearer")
    user: UserInfo = Field(..., description="当前登录用户的基本信息")


# -------------------- 修改密码 --------------------

class PasswordChange(BaseModel):
    """
    修改密码请求体
    接口：PUT /api/auth/password
    说明：学生登录后可修改默认密码
    """
    old_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="当前密码（旧密码）",
    )
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="新密码（至少 6 位）",
    )


# -------------------- 学生 CRUD 相关 --------------------

class UserCreate(BaseModel):
    """
    教师创建（录入）学生的请求体
    接口：POST /api/admin/students
    说明：
      - 系统不提供自主注册功能，由教师后台录入学生名单
      - 系统会根据 username 自动生成默认密码哈希值
      - major 和 is_part_time 为学生特有字段
    """
    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="学号，作为登录用户名，全局唯一",
        examples=["2024001"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="学生真实姓名",
        examples=["张三"],
    )
    major: Optional[str] = Field(
        default=None,
        max_length=100,
        description="专业名称，如 '计算机科学与技术'",
        examples=["计算机科学与技术"],
    )
    is_part_time: bool = Field(
        default=False,
        description="是否为非全日制学生，默认为 False（全日制）",
    )


class UserUpdate(BaseModel):
    """
    教师更新学生信息的请求体
    接口：PUT /api/admin/students/{student_id}
    说明：所有字段均为可选，仅传需要修改的字段即可（部分更新）
    """
    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="学生姓名（可选更新）",
    )
    major: Optional[str] = Field(
        default=None,
        max_length=100,
        description="专业名称（可选更新）",
    )
    is_part_time: Optional[bool] = Field(
        default=None,
        description="是否非全日制（可选更新）",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="是否启用账号（可选更新，教师可停用/启用学生）",
    )


class UserResponse(BaseModel):
    """
    学生信息响应体（用于列表展示和详情查看）
    接口：GET /api/admin/students 及 GET /api/admin/students/{student_id}
    """
    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="学号")
    full_name: str = Field(..., description="真实姓名")
    role: str = Field(..., description="角色：student")
    is_active: bool = Field(..., description="账号是否启用")
    major: Optional[str] = Field(default=None, description="专业名称")
    is_part_time: Optional[bool] = Field(default=None, description="是否非全日制")
    created_at: datetime = Field(..., description="账号创建时间")

    model_config = {"from_attributes": True}
