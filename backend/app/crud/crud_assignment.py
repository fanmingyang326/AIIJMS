# ============================================================
# 作业 CRUD 操作层
# 功能：封装所有与作业表 (assignments) 相关的数据库操作
# 包含：
#   - 作业的创建、查询、更新、删除
#   - 学生端作业列表（含提交状态动态计算 + 专业/学习类型过滤）
#   - 教师端：查看某学生的作业完成情况
#   - 教师端：查看某作业的提交统计（含未交名单）
#   - AI Agent 专用：根据关键词搜索作业、查询未交作业
# ============================================================

import json
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.app.models.assignment import Assignment
from backend.app.models.submission import Submission
from backend.app.models.user import User, UserRole
from backend.app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentListItem,
)


# ==================== 内部工具函数 ====================

def _is_assignment_visible(
    target_majors_json: Optional[str],
    target_is_part_time: Optional[bool],
    student_major: Optional[str],
    student_is_part_time: Optional[bool],
) -> bool:
    """
    判断某个作业对某个学生是否可见

    参数：
        target_majors_json  - 作业的目标专业（数据库中的 JSON 字符串）
        target_is_part_time - 作业的目标学习类型（None=全部/False=全日制/True=非全日制）
        student_major       - 学生的专业名称
        student_is_part_time- 学生是否为非全日制

    返回：
        True - 该学生可以看到这个作业
        False - 该学生看不到这个作业

    过滤规则：
        专业过滤：
            - target_majors 为 None 或空列表 → 面向所有专业
            - 学生专业在 target_majors 中 → 可见
            - 学生没有设置专业 → 只能看到面向所有专业的作业

        学习类型过滤：
            - target_is_part_time 为 None → 面向全部学生
            - target_is_part_time == student_is_part_time → 可见

        两个条件必须同时满足才可见。
    """
    # ---- 专业过滤 ----
    major_visible = True
    if target_majors_json:
        try:
            majors_list = json.loads(target_majors_json)
        except (json.JSONDecodeError, TypeError):
            majors_list = []

        if majors_list:
            # 有专业限制
            if not student_major:
                # 学生没设置专业 → 看不到有专业限制的作业
                major_visible = False
            elif student_major not in majors_list:
                major_visible = False

    # ---- 学习类型过滤 ----
    type_visible = True
    if target_is_part_time is not None:
        # 作业指定了学习类型
        if student_is_part_time is None:
            # 学生没有设置学习类型信息 → 只能看到不限类型的作业
            type_visible = False
        elif target_is_part_time != student_is_part_time:
            type_visible = False

    # 两个条件必须同时满足
    return major_visible and type_visible


# ==================== 教师端：作业 CRUD ====================

def create_assignment(
    db: Session,
    assignment_data: AssignmentCreate,
    teacher_id: int,
) -> Assignment:
    """
    教师发布新作业

    参数：
        db              - 数据库会话
        assignment_data - 作业创建数据（Pydantic 模型）
        teacher_id      - 发布教师的用户 ID（从 JWT Token 中解析）

    返回：
        新创建的 Assignment 对象

    说明：
        - teacher_id 由路由层从 JWT Token 中提取并传入，不由前端提交
        - created_at 由 ORM 模型自动填充当前时间
        - target_majors 为 Python 列表，存入数据库时转为 JSON 字符串
        - target_is_part_time 为可选布尔值，直接存入数据库
    """
    # 将 target_majors 列表转为 JSON 字符串存储
    target_majors_json = None
    if assignment_data.target_majors:
        target_majors_json = json.dumps(
            assignment_data.target_majors, ensure_ascii=False
        )

    new_assignment = Assignment(
        course_name=assignment_data.course_name,
        title=assignment_data.title,
        description=assignment_data.description,
        deadline=assignment_data.deadline,
        allowed_extensions=assignment_data.allowed_extensions,
        target_majors=target_majors_json,
        target_is_part_time=assignment_data.target_is_part_time,
        teacher_id=teacher_id,
    )

    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)

    return new_assignment


