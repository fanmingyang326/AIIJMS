# ============================================================
# 作业模型 (assignments 表)
# 功能：存储教师发布的作业信息
# 说明：
#   - course_name         用于标识该作业所属的课程
#   - deadline            截止时间精确到分钟
#   - allowed_extensions  存储允许的文件后缀，如 ".pdf,.zip,.docx"
#   - teacher_id          外键关联发布该作业的教师
#   - target_majors       目标专业列表（JSON），为空表示面向所有专业
#   - target_is_part_time 目标学习类型，NULL=全部，True=仅非全日制，False=仅全日制
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


class Assignment(Base):
    """
    作业表 ORM 模型

    字段说明：
        id                  - 主键，自增
        course_name         - 课程名称（如 "数据库原理"、"操作系统"）
        title               - 作业标题（如 "第三次实验报告"）
        description         - 作业要求的详细描述（支持长文本）
        deadline            - 作业截止时间，精确到分钟
        allowed_extensions  - 允许提交的文件后缀，逗号分隔字符串（如 ".pdf,.zip"）
        target_majors       - 目标专业列表，JSON 字符串（如 '["软件工程","计算机科学"]'）
                              为 NULL 或空表示面向所有专业
        target_is_part_time - 目标学习类型：
                              NULL = 面向所有学生（全日制 + 非全日制）
                              False = 仅面向全日制学生
                              True  = 仅面向非全日制学生
        teacher_id          - 发布该作业的教师 ID（外键关联 users 表）
        created_at          - 作业发布（创建）时间
    """
    __tablename__ = "assignments"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="作业唯一标识，自增主键",
    )
    course_name = Column(
        String(150),
        nullable=False,
        index=True,
        comment="课程名称，如 '数据库原理'",
    )
    title = Column(
        String(200),
        nullable=False,
        comment="作业标题，如 '第三次实验报告'",
    )
    description = Column(
        Text,
        nullable=False,
        comment="作业要求的详细描述，支持长文本",
    )
    deadline = Column(
        DateTime,
        nullable=False,
        comment="作业截止时间，精确到分钟",
    )
    allowed_extensions = Column(
        String(200),
        nullable=False,
        default=".pdf,.zip",
        comment="允许提交的文件后缀，逗号分隔，如 '.pdf,.zip,.docx'",
    )
    target_majors = Column(
        Text,
        nullable=True,
        default=None,
        comment="目标专业列表，JSON 格式，如 '[\"软件工程\",\"计算机科学\"]'，为 NULL 表示面向所有专业",
    )
    target_is_part_time = Column(
        Boolean,
        nullable=True,
        default=None,
        comment="目标学习类型：NULL=全部学生，False=仅全日制，True=仅非全日制",
    )
    teacher_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发布该作业的教师 ID，外键关联 users.id",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="作业发布时间，自动填充当前时间",
    )

    # -------------------- ORM 关联关系 --------------------

    # 多对一：多个作业 -> 一个教师
    teacher = relationship(
        "User",
        back_populates="assignments",
    )

    # 一对多：一个作业 -> 多条提交记录
    submissions = relationship(
        "Submission",
        back_populates="assignment",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return (
            f"<Assignment(id={self.id}, course='{self.course_name}', "
            f"title='{self.title}', deadline='{self.deadline}')>"
        )
