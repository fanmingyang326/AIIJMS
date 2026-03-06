# ============================================================
# SQLAlchemy 声明式基类
# 功能：定义所有 ORM 模型的统一基类
# ============================================================

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    所有 SQLAlchemy ORM 模型的声明式基类。
    所有表模型必须继承此类，以便 Alembic 自动检测并管理数据库迁移。
    """
    pass
