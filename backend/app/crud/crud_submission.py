# ============================================================
# 提交记录 CRUD 操作层
# 功能：封装所有与提交记录表 (submissions) 相关的数据库操作
# 包含：
#   - 查询已有提交记录
#   - 创建或覆盖提交记录（覆盖重交逻辑核心）
#   - 查询某作业的所有提交（教师端）
#   - AI Agent 专用：检查提交状态
# ============================================================

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload

from backend.app.models.submission import Submission
from backend.app.models.assignment import Assignment
from backend.app.models.user import User


# ==================== 查询操作 ====================

def get_submission(
    db: Session,
    student_id: int,
    assignment_id: int,
) -> Optional[Submission]:
    """
    查询某学生对某作业的提交记录

    参数：
        db            - 数据库会话
        student_id    - 学生 ID
        assignment_id - 作业 ID

    返回：
        Submission 对象，未提交则返回 None

    说明：
        由于联合唯一约束 (student_id, assignment_id)，
        同一学生对同一作业最多只有一条记录
    """
    return (
        db.query(Submission)
        .filter(
            Submission.student_id == student_id,
            Submission.assignment_id == assignment_id,
        )
        .first()
    )


def get_submissions_by_assignment(
    db: Session,
    assignment_id: int,
) -> List[Submission]:
    """
    查询某作业下的所有提交记录（教师端使用）

    参数：
        db            - 数据库会话
        assignment_id - 作业 ID

    返回：
        该作业的所有提交记录列表，包含关联的学生信息

    说明：
        - 使用 joinedload 预加载学生信息，避免 N+1 查询问题
        - 按提交时间倒序排列（最新提交的在前）
    """
    return (
        db.query(Submission)
        .options(joinedload(Submission.student))  # 预加载学生关系
        .filter(Submission.assignment_id == assignment_id)
        .order_by(Submission.submitted_at.desc())
        .all()
    )


# ==================== 创建/覆盖操作 ====================

def create_or_update_submission(
    db: Session,
    student_id: int,
    assignment_id: int,
    file_path: str,
) -> tuple[Submission, bool]:
    """
    创建提交记录 或 覆盖已有提交（覆盖重交逻辑核心）

    参数：
        db            - 数据库会话
        student_id    - 学生 ID（从 JWT Token 解析，绝不由前端传递）
        assignment_id - 作业 ID
        file_path     - 文件在服务器上的存储路径

    返回：
        元组 (Submission, is_new)：
        - Submission: 提交记录对象
        - is_new: True 表示新建，False 表示覆盖更新

    覆盖重交逻辑：
        1. 查询该学生对该作业是否已有提交记录
        2. 若有 → 更新 file_path 和 submitted_at（旧文件由 file_service 负责删除）
        3. 若无 → 新建一条提交记录

    安全说明：
        student_id 由 FastAPI 从 JWT Token 中解析出来，
        在 Agent 层面作为安全上下文硬性注入，绝不由大模型或前端提供
    """
    # 查询是否存在已有记录
    existing = get_submission(db, student_id, assignment_id)

    if existing:
        # ---- 覆盖更新 ----
        existing.file_path = file_path
        existing.submitted_at = datetime.now(timezone.utc)
        existing.status = "submitted"

        db.commit()
        db.refresh(existing)
        return existing, False  # is_new = False（覆盖）
    else:
        # ---- 新建记录 ----
        new_submission = Submission(
            student_id=student_id,
            assignment_id=assignment_id,
            file_path=file_path,
            submitted_at=datetime.now(timezone.utc),
            status="submitted",
        )

        db.add(new_submission)
        db.commit()
        db.refresh(new_submission)
        return new_submission, True  # is_new = True（新建）


# ==================== AI Agent 专用查询 ====================

def check_student_submission_status(
    db: Session,
    student_id: int,
    keyword: str,
) -> List[dict]:
    """
    检查学生对某作业的提交状态（AI Agent 工具专用）

    参数：
        db         - 数据库会话
        student_id - 学生 ID（从 JWT Token 安全注入）
        keyword    - 搜索关键词（模糊匹配作业标题或课程名）

    返回：
        匹配作业的提交状态列表 List[dict]，最多返回 5 条，每项包含：
        - course_name: 课程名
        - title: 作业标题
        - has_submitted: 是否已提交
        - submitted_at: 提交时间（已提交时有值）
        - file_name: 提交的文件名（已提交时有值）
        - deadline: 截止时间
        - is_expired: 是否已过期

    使用场景：
        学生问"我操作系统的实验交了没？"，
        Agent 提取"操作系统"或"实验"作为关键词调用此函数

    安全说明：
        查询结果限制为最多 5 条，防止模糊搜索返回超量数据
        撑爆大模型上下文 Token 限制
    """
    # 根据关键词模糊搜索匹配的作业（限制数量，防止 Token 超量）
    search_pattern = f"%{keyword}%"
    assignments = (
        db.query(Assignment)
        .filter(
            (Assignment.title.ilike(search_pattern)) |
            (Assignment.course_name.ilike(search_pattern))
        )
        .order_by(Assignment.deadline.desc())
        .limit(5)
        .all()
    )

    if not assignments:
        return []

    now = datetime.now(timezone.utc)
    result = []

    for assignment in assignments:
        # 查询该学生对该作业的提交记录
        submission = get_submission(db, student_id, assignment.id)

        status_info = {
            "course_name": assignment.course_name,
            "title": assignment.title,
            "deadline": assignment.deadline.strftime("%Y-%m-%d %H:%M"),
            "is_expired": now > assignment.deadline,
            "has_submitted": submission is not None,
            "submitted_at": None,
            "file_name": None,
        }

        if submission:
            status_info["submitted_at"] = submission.submitted_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            # 从文件路径中提取文件名
            import os
            status_info["file_name"] = os.path.basename(submission.file_path)

        result.append(status_info)

    return result