def get_all_assignments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Assignment]:
    """
    查询所有作业列表（教师端使用）

    参数：
        db    - 数据库会话
        skip  - 分页偏移量
        limit - 每页数量

    返回：
        作业列表 List[Assignment]，按创建时间倒序
    """
    return (
        db.query(Assignment)
        .order_by(Assignment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_assignment_by_id(
    db: Session,
    assignment_id: int,
) -> Optional[Assignment]:
    """
    根据作业 ID 查询单个作业

    参数：
        db            - 数据库会话
        assignment_id - 作业 ID

    返回：
        Assignment 对象，不存在则返回 None
    """
    return db.query(Assignment).filter(Assignment.id == assignment_id).first()


def update_assignment(
    db: Session,
    assignment_id: int,
    update_data: AssignmentUpdate,
) -> Optional[Assignment]:
    """
    更新作业信息

    参数：
        db            - 数据库会话
        assignment_id - 要更新的作业 ID
        update_data   - 更新数据（Pydantic 模型，部分更新）

    返回：
        更新后的 Assignment 对象，不存在则返回 None

    说明：
        - target_majors 需要特殊处理：从列表转为 JSON 字符串
        - target_is_part_time 直接赋值即可（普通布尔值或 None）
        - 传空列表 [] 的 target_majors 表示改为面向所有专业（存为 None）
    """
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        return None

    # 仅更新请求中明确传递的字段
    update_dict = update_data.model_dump(exclude_unset=True)

    # 特殊处理 target_majors：列表 → JSON 字符串
    if "target_majors" in update_dict:
        majors = update_dict.pop("target_majors")
        if majors:
            assignment.target_majors = json.dumps(majors, ensure_ascii=False)
        else:
            # 传入空列表或 None → 清除目标专业限制
            assignment.target_majors = None

    # 其余字段（包括 target_is_part_time）直接赋值
    for field, value in update_dict.items():
        setattr(assignment, field, value)

    db.commit()
    db.refresh(assignment)

    return assignment


def delete_assignment(db: Session, assignment_id: int) -> bool:
    """
    删除作业

    参数：
        db            - 数据库会话
        assignment_id - 要删除的作业 ID

    返回：
        True - 删除成功，False - 作业不存在

    注意：
        - 由于 ORM 模型设置了 cascade="all, delete-orphan"，
          删除作业时会自动级联删除所有相关提交记录
    """
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        return False

    db.delete(assignment)
    db.commit()
    return True


# ==================== 学生端：作业列表（含提交状态 + 过滤） ====================

def get_student_assignments_with_status(
    db: Session,
    student_id: int,
    student_major: Optional[str] = None,
    student_is_part_time: Optional[bool] = None,
) -> List[AssignmentListItem]:
    """
    查询学生端作业列表，包含每个作业的提交状态

    参数：
        db                  - 数据库会话
        student_id          - 当前登录学生的 ID（从 JWT Token 解析）
        student_major       - 当前学生的专业（用于按专业过滤作业）
        student_is_part_time- 当前学生是否为非全日制（用于按学习类型过滤）

    返回：
        List[AssignmentListItem]，每项包含作业信息和动态计算的 status 字段

    状态计算逻辑：
        - "已交"   → 该学生对该作业存在提交记录
        - "未交"   → 该学生未提交 且 截止时间尚未到来
        - "已截止" → 该学生未提交 且 截止时间已过

    可见性过滤逻辑：
        - 专业过滤：target_majors 为空则所有人可见，否则仅匹配的专业可见
        - 学习类型过滤：target_is_part_time 为 None 则所有人可见，否则仅匹配的类型可见
        - 两个条件同时满足才可见

    说明：
        - 使用 outerjoin 一次性查出作业列表及该学生的提交记录，
          杜绝 N+1 查询问题
        - 按截止时间升序排列（最紧急的在前）
    """
    # 使用 outerjoin 将 Assignment 和 Submission 联合查询
    # ON 条件必须同时匹配 assignment_id 和 student_id，
    # 确保只关联当前学生的提交记录
    rows = (
        db.query(Assignment, Submission)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == student_id,
            ),
        )
        .order_by(Assignment.deadline.asc())
        .all()
    )

    result = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for assignment, submission in rows:
        # 可见性过滤：检查专业和学习类型是否匹配
        if not _is_assignment_visible(
            target_majors_json=assignment.target_majors,
            target_is_part_time=assignment.target_is_part_time,
            student_major=student_major,
            student_is_part_time=student_is_part_time,
        ):
            continue

        # 动态计算提交状态
        if submission:
            status = "已交"
            submitted_at = submission.submitted_at
        elif now > assignment.deadline:
            status = "已截止"
            submitted_at = None
        else:
            status = "未交"
            submitted_at = None

        result.append(AssignmentListItem(
            id=assignment.id,
            course_name=assignment.course_name,
            title=assignment.title,
            description=assignment.description,
            deadline=assignment.deadline,
            allowed_extensions=assignment.allowed_extensions,
            created_at=assignment.created_at,
            status=status,
            submitted_at=submitted_at,
        ))

    return result


