# ============================================================
# CRUD 数据库操作层初始化文件
# 功能：统一导出所有 CRUD 操作函数，供路由层和服务层调用
# 说明：CRUD = Create（创建）Read（查询）Update（更新）Delete（删除）
# ============================================================

from backend.app.crud.crud_user import (
    get_user_by_id,
    get_user_by_username,
    get_all_students,
    create_student,
    update_student,
    delete_student,
    update_user_password,
    authenticate_user,
)
from backend.app.crud.crud_assignment import (
    create_assignment,
    get_all_assignments,
    get_assignment_by_id,
    update_assignment,
    delete_assignment,
    get_student_assignments_with_status,
    search_assignment_by_keyword,
    get_pending_assignments_for_student,
)
from backend.app.crud.crud_submission import (
    get_submission,
    create_or_update_submission,
    get_submissions_by_assignment,
    check_student_submission_status,
)

__all__ = [
    # 用户 CRUD
    "get_user_by_id",
    "get_user_by_username",
    "get_all_students",
    "create_student",
    "update_student",
    "delete_student",
    "update_user_password",
    "authenticate_user",
    # 作业 CRUD
    "create_assignment",
    "get_all_assignments",
    "get_assignment_by_id",
    "update_assignment",
    "delete_assignment",
    "get_student_assignments_with_status",
    "search_assignment_by_keyword",
    "get_pending_assignments_for_student",
    # 提交 CRUD
    "get_submission",
    "create_or_update_submission",
    "get_submissions_by_assignment",
    "check_student_submission_status",
]
