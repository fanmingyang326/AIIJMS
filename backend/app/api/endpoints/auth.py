# ============================================================
# 认证路由模块
# 功能：处理用户登录和密码修改
# 接口：
#   POST /api/auth/login    - 用户登录，返回 JWT Token
#   PUT  /api/auth/password  - 修改密码（需登录）
# 安全说明：
#   - 登录成功后返回 JWT Token，Token 载荷包含 id 和 role
#   - 修改密码时需验证旧密码，防止未授权修改
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import (
    create_access_token,
    verify_password,
    get_current_user,
)
from backend.app.models.user import User
from backend.app.schemas.user import (
    UserLogin,
    TokenResponse,
    UserInfo,
    PasswordChange,
)
from backend.app.crud.crud_user import (
    authenticate_user,
    update_user_password,
)

# 创建认证路由器，设置路由前缀和标签
router = APIRouter(prefix="/auth", tags=["认证模块"])


# ==================== 用户登录 ====================

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description=(
        "教师和学生统一登录接口。\n\n"
        "- 教师使用工号 + 密码登录\n"
        "- 学生使用学号 + 密码登录\n"
        "- 登录成功返回 JWT Token 和用户基本信息\n"
        "- Token 有效期默认 24 小时"
    ),
)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db),
):
    """
    用户登录接口

    处理流程：
        1. 接收 username 和 password
        2. 调用 authenticate_user 验证身份（查用户 → 检查激活 → 验密码）
        3. 验证通过 → 生成 JWT Token（载荷含 id, role）
        4. 返回 Token 和用户基本信息

    错误响应：
        401 - 用户名或密码错误 / 账号已被停用
    """
    # 调用 CRUD 层的认证函数
    user = authenticate_user(db, login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误，或账号已被停用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 获取角色字符串值（兼容 Enum 类型）
    role_value = user.role.value if hasattr(user.role, 'value') else user.role

    # 生成 JWT Token
    access_token = create_access_token(
        user_id=user.id,
        role=role_value,
    )

    # 构造用户信息
    user_info = UserInfo(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=role_value,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_info,
    )


# ==================== 修改密码 ====================

@router.post(
    "/change-password",
    summary="修改密码",
    description=(
        "已登录用户修改密码。\n\n"
        "- 需要提供旧密码和新密码\n"
        "- 旧密码验证通过后才能修改\n"
        "- 新密码至少 6 位\n"
        "- 教师和学生均可使用此接口"
    ),
)
def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    修改密码接口

    处理流程：
        1. 从 JWT Token 解析当前用户（get_current_user 依赖注入）
        2. 验证旧密码是否正确
        3. 旧密码验证通过 → 将新密码哈希后写入数据库
        4. 返回成功提示

    安全说明：
        - 必须携带有效的 JWT Token
        - 必须验证旧密码，防止 Token 泄露后被恶意修改
        - 新密码在 CRUD 层自动进行 bcrypt 哈希处理

    错误响应：
        400 - 旧密码验证失败
        401 - Token 无效或已过期
    """
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码验证失败，请检查后重试",
        )

    # 更新密码
    success = update_user_password(
        db=db,
        user_id=current_user.id,
        new_password=password_data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败，请稍后重试",
        )

    return {"message": "密码修改成功"}
