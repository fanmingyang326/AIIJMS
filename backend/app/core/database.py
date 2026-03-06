# ============================================================
# 数据库会话管理
# 功能：
#   1. 创建 SQLAlchemy 引擎和会话工厂
#   2. 提供 FastAPI 依赖注入用的 get_db 生成器
#   3. 提供数据库初始化函数（建表 + 创建默认教师账号）
# ============================================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import settings
from backend.app.models.base import Base

# -------------------- 创建数据库引擎 --------------------
# pool_pre_ping=True：每次从连接池获取连接前先 ping 一下，避免使用已断开的连接
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # 生产环境设为 False，调试时可设为 True 查看 SQL 语句
)

# -------------------- 创建会话工厂 --------------------
# autocommit=False：需要手动调用 commit()
# autoflush=False：需要手动调用 flush()，避免隐式刷新带来的性能问题
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db():
    """
    FastAPI 依赖注入：获取数据库会话

    使用方式：
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    说明：
        - 使用 yield 确保请求结束后自动关闭会话
        - 每个请求独立会话，线程安全
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    初始化数据库

    功能：
        1. 根据 ORM 模型自动创建所有表（如果不存在）
        2. 检查是否存在默认教师账号，不存在则自动创建

    说明：
        - 仅在应用启动时调用一次
        - 生产环境建议使用 Alembic 进行数据库迁移管理
    """
    from backend.app.models import User, Assignment, Submission  # noqa: F401
    from backend.app.core.security import hash_password
    from backend.app.models.user import UserRole

    # 第一步：创建所有表
    Base.metadata.create_all(bind=engine)

    # 第二步：创建默认教师账号（如果不存在）
    db = SessionLocal()
    try:
        # 查询是否已存在教师账号
        existing_teacher = db.query(User).filter(
            User.role == UserRole.TEACHER
        ).first()

        if not existing_teacher:
            # 创建默认教师账号
            default_teacher = User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="系统管理员",
                role=UserRole.TEACHER,
                is_active=True,
            )
            db.add(default_teacher)
            db.commit()
            print("✅ 默认教师账号已创建：admin / admin123")
        else:
            print("ℹ️ 教师账号已存在，跳过创建")
    except Exception as e:
        db.rollback()
        print(f"❌ 初始化数据库时出错：{e}")
    finally:
        db.close()