# ==================== 教师端：查看某学生的作业完成情况 ====================

def get_teacher_view_student_assignments(
    db: Session,
    student_id: int,
    student_major: Optional[str] = None,
    student_is_part_time: Optional[bool] = None,
) -> List[dict]:
    """
    教师端：查看某个学生的作业完成情况

    参数：
        db                  - 数据库会话
        student_id          - 目标学生的 ID
        student_major       - 该学生的专业
        student_is_part_time- 该学生是否为非全日制

    返回：
        作业列表 List[dict]，每项包含作业信息和提交状态

    说明：
        复用 _is_assignment_visible() 函数进行可见性过滤，
        确保只返回该学生应该看到的作业。
    """
    rows = (
        db.query(Assignment, Submission)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == student_id,
            ),
        )
        .order_by(Assignment.deadline.asc())
        .all()
    )

    result = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for assignment, submission in rows:
        # 可见性过滤
        if not _is_assignment_visible(
            target_majors_json=assignment.target_majors,
            target_is_part_time=assignment.target_is_part_time,
            student_major=student_major,
            student_is_part_time=student_is_part_time,
        ):
            continue

        # 动态计算提交状态
        if submission:
            status = "已交"
            submitted_at = submission.submitted_at.strftime("%Y-%m-%d %H:%M") if submission.submitted_at else None
        elif now > assignment.deadline:
            status = "已截止"
            submitted_at = None
        else:
            status = "未交"
            submitted_at = None

        result.append({
            "id": assignment.id,
            "course_name": assignment.course_name,
            "title": assignment.title,
            "deadline": assignment.deadline.strftime("%Y-%m-%d %H:%M"),
            "status": status,
            "submitted_at": submitted_at,
        })

    return result


# ==================== 教师端：某作业的提交统计（含未交名单） ====================

def get_assignment_submit_stats(
    db: Session,
    assignment_id: int,
) -> Optional[dict]:
    """
    教师端：查看某作业的提交统计，包含已交和未交学生名单

    参数：
        db            - 数据库会话
        assignment_id - 作业 ID

    返回：
        统计字典，包含：
        - total_should_submit: 应交人数
        - submitted_count: 已交人数
        - not_submitted_count: 未交人数
        - submitted_students: 已交学生列表
        - not_submitted_students: 未交学生列表
        返回 None 表示作业不存在

    逻辑：
        1. 读取作业的 target_majors 和 target_is_part_time
        2. 查出所有 role=student 且 is_active=True 的学生
        3. 使用 _is_assignment_visible 过滤出「应交学生集合」
        4. 查出该作业的所有提交记录 = 「已交集合」
        5. 应交集合 - 已交集合 = 「未交集合」
    """
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        return None

    # 查出所有活跃学生
    all_students = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.is_active == True,
        )
        .all()
    )

    # 根据作业的目标专业和学习类型过滤出「应交学生集合」
    should_submit_students = []
    for student in all_students:
        if _is_assignment_visible(
            target_majors_json=assignment.target_majors,
            target_is_part_time=assignment.target_is_part_time,
            student_major=student.major,
            student_is_part_time=student.is_part_time,
        ):
            should_submit_students.append(student)

    # 查出该作业的所有提交记录
    submissions = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .all()
    )

    # 构建已提交学生 ID 集合及提交时间映射
    submitted_student_ids = set()
    submitted_at_map = {}
    for sub in submissions:
        submitted_student_ids.add(sub.student_id)
        submitted_at_map[sub.student_id] = sub.submitted_at

    # 分类
    submitted_students = []
    not_submitted_students = []

    for student in should_submit_students:
        student_info = {
            "student_id": student.id,
            "username": student.username,
            "full_name": student.full_name,
            "major": student.major,
            "is_part_time": student.is_part_time,
        }
        if student.id in submitted_student_ids:
            sub_time = submitted_at_map.get(student.id)
            student_info["submitted_at"] = (
                sub_time.strftime("%Y-%m-%d %H:%M") if sub_time else None
            )
            submitted_students.append(student_info)
        else:
            not_submitted_students.append(student_info)

    return {
        "total_should_submit": len(should_submit_students),
        "submitted_count": len(submitted_students),
        "not_submitted_count": len(not_submitted_students),
        "submitted_students": submitted_students,
        "not_submitted_students": not_submitted_students,
    }


