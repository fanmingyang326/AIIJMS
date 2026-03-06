# ============================================================
# 用户模型 (users 表)
# 功能：存储教师和学生的账号信息
# 说明：
#   - username 字段对于学生角色是"学号"，对于教师角色是"工号"
#   - major 和 is_part_time 字段仅对学生角色有效
#   - role 字段取值为 "student" 或 "teacher"
#   - is_active 用于控制账号是否可以登录（教师可停用学生账号）
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from backend.app.models.base import Base

import enum


class UserRole(str, enum.Enum):
    """用户角色枚举：学生 / 教师"""
    STUDENT = "student"
    TEACHER = "teacher"


class User(Base):
    """
    用户表 ORM 模型

    字段说明：
        id            - 主键，自增
        username      - 登录用户名（学号 / 工号），全局唯一，不可重复
        password_hash - 密码的 bcrypt 哈希值
        full_name     - 用户真实姓名
        role          - 角色标识（student / teacher）
        is_active     - 账号启用状态，默认启用
        major         - 专业名称（仅学生角色有效，教师角色为 NULL）
        is_part_time  - 是否为非全日制学生（仅学生角色有效，教师角色为 NULL）
        created_at    - 账号创建时间，自动填充
    """
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="用户唯一标识，自增主键",
    )
    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="登录用户名（学生为学号，教师为工号）",
    )
    password_hash = Column(
        String(128),
        nullable=False,
        comment="密码的 bcrypt 哈希值",
    )
    full_name = Column(
        String(100),
        nullable=False,
        comment="用户真实姓名",
    )
    role = Column(
        SAEnum(UserRole, name="user_role_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.STUDENT,
        comment="用户角色：student（学生）/ teacher（教师）",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="账号是否处于启用状态，默认为 True",
    )
    major = Column(
        String(100),
        nullable=True,
        comment="专业名称（仅学生角色有效，教师角色此字段为 NULL）",
    )
    is_part_time = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="是否为非全日制学生（仅学生角色有效）",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="账号创建时间",
    )

    # -------------------- ORM 关联关系 --------------------

    # 教师发布的作业列表（一对多：一个教师 -> 多个作业）
    assignments = relationship(
        "Assignment",
        back_populates="teacher",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # 学生的提交记录列表（一对多：一个学生 -> 多条提交）
    submissions = relationship(
        "Submission",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
