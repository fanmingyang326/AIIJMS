# ============================================================
# 文件服务模块
# 功能：处理作业提交相关的所有文件操作
# 包含：
#   1. 文件后缀校验 —— 检查上传文件是否在允许的后缀范围内
#   2. 截止时间校验 —— 检查作业是否已过截止时间
#   3. 文件强制重命名 —— 按规则 {学号}_{姓名}_{作业标题}.{后缀} 重命名
#   4. 文件保存到本地 —— 按 assignment_id 划分子目录存储
#   5. 旧文件删除 —— 覆盖重交时删除旧文件（安全时序：先存新再删旧）
#   6. ZIP 打包下载 —— 将某作业所有提交文件打包为磁盘临时 ZIP 文件
# ============================================================

import os
import re
import zipfile
import tempfile
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.assignment import Assignment
from backend.app.models.submission import Submission
from backend.app.models.user import User


# ==================== 1. 文件后缀校验 ====================

def validate_file_extension(
    filename: str,
    allowed_extensions: str,
) -> str:
    """
    校验上传文件的后缀是否在允许范围内

    参数：
        filename           - 上传文件的原始文件名（如 "report.pdf"）
        allowed_extensions - 允许的后缀字符串，逗号分隔（如 ".pdf,.zip,.docx"）

    返回：
        文件后缀（包含点号，如 ".pdf"）

    异常：
        HTTPException 400 - 文件后缀不在允许范围内

    示例：
        >>> validate_file_extension("report.pdf", ".pdf,.zip")
        ".pdf"
        >>> validate_file_extension("code.py", ".pdf,.zip")
        HTTPException: 文件格式不允许
    """
    # 提取文件后缀（转小写以忽略大小写）
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传的文件缺少文件后缀名",
        )

    # 解析允许的后缀列表（去空格、转小写）
    allowed_list = [
        e.strip().lower()
        for e in allowed_extensions.split(",")
        if e.strip()
    ]

    if ext not in allowed_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"文件格式不允许：当前文件后缀为 '{ext}'，"
                f"该作业仅允许以下格式：{', '.join(allowed_list)}"
            ),
        )

    return ext


# ==================== 2. 截止时间校验 ====================

