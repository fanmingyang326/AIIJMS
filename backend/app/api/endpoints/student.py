# ============================================================
# 学生路由模块
# 功能：处理学生端的所有操作
# 接口：
#   GET  /api/student/assignments               - 获取作业列表（含提交状态）
#   POST /api/student/assignments/{id}/submit    - 提交作业文件
# 权限说明：
#   所有接口均使用 require_student 依赖注入，确保仅学生可访问
# 安全重点：
#   文件提交接口绝不接收前端传递的 student_id，
#   必须从 JWT Token 中解析当前学生身份
# ============================================================

from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_student
from backend.app.models.user import User
from backend.app.schemas.assignment import AssignmentListItem
from backend.app.schemas.submission import SubmissionResponse
from backend.app.crud.crud_assignment import (
    get_student_assignments_with_status,
    get_assignment_by_id,
)
from backend.app.crud.crud_submission import create_or_update_submission
from backend.app.services.file_service import process_file_submission

# 创建学生路由器
router = APIRouter(prefix="/student", tags=["学生模块"])


# ==================== 获取作业列表 ====================

@router.get(
    "/assignments",
    response_model=List[AssignmentListItem],
    summary="获取作业列表（含提交状态）",
    description=(
        "学生端首页 Dashboard 使用此接口渲染作业列表。\n\n"
        "每个作业包含动态计算的提交状态：\n"
        "- **未交** — 未过截止时间且未提交\n"
        "- **已交** — 已成功提交（含提交时间）\n"
        "- **已截止** — 截止时间已过且未提交\n\n"
        "按截止时间升序排列（最紧急的在前）\n\n"
        "**可见性规则**：\n"
        "- 教师发布作业时可设置目标专业和学习类型\n"
        "- 学生只能看到面向自己专业和学习类型的作业\n"
        "- 未设置限制的作业对所有学生可见"
    ),
)
def get_my_assignments(
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    获取当前学生的作业列表

    处理流程：
        1. 通过 require_student 依赖注入验证学生身份，获取 student 对象
        2. 调用 CRUD 层查询所有作业，传入学生的专业和学习类型用于过滤
        3. 对每个可见作业动态计算该学生的提交状态
        4. 返回包含 status 字段的作业列表

    安全说明：
        - student_id、student_major、student_is_part_time 均从 JWT Token 中自动提取
        - 每个学生只能看到自己有权限查看的作业和自己的提交状态
    """
    assignments = get_student_assignments_with_status(
        db=db,
        student_id=student.id,
        student_major=student.major,
        student_is_part_time=student.is_part_time,
    )
    return assignments


# ==================== 提交作业文件 ====================

@router.post(
    "/assignments/{assignment_id}/submit",
    response_model=SubmissionResponse,
    summary="提交作业文件",
    description=(
        "学生上传作业文件。\n\n"
        "**硬性要求**：\n"
        "- 请求体必须是 `multipart/form-data`\n"
        "- 仅包含 `file` 字段，绝不允许传递 student_id\n"
        "- student_id 从 JWT Token 中自动解析\n\n"
        "**提交校验**：\n"
        "- ① 截止时间校验：超时直接拒绝\n"
        "- ② 文件后缀校验：不在允许范围内直接拒绝\n\n"
        "**覆盖重交**：\n"
        "- 同一学生对同一作业只能有一条记录\n"
        "- 在截止前重复提交采取直接覆盖策略\n"
        "- 覆盖旧数据库记录和旧本地文件\n\n"
        "**文件重命名**：\n"
        "- 后端强制重命名为：`{学号}_{姓名}_{课程名}.{后缀}`\n"
        "- 存储路径：`uploads/{assignment_id}/文件名`"
    ),
)
async def submit_assignment(
    assignment_id: int,
    file: UploadFile = File(
        ...,
        description="上传的作业文件（仅此一个字段）",
    ),
    student: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    提交作业文件

    处理流程：
        1. 验证学生身份（从 JWT Token 解析 student_id）
        2. 查询作业是否存在
        3. 调用 file_service 的完整提交流程（process_file_submission）：
           a. 校验截止时间 → 超时抛 400
           b. 校验文件后缀 → 不符抛 400
           c. 检查旧文件并删除（覆盖重交）
           d. 按规范重命名文件
           e. 保存新文件到本地
        4. 调用 CRUD 层创建/更新提交记录（覆盖重交）
        5. 返回提交结果

    路径参数：
        assignment_id - 目标作业 ID

    请求体（multipart/form-data）：
        file - 上传的文件（唯一字段）

    安全重点：
        - student_id 绝不由前端传递，必须从 JWT Token 中解析
        - file 是唯一接受的表单字段
        - 后端进行截止时间和文件后缀的双重强校验

    错误响应：
        400 - 已过截止时间 / 文件后缀不允许
        404 - 作业不存在
        403 - 非学生角色
    """
    # ---- 第 1 步：查询作业是否存在 ----
    assignment = get_assignment_by_id(db=db, assignment_id=assignment_id)

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"作业 ID={assignment_id} 不存在",
        )

    # ---- 第 2 步：调用文件服务完整提交流程 ----
    # 内部依次执行：校验时间 → 校验后缀 → 删旧文件 → 重命名 → 保存新文件
    # student 对象从 JWT Token 解析，安全注入
    file_path = await process_file_submission(
        db=db,
        file=file,
        assignment=assignment,
        student=student,
    )

    # ---- 第 3 步：创建或覆盖数据库提交记录 ----
    # create_or_update_submission 实现覆盖重交逻辑：
    #   - 已有记录 → 更新 file_path 和 submitted_at
    #   - 无记录   → 新建一条
    submission, is_new = create_or_update_submission(
        db=db,
        student_id=student.id,      # ✅ 从 Token 解析，非前端传递
        assignment_id=assignment_id,
        file_path=file_path,
    )

    # ---- 第 4 步：构造响应 ----
    message = "提交成功" if is_new else "已覆盖之前的提交，重新提交成功"

    return SubmissionResponse(
        id=submission.id,
        file_path=submission.file_path,
        submitted_at=submission.submitted_at,
        status=submission.status,
        student_id=submission.student_id,
        assignment_id=submission.assignment_id,
        message=message,
    )