# ==================== AI Agent 专用查询 ====================

def search_assignment_by_keyword(
    db: Session,
    keyword: str,
) -> List[Assignment]:
    """
    根据关键词模糊搜索作业（按标题或课程名匹配）

    参数：
        db      - 数据库会话
        keyword - 搜索关键词（模糊匹配作业标题或课程名）

    返回：
        匹配的作业列表 List[Assignment]

    使用场景：
        AI Agent 的 get_assignment_details 工具调用此函数，
        当学生提问"数据库那个作业要交什么格式的？"时，
        Agent 使用"数据库"作为关键词搜索。
    """
    search_pattern = f"%{keyword}%"
    return (
        db.query(Assignment)
        .filter(
            (Assignment.title.ilike(search_pattern)) |
            (Assignment.course_name.ilike(search_pattern))
        )
        .order_by(Assignment.deadline.asc())
        .all()
    )


def get_pending_assignments_for_student(
    db: Session,
    student_id: int,
    student_major: Optional[str] = None,
    student_is_part_time: Optional[bool] = None,
) -> List[dict]:
    """
    查询学生所有未过期且未提交的作业

    参数：
        db                  - 数据库会话
        student_id          - 学生 ID（从 JWT Token 安全注入）
        student_major       - 学生专业（用于按专业过滤作业）
        student_is_part_time- 学生是否为非全日制（用于按学习类型过滤）

    返回：
        未交作业信息列表 List[dict]，每项包含：
        - course_name: 课程名
        - title: 作业标题
        - deadline: 截止时间
        - remaining: 距截止剩余描述

    使用场景：
        AI Agent 的 get_pending_assignments 工具调用此函数，
        用于回答"我还有哪些作业没交？"
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 使用 outerjoin 一次性查出未过期作业及该学生的提交记录
    rows = (
        db.query(Assignment, Submission)
        .outerjoin(
            Submission,
            and_(
                Submission.assignment_id == Assignment.id,
                Submission.student_id == student_id,
            ),
        )
        .filter(Assignment.deadline > now)
        .order_by(Assignment.deadline.asc())
        .all()
    )

    pending_list = []

    for assignment, submission in rows:
        # 仅返回未提交的作业
        if submission is not None:
            continue

        # 可见性过滤：检查专业和学习类型是否匹配
        if not _is_assignment_visible(
            target_majors_json=assignment.target_majors,
            target_is_part_time=assignment.target_is_part_time,
            student_major=student_major,
            student_is_part_time=student_is_part_time,
        ):
            continue

        # 计算剩余时间描述
        remaining = assignment.deadline - now
        days = remaining.days
        hours = remaining.seconds // 3600

        if days > 0:
            remaining_desc = f"还剩 {days} 天 {hours} 小时"
        elif hours > 0:
            remaining_desc = f"还剩 {hours} 小时"
        else:
            minutes = remaining.seconds // 60
            remaining_desc = f"还剩 {minutes} 分钟（紧急！）"

        pending_list.append({
            "course_name": assignment.course_name,
            "title": assignment.title,
            "deadline": assignment.deadline.strftime("%Y-%m-%d %H:%M"),
            "remaining": remaining_desc,
            "allowed_extensions": assignment.allowed_extensions,
        })

    return pending_list