def validate_deadline(deadline: datetime) -> None:
    """
    校验作业是否已过截止时间

    参数：
        deadline - 作业的截止时间

    异常：
        HTTPException 400 - 已过截止时间，拒绝提交

    说明：
        比较当前 UTC 时间与截止时间，
        若当前时间已超过截止时间则抛出异常
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if now > deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"提交失败：该作业已于 "
                f"{deadline.strftime('%Y-%m-%d %H:%M')} 截止，"
                f"当前时间已超过截止时间。"
            ),
        )


# ==================== 3. 文件强制重命名 ====================

def generate_safe_filename(
    username: str,
    full_name: str,
    title: str,
    extension: str,
) -> str:
    """
    按系统规范生成安全的文件名

    命名规则：{学号}_{姓名}_{作业标题}.{后缀}

    参数：
        username  - 学生学号（如 "2024001"）
        full_name - 学生姓名（如 "张三"）
        title     - 作业标题（如 "第三次实验报告"）
        extension - 文件后缀（如 ".pdf"）

    返回：
        规范化的文件名（如 "2024001_张三_第三次实验报告.pdf"）

    安全处理：
        - 移除文件名中的特殊字符（仅保留中文、字母、数字、下划线、横线）
        - 确保后缀以点号开头
    """
    # 安全字符过滤函数：仅保留中文、字母、数字、下划线、横线
    def sanitize(text: str) -> str:
        return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_\-]', '', text)

    safe_username = sanitize(username)
    safe_name = sanitize(full_name)
    safe_title = sanitize(title)

    # 确保后缀以点号开头
    if not extension.startswith('.'):
        extension = f'.{extension}'

    return f"{safe_username}_{safe_name}_{safe_title}{extension}"


# ==================== 4. 文件保存到本地 ====================

async def save_upload_file(
    file: UploadFile,
    assignment_id: int,
    target_filename: str,
) -> str:
    """
    将上传文件保存到本地存储

    参数：
        file            - FastAPI 的 UploadFile 对象
        assignment_id   - 作业 ID（用于划分子目录）
        target_filename - 目标文件名（经过 generate_safe_filename 生成）

    返回：
        文件的完整存储路径（相对于项目根目录）

    存储规则：
        uploads/{assignment_id}/{学号}_{姓名}_{作业标题}.{后缀}

    示例：
        uploads/3/2024001_张三_第三次实验报告.pdf

    说明：
        - 自动创建目标目录（如果不存在）
        - 使用二进制写入模式，支持任意文件类型
        - 分块读取上传文件，避免大文件占用过多内存
    """
    # 构建目标目录：uploads/{assignment_id}/
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(assignment_id))

    # 自动创建目录（递归创建，exist_ok 避免已存在时报错）
    os.makedirs(upload_dir, exist_ok=True)

    # 构建完整文件路径
    file_path = os.path.join(upload_dir, target_filename)

    # 分块读写文件（每次读取 1MB，避免大文件内存溢出）
    chunk_size = 1024 * 1024  # 1MB

    with open(file_path, "wb") as buffer:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            buffer.write(chunk)

    return file_path


# ==================== 5. 旧文件删除 ====================

def delete_old_file(file_path: str) -> bool:
    """
    删除服务器上的旧文件（覆盖重交时使用）

    参数：
        file_path - 要删除的文件路径

    返回：
        True  - 文件删除成功
        False - 文件不存在或删除失败

    说明：
        - 覆盖重交时，新文件保存成功后才调用此函数删除旧文件
        - 即使删除失败也不阻断提交流程（仅记录日志）
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except OSError as e:
        # 删除失败不应阻断业务流程，仅记录错误
        print(f"⚠️ 删除旧文件失败：{file_path}，错误：{e}")
        return False


# ==================== 6. ZIP 打包下载 ====================

def create_zip_archive(
    db: Session,
    assignment_id: int,
) -> tuple[str, str]:
    """
    将某作业下所有已提交的文件打包为磁盘临时 ZIP 文件

    参数：
        db            - 数据库会话
        assignment_id - 作业 ID

    返回：
        元组 (temp_zip_path, zip_filename)：
        - temp_zip_path: 临时 ZIP 文件在磁盘上的路径
        - zip_filename:  建议的下载文件名（如 "数据库原理_第三次实验报告_提交文件.zip"）

    异常：
        HTTPException 404 - 作业不存在
        HTTPException 404 - 该作业暂无任何提交文件

    处理流程：
        1. 查询作业信息（获取课程名和标题，用于 ZIP 文件名）
        2. 查询该作业的所有提交记录
        3. 使用 tempfile.NamedTemporaryFile 在磁盘上创建临时 ZIP 文件
        4. 逐一读取实际文件并写入 ZIP
        5. 返回临时文件路径供 FileResponse 使用

    说明：
        - 使用磁盘临时文件避免大文件导致内存 OOM
        - 临时文件由调用方（路由层）通过 BackgroundTask 在响应完成后清理
        - ZIP 内的文件名保持重命名后的规范格式
        - 跳过本地不存在的文件（可能被手动删除）
    """
    # 查询作业信息
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="作业不存在",
        )

    # 查询该作业的所有提交记录
    submissions = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .all()
    )

    if not submissions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该作业暂无任何提交文件",
        )

    # 创建磁盘临时文件（delete=False 保证关闭后文件仍存在，由调用方负责清理）
    tmp_file = tempfile.NamedTemporaryFile(
        suffix=".zip",
        delete=False,
    )
    temp_zip_path = tmp_file.name

    try:
        with zipfile.ZipFile(tmp_file, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            added_count = 0

            for submission in submissions:
                # 检查文件是否实际存在
                if not os.path.exists(submission.file_path):
                    print(
                        f"⚠️ 文件不存在，跳过：{submission.file_path}"
                        f"（学生ID: {submission.student_id}）"
                    )
                    continue

                # 提取文件名（使用重命名后的文件名）
                file_name = os.path.basename(submission.file_path)

                # 将文件写入 ZIP 包
                zip_file.write(submission.file_path, file_name)
                added_count += 1

        if added_count == 0:
            # 没有有效文件，清理临时文件后抛异常
            os.remove(temp_zip_path)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="所有提交文件在服务器上均不存在，无法打包",
            )
    except HTTPException:
        raise
    except Exception:
        # 出现意外异常时清理临时文件
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)
        raise

    # 生成建议的下载文件名
    zip_filename = (
        f"{assignment.course_name}_{assignment.title}_提交文件.zip"
    )

    return temp_zip_path, zip_filename


