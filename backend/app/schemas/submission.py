# ============================================================
# 提交记录相关 Pydantic 模型
# 功能：定义提交模块所有 API 的响应体
# 说明：
#   - 提交接口 (POST) 使用 multipart/form-data，不需要 Pydantic 请求体
#   - 文件上传仅包含 file 字段，student_id 从 JWT Token 中解析
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubmissionResponse(BaseModel):
    """
    文件提交成功后的响应体
    接口：POST /api/student/assignments/{assignment_id}/submit
    """
    id: int = Field(..., description="提交记录 ID")
    file_path: str = Field(..., description="文件在服务器上的存储路径")
    submitted_at: datetime = Field(..., description="提交时间")
    status: str = Field(..., description="提交状态：submitted")
    student_id: int = Field(..., description="提交学生 ID")
    assignment_id: int = Field(..., description="所属作业 ID")
    message: str = Field(
        default="提交成功",
        description="操作结果提示信息",
    )

    model_config = {"from_attributes": True}


class SubmissionStatusResponse(BaseModel):
    """
    查询某学生对某作业的提交状态响应体
    用于 AI Agent 的 check_submission_status 工具
    """
    has_submitted: bool = Field(
        ...,
        description="是否已提交",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="已提交的文件名（未提交时为 None）",
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="提交时间（未提交时为 None）",
    )
    assignment_title: str = Field(
        ...,
        description="作业标题",
    )
    course_name: str = Field(
        ...,
        description="课程名称",
    )


class SubmissionDetail(BaseModel):
    """
    教师端查看某作业所有提交详情的响应体
    接口：GET /api/teacher/assignments/{assignment_id}/submissions
    包含学生信息，方便教师查看提交情况
    """
    id: int = Field(..., description="提交记录 ID")
    student_id: int = Field(..., description="学生 ID")
    student_name: str = Field(..., description="学生姓名")
    student_username: str = Field(..., description="学号")
    major: Optional[str] = Field(default=None, description="学生专业")
    is_part_time: Optional[bool] = Field(default=None, description="是否非全日制")
    file_path: str = Field(..., description="文件存储路径")
    submitted_at: datetime = Field(..., description="提交时间")
    status: str = Field(..., description="提交状态")

    model_config = {"from_attributes": True}
