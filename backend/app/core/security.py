# ============================================================
# 安全工具模块
# 功能：
#   1. 密码哈希与验证（基于 bcrypt / passlib）
#   2. JWT Token 的创建与解析
#   3. FastAPI 依赖注入：从请求中提取并验证当前用户
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.user import User

# -------------------- 密码哈希上下文 --------------------
# 使用 bcrypt 作为密码哈希算法
# deprecated="auto" 表示自动处理旧算法的迁移
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# -------------------- JWT Bearer 认证方案 --------------------
# 从请求头 Authorization: Bearer <token> 中提取 Token
security_scheme = HTTPBearer(auto_error=False)


# ==================== 密码相关函数 ====================

def hash_password(plain_password: str) -> str:
    """
    将明文密码进行 bcrypt 哈希处理

    参数：
        plain_password - 用户输入的明文密码

    返回：
        哈希后的密码字符串，可安全存入数据库
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希密码匹配

    参数：
        plain_password  - 用户输入的明文密码
        hashed_password - 数据库中存储的哈希密码

    返回：
        True  - 密码匹配
        False - 密码不匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


# ==================== JWT Token 相关函数 ====================

def create_access_token(
    user_id: int,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 JWT 访问令牌

    参数：
        user_id       - 用户 ID，写入 Token 的 sub 字段
        role          - 用户角色（student / teacher），写入 Token
        expires_delta - 自定义过期时间增量，默认使用配置中的值

    返回：
        编码后的 JWT Token 字符串

    Token 载荷 (Payload) 结构：
        {
            "sub": "用户ID",    # JWT 标准字段：主题（Subject）
            "id": 用户ID,       # 冗余存储，方便解析
            "role": "角色",     # 用户角色
            "exp": 过期时间戳   # JWT 标准字段：过期时间
        }
    """
    # 计算过期时间
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # 构造 Token 载荷
    to_encode = {
        "sub": str(user_id),   # JWT 规范要求 sub 为字符串
        "id": user_id,         # 整数形式的用户 ID，便于直接使用
        "role": role,          # 角色信息
        "exp": expire,         # 过期时间
    }

    # 使用 HS256 算法签名
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    解析并验证 JWT Token

    参数：
        token - JWT Token 字符串

    返回：
        解码后的 Token 载荷字典

    异常：
        HTTPException 401 - Token 无效或已过期
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== FastAPI 依赖注入函数 ====================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    access_token: Optional[str] = None,
    db: Session = Depends(get_db),
) -> User:
    """
    从请求头或 Query 参数中提取 JWT Token 并解析出当前登录用户

    使用方式（在路由中作为依赖注入）：
        @router.get("/me")
        def get_me(current_user: User = Depends(get_current_user)):
            return current_user

    Token 提取优先级：
        1. Authorization: Bearer <token> 请求头（常规接口）
        2. ?access_token=<token> 查询参数（文件下载等浏览器直接跳转场景）

    流程：
        1. 从 Authorization 头或 Query 参数提取 Token
        2. 解码 Token 获取 user_id
        3. 查询数据库验证用户是否存在且启用
        4. 返回完整的 User ORM 对象

    异常：
        401 - Token 无效 / 用户不存在 / 账号已停用
    """
    # 优先从 Header 提取，其次从 Query 参数提取
    token = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据，请登录后重试",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 解析 Token 载荷
    payload = decode_access_token(token)

    # 提取用户 ID
    user_id: int = payload.get("id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 载荷中缺少用户 ID",
        )

    # 查询数据库中的用户
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在，请重新登录",
        )

    # 检查账号是否启用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被停用，请联系教师",
        )

    return user


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    """
    教师角色权限校验依赖

    使用方式：
        @router.post("/admin/students")
        def create_student(teacher: User = Depends(require_teacher)):
            ...

    说明：
        在 get_current_user 基础上增加角色验证，确保当前用户为教师

    异常：
        403 - 当前用户不是教师角色
    """
    role_value = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role_value != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：仅教师可执行此操作",
        )
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """
    学生角色权限校验依赖

    使用方式：
        @router.get("/student/assignments")
        def my_assignments(student: User = Depends(require_student)):
            ...

    说明：
        在 get_current_user 基础上增加角色验证，确保当前用户为学生

    异常：
        403 - 当前用户不是学生角色
    """
    role_value = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if role_value != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足：仅学生可执行此操作",
        )
    return current_user