# ==================== 完整提交流程（组合函数） ====================

async def process_file_submission(
    db: Session,
    file: UploadFile,
    assignment: Assignment,
    student: User,
) -> str:
    """
    处理文件提交的完整流程（供路由层调用的组合函数）

    参数：
        db         - 数据库会话
        file       - 上传的文件
        assignment - 作业 ORM 对象
        student    - 当前学生 ORM 对象（从 JWT Token 解析）

    返回：
        文件在服务器上的存储路径

    完整流程：
        1. 校验截止时间 → 超时拒绝
        2. 校验文件后缀 → 不符拒绝
        3. 按规范重命名文件（使用作业标题 title）
        4. 保存新文件到本地（使用时间戳后缀防冲突）
        5. 确认保存成功后，再删除旧文件（安全时序）

    安全要点：
        - student 参数从 JWT Token 解析，绝不接受前端传递
        - 强校验截止时间和文件后缀，确保业务规则不被绕过
        - 先存新文件、再删旧文件，避免保存失败时数据丢失
    """
    # ---- 第 1 步：校验截止时间 ----
    validate_deadline(assignment.deadline)

    # ---- 第 2 步：校验文件后缀 ----
    extension = validate_file_extension(
        filename=file.filename or "",
        allowed_extensions=assignment.allowed_extensions,
    )

    # ---- 第 3 步：查询已有提交记录（用于后续删除旧文件） ----
    from backend.app.crud.crud_submission import get_submission
    existing_submission = get_submission(
        db, student.id, assignment.id
    )
    old_file_path = None
    if existing_submission and existing_submission.file_path:
        old_file_path = existing_submission.file_path

    # ---- 第 4 步：按规范生成新文件名（使用作业标题 title） ----
    # 命名规则：{学号}_{姓名}_{作业标题}.{后缀}
    target_filename = generate_safe_filename(
        username=student.username,
        full_name=student.full_name,
        title=assignment.title,       # ✅ 修复：使用 title 而非 course_name
        extension=extension,
    )

    # ---- 第 5 步：保存新文件到本地 ----
    # 如果旧文件与新文件同名（同一学生重交同一作业），
    # 先添加时间戳后缀避免写冲突，保存成功后再清理
    if old_file_path and os.path.basename(old_file_path) == target_filename:
        # 使用临时时间戳后缀防止文件名冲突
        timestamp_suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        name_without_ext, ext_part = os.path.splitext(target_filename)
        temp_target_filename = f"{name_without_ext}_{timestamp_suffix}{ext_part}"
    else:
        temp_target_filename = target_filename

    file_path = await save_upload_file(
        file=file,
        assignment_id=assignment.id,
        target_filename=temp_target_filename,
    )

    # ---- 第 6 步：新文件保存成功后，删除旧文件 ----
    if old_file_path:
        delete_old_file(old_file_path)

    # 如果使用了临时时间戳后缀，重命名为最终文件名
    if temp_target_filename != target_filename:
        final_path = os.path.join(
            os.path.dirname(file_path),
            target_filename,
        )
        try:
            os.rename(file_path, final_path)
            file_path = final_path
        except OSError as e:
            # 重命名失败不阻断流程，使用带时间戳的文件名
            print(f"⚠️ 文件重命名失败：{e}，使用带时间戳的文件名")

    return file_path
