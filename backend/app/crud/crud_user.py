# ============================================================
# 用户 CRUD 操作层
# 功能：封装所有与用户表 (users) 相关的数据库操作
# 包含：
#   - 用户查询（按 ID / 用户名）
#   - 学生列表查询（分页 + 筛选）
#   - 学生录入（教师创建学生账号）
#   - 学生批量导入（从 Excel 批量创建）
#   - 学生信息更新
#   - 学生账号删除
#   - 密码修改
#   - 登录身份验证
#   - 获取所有专业列表（用于发布作业时选择目标专业）
# ============================================================

from typing import Optional, List

from sqlalchemy.orm import Session

from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserUpdate
from backend.app.core.security import hash_password, verify_password
from backend.app.core.config import settings


# ==================== 查询操作 ====================

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    根据用户 ID 查询用户
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    根据用户名（学号/工号）查询用户
    """
    return db.query(User).filter(User.username == username).first()


def get_all_students(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
) -> List[User]:
    """
    查询所有学生列表（支持分页和关键词搜索）

    说明：
        - 仅返回 role 为 student 的用户
        - 按创建时间倒序排列
        - 支持对学号和姓名的模糊搜索
    """
    query = db.query(User).filter(User.role == UserRole.STUDENT)

    if keyword:
        search_pattern = f"%{keyword}%"
        query = query.filter(
            (User.username.ilike(search_pattern)) |
            (User.full_name.ilike(search_pattern))
        )

    return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()


def get_all_majors(db: Session) -> List[str]:
    """
    获取所有学生的不重复专业列表

    返回：
        专业名称列表 List[str]，去重且排除 NULL 值

    使用场景：
        教师发布作业时，前端下拉框展示可选的目标专业列表
    """
    rows = (
        db.query(User.major)
        .filter(
            User.role == UserRole.STUDENT,
            User.major.isnot(None),
            User.major != "",
        )
        .distinct()
        .order_by(User.major)
        .all()
    )
    return [row[0] for row in rows]


# ==================== 创建操作 ====================

def create_student(db: Session, student_data: UserCreate) -> User:
    """
    教师录入新学生

    注意：
        - 调用前应先检查 username 是否已存在（在路由层处理）
        - 默认密码由 config.settings.DEFAULT_STUDENT_PASSWORD 控制
    """
    password_hash = hash_password(settings.DEFAULT_STUDENT_PASSWORD)

    new_student = User(
        username=student_data.username,
        password_hash=password_hash,
        full_name=student_data.full_name,
        role=UserRole.STUDENT,
        is_active=True,
        major=student_data.major,
        is_part_time=student_data.is_part_time,
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return new_student


def batch_create_students(
    db: Session,
    students_data: List[dict],
) -> dict:
    """
    批量创建学生账号（从 Excel 导入）

    参数：
        db             - 数据库会话
        students_data  - 学生数据列表，每项为 dict，包含：
                         row (行号), username (学号), full_name (姓名),
                         major (专业), is_part_time (是否非全日制)

    返回：
        导入结果字典：
        {
            "success_count": 成功导入的数量,
            "fail_count": 失败的数量,
            "fail_details": [
                {"row": 行号, "username": 学号, "reason": 失败原因},
                ...
            ]
        }

    说明：
        - 逐条检查学号是否已存在（数据库中 + 本批次中），已存在的跳过并记录
        - 所有新学生使用系统默认密码
        - 使用批量提交（一次 commit），提升性能
    """
    success_count = 0
    fail_details = []
    password_hash = hash_password(settings.DEFAULT_STUDENT_PASSWORD)

    new_students = []

    for item in students_data:
        row_num = item.get("row", "?")
        username = item.get("username", "").strip()
        full_name = item.get("full_name", "").strip()
        major = item.get("major", "").strip() or None
        is_part_time = item.get("is_part_time", False)

        # 校验必填字段
        if not username:
            fail_details.append({
                "row": row_num,
                "username": username or "(空)",
                "reason": "学号不能为空",
            })
            continue

        if not full_name:
            fail_details.append({
                "row": row_num,
                "username": username,
                "reason": "姓名不能为空",
            })
            continue

        # 检查学号是否已存在（数据库中）
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            fail_details.append({
                "row": row_num,
                "username": username,
                "reason": "学号已存在，跳过",
            })
            continue

        # 检查本批次内是否有重复学号
        if any(s.username == username for s in new_students):
            fail_details.append({
                "row": row_num,
                "username": username,
                "reason": "Excel 中学号重复",
            })
            continue

        # 创建新学生对象
        new_student = User(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            role=UserRole.STUDENT,
            is_active=True,
            major=major,
            is_part_time=is_part_time,
        )
        new_students.append(new_student)
        success_count += 1

    # 批量写入数据库
    if new_students:
        db.add_all(new_students)
        db.commit()

    return {
        "success_count": success_count,
        "fail_count": len(fail_details),
        "fail_details": fail_details,
    }


# ==================== 更新操作 ====================

def update_student(
    db: Session,
    student_id: int,
    update_data: UserUpdate,
) -> Optional[User]:
    """
    更新学生信息（部分更新 / PATCH 语义）
    """
    student = db.query(User).filter(
        User.id == student_id,
        User.role == UserRole.STUDENT,
    ).first()

    if not student:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)

    return student


def update_user_password(
    db: Session,
    user_id: int,
    new_password: str,
) -> bool:
    """
    修改用户密码

    说明：
        - 旧密码的验证应在路由层完成
        - 此函数仅负责将新密码哈希后写入数据库
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False

    user.password_hash = hash_password(new_password)
    db.commit()
    return True


# ==================== 删除操作 ====================

def delete_student(db: Session, student_id: int) -> bool:
    """
    删除学生账号（级联删除提交记录，仅允许删除 student 角色）
    """
    student = db.query(User).filter(
        User.id == student_id,
        User.role == UserRole.STUDENT,
    ).first()

    if not student:
        return False

    db.delete(student)
    db.commit()
    return True


# ==================== 认证操作 ====================

def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> Optional[User]:
    """
    验证用户登录凭据

    验证流程：
        1. 根据用户名查询用户
        2. 检查用户是否存在
        3. 检查账号是否启用
        4. 验证密码哈希是否匹配
    """
    user = get_user_by_username(db, username)

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
