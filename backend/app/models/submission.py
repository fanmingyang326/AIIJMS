# ============================================================
# 提交记录模型 (submissions 表)
# 功能：存储学生对某个作业的文件提交记录
# 说明：
#   - 设定联合唯一约束 (student_id, assignment_id)
#     确保同一学生对同一作业只能有一条提交记录
#   - 若学生在截止前重复提交，后端采取"覆盖策略"：
#     更新 file_path、submitted_at 等字段，而非新增记录
#   - status 字段记录提交状态：submitted（已提交）/ pending（待提交）
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


class Submission(Base):
    """
    提交记录表 ORM 模型

    字段说明：
        id              - 主键，自增
        file_path       - 文件在服务器本地的存储路径
        submitted_at    - 文件提交（或覆盖重提交）的时间
        status          - 提交状态：
                            "submitted" = 已提交
                            "pending"   = 待提交（预留，暂未使用）
        student_id      - 提交该文件的学生 ID（外键关联 users 表）
        assignment_id   - 该提交所属的作业 ID（外键关联 assignments 表）

    联合唯一约束：
        (student_id, assignment_id) —— 同一学生对同一作业仅允许一条记录
    """
    __tablename__ = "submissions"

    # -------------------- 联合唯一约束 --------------------
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "assignment_id",
            name="uq_student_assignment",
        ),
        {"comment": "学生作业提交记录表"},
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="提交记录唯一标识，自增主键",
    )
    file_path = Column(
        String(500),
        nullable=False,
        comment="文件在服务器上的本地存储路径",
    )
    submitted_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="文件提交时间（覆盖重交时同步更新）",
    )
    status = Column(
        String(20),
        default="submitted",
        nullable=False,
        comment="提交状态：submitted（已提交）/ pending（待提交）",
    )
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="提交该文件的学生 ID，外键关联 users.id",
    )
    assignment_id = Column(
        Integer,
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        comment="该提交所属的作业 ID，外键关联 assignments.id",
    )

    # -------------------- ORM 关联关系 --------------------

    # 多对一：多条提交 -> 一个学生
    student = relationship(
        "User",
        back_populates="submissions",
    )

    # 多对一：多条提交 -> 一个作业
    assignment = relationship(
        "Assignment",
        back_populates="submissions",
    )

    def __repr__(self) -> str:
        return (
            f"<Submission(id={self.id}, student_id={self.student_id}, "
            f"assignment_id={self.assignment_id}, status='{self.status}')>"
        )
