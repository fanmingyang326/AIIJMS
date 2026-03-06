# ============================================================
# 数据库模型包初始化文件
# 功能：统一导出所有 SQLAlchemy 模型，方便外部引用
# ============================================================

from backend.app.models.user import User
from backend.app.models.assignment import Assignment
from backend.app.models.submission import Submission

# 导出所有模型，供 Alembic 迁移和其他模块使用
__all__ = ["User", "Assignment", "Submission"]
