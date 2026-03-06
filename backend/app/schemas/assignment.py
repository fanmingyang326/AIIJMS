# ============================================================
# 作业相关 Pydantic 模型
# 功能：定义作业模块所有 API 的请求体与响应体
# 包含：发布作业、更新作业、作业列表（含提交状态）等
# ============================================================

import json
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


# -------------------- 教师端：作业发布与管理 --------------------

class AssignmentCreate(BaseModel):
    """
    教师发布新作业的请求体
    接口：POST /api/teacher/assignments（由教师端调用）
    说明：
      - course_name         必填，课程名称
      - title               必填，作业标题
      - description         必填，作业要求的详细描述
      - deadline            必填，截止时间（ISO 8601 格式，精确到分钟）
      - allowed_extensions  必填，允许的文件后缀（逗号分隔字符串）
      - target_majors       可选，目标专业列表，为空表示面向所有专业
      - target_is_part_time 可选，目标学习类型，None=全部/False=全日制/True=非全日制
    """
    course_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="课程名称，如 '数据库原理'",
        examples=["数据库原理"],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="作业标题，如 '第三次实验报告'",
        examples=["第三次实验报告"],
    )
    description: str = Field(
        ...,
        min_length=1,
        description="作业要求的详细描述，支持长文本",
        examples=["请完成数据库 ER 图设计，并提交 PDF 格式的实验报告。"],
    )
    deadline: datetime = Field(
        ...,
        description="作业截止时间，ISO 8601 格式，精确到分钟，如 '2025-06-30T23:59'",
        examples=["2025-06-30T23:59:00"],
    )
    allowed_extensions: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="允许提交的文件后缀，逗号分隔，如 '.pdf,.zip,.docx'",
        examples=[".pdf,.zip"],
    )
    target_majors: Optional[List[str]] = Field(
        default=None,
        description=(
            "目标专业列表，如 ['软件工程', '计算机科学']。\n"
            "为 null 或不传表示面向所有专业。"
        ),
        examples=[["软件工程", "计算机科学"]],
    )
    target_is_part_time: Optional[bool] = Field(
        default=None,
        description=(
            "目标学习类型：\n"
            "- null（不传）= 面向所有学生（全日制 + 非全日制）\n"
            "- false = 仅面向全日制学生\n"
            "- true  = 仅面向非全日制学生"
        ),
    )


class AssignmentUpdate(BaseModel):
    """
    教师更新作业信息的请求体
    接口：PUT /api/teacher/assignments/{assignment_id}
    说明：所有字段均为可选，仅传需要修改的字段即可
    """
    course_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=150,
        description="课程名称（可选更新）",
    )
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="作业标题（可选更新）",
    )
    description: Optional[str] = Field(
        default=None,
        min_length=1,
        description="作业要求描述（可选更新）",
    )
    deadline: Optional[datetime] = Field(
        default=None,
        description="截止时间（可选更新）",
    )
    allowed_extensions: Optional[str] = Field(
        default=None,
        max_length=200,
        description="允许的文件后缀（可选更新）",
    )
    target_majors: Optional[List[str]] = Field(
        default=None,
        description="目标专业列表（可选更新），传空列表 [] 表示改为面向所有专业",
    )
    target_is_part_time: Optional[bool] = Field(
        default=None,
        description=(
            "目标学习类型（可选更新）：\n"
            "- null = 面向所有学生\n"
            "- false = 仅全日制\n"
            "- true = 仅非全日制"
        ),
    )


class AssignmentResponse(BaseModel):
    """
    作业详情响应体（完整信息）
    接口：GET /api/teacher/assignments/{assignment_id} 等
    """
    id: int = Field(..., description="作业 ID")
    course_name: str = Field(..., description="课程名称")
    title: str = Field(..., description="作业标题")
    description: str = Field(..., description="作业要求描述")
    deadline: datetime = Field(..., description="截止时间")
    allowed_extensions: str = Field(..., description="允许的文件后缀")
    target_majors: Optional[List[str]] = Field(
        default=None,
        description="目标专业列表，为 null 表示面向所有专业",
    )
    target_is_part_time: Optional[bool] = Field(
        default=None,
        description="目标学习类型：null=全部，false=仅全日制，true=仅非全日制",
    )
    teacher_id: int = Field(..., description="发布教师 ID")
    created_at: datetime = Field(..., description="作业创建时间")

    model_config = {"from_attributes": True}

    @field_validator("target_majors", mode="before")
    @classmethod
    def parse_target_majors(cls, v):
        """
        将数据库中的 JSON 字符串自动解析为 Python 列表
        例如：'["软件工程","计算机科学"]' → ["软件工程", "计算机科学"]
        """
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


# -------------------- 学生端：作业列表（含提交状态） --------------------

class AssignmentListItem(BaseModel):
    """
    学生端作业列表项（包含提交状态）
    接口：GET /api/student/assignments
    说明：
      - status 由后端根据学生的提交情况和截止时间动态计算：
        * "未交"   - 未过截止时间且该学生未提交
        * "已交"   - 该学生已提交
        * "已截止" - 已过截止时间且该学生未提交
    """
    id: int = Field(..., description="作业 ID")
    course_name: str = Field(..., description="课程名称")
    title: str = Field(..., description="作业标题")
    description: str = Field(..., description="作业要求描述")
    deadline: datetime = Field(..., description="截止时间")
    allowed_extensions: str = Field(..., description="允许的文件后缀")
    created_at: datetime = Field(..., description="作业创建时间")
    status: str = Field(
        ...,
        description="提交状态：未交 / 已交 / 已截止",
        examples=["未交"],
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="提交时间（仅状态为 '已交' 时有值）",
    )

    model_config = {"from_attributes": True}
