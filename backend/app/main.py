# ============================================================
# FastAPI 应用入口
# 功能：
#   1. 创建 FastAPI 应用实例
#   2. 注册所有 API 路由（auth / admin / teacher / student / chat）
#   3. 配置 CORS 中间件（允许前端跨域请求）
#   4. 应用启动时初始化数据库（建表 + 创建默认教师账号）
#   5. 提供健康检查端点
#   6. 挂载前端静态文件（SPA 支持）
# 启动命令：
#   uvicorn backend.app.main:app --reload --port 8000
# ============================================================

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.core.config import settings
from backend.app.core.database import init_database

# 导入所有路由模块
from backend.app.api.endpoints.auth import router as auth_router
from backend.app.api.endpoints.admin import admin_router, teacher_router
from backend.app.api.endpoints.student import router as student_router
from backend.app.api.endpoints.chat import router as chat_router


# ==================== 路径常量 ====================

# 计算项目根目录（main.py 位于 backend/app/main.py，向上三级）
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent.parent

# 前端构建产物目录（常见路径，按优先级尝试）
_FRONTEND_CANDIDATES = [
    _PROJECT_ROOT / "frontend" ,       # Vite 默认
]


def _find_frontend_dist() -> Path | None:
    """
    自动查找前端构建产物目录

    按优先级依次检查常见路径，找到第一个包含 index.html 的目录即返回。
    如果都找不到，返回 None。
    """
    for candidate in _FRONTEND_CANDIDATES:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


# ==================== 应用生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器

    启动时：
        - 初始化数据库（创建表 + 默认教师账号）
        - 检测前端静态文件目录

    关闭时：
        - 清理资源（当前无需额外清理）
    """
    # ---- 启动阶段 ----
    print("🚀 正在启动 AI 智能作业管理系统...")
    init_database()  # 自动建表 + 创建默认教师

    # 检测前端静态文件
    frontend_dir = _find_frontend_dist()
    if frontend_dir:
        print(f"📂 前端静态文件目录：{frontend_dir}")
    else:
        print("⚠️ 未找到前端构建产物，仅提供 API 服务（访问 /docs 查看接口文档）")

    print("✅ 系统启动完成！")

    yield  # 应用运行中...

    # ---- 关闭阶段 ----
    print("👋 系统正在关闭...")


# ==================== 创建 FastAPI 应用 ====================

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "具备 AI 智能体的双角色作业管理系统\n\n"
        "## 功能模块\n"
        "- 🔐 **认证模块** — 统一登录 + JWT 鉴权\n"
        "- 👨‍🏫 **教师端** — 学生管理 + 作业发布 + 提交查看 + 打包下载\n"
        "- 👨‍🎓 **学生端** — 作业查看 + 文件提交\n"
        "- 🤖 **AI 助手** — LangChain ReAct Agent 智能问答\n\n"
        "## 技术栈\n"
        "FastAPI + SQLAlchemy + PostgreSQL + JWT + LangChain + 通义千问"
    ),
    docs_url="/docs",         # Swagger UI 路径
    redoc_url="/redoc",       # ReDoc 路径
    lifespan=lifespan,
)


# ==================== 配置 CORS 中间件 ====================

# 允许的前端源地址
# 生产环境应替换为实际部署的前端域名
ALLOWED_ORIGINS = [
    "http://localhost:5173",      # Vite 默认开发端口
    "http://localhost:3000",      # React CRA / Next.js 默认端口
    "http://127.0.0.1:5173",     # Vite（IP 形式）
    "http://127.0.0.1:8000",     # 前端构建后由后端托管时
    "http://localhost:8000",      # 同上（域名形式）
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 注册 API 路由 ====================
# 所有路由统一使用 /api 前缀

app.include_router(auth_router, prefix="/api")       # /api/auth/...
app.include_router(admin_router, prefix="/api")      # /api/admin/...
app.include_router(teacher_router, prefix="/api")    # /api/teacher/...
app.include_router(student_router, prefix="/api")    # /api/student/...
app.include_router(chat_router, prefix="/api")       # /api/chat/...


# ==================== 健康检查端点 ====================

@app.get(
    "/api/health",
    tags=["系统"],
    summary="健康检查",
    description="用于监控系统运行状态的健康检查端点",
)
def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "message": "系统运行正常 ✅",
    }


# ==================== 路由总览端点 ====================

@app.get(
    "/api/routes",
    tags=["系统"],
    summary="路由总览",
    description="列出系统所有已注册的 API 路由",
)
def list_routes():
    """列出所有已注册的 API 路由"""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
            })
    return {
        "total": len(routes),
        "routes": routes,
    }


# ==================== 前端静态文件托管 ====================
# 注意：此部分必须放在所有 API 路由注册之后，
# 否则 catch-all 路由会拦截 API 请求

_FRONTEND_DIR = _find_frontend_dist()

if _FRONTEND_DIR:
    # 挂载静态资源目录（JS、CSS、图片等）
    # Vite 构建后静态资源在 assets/ 子目录
    _assets_dir = _FRONTEND_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_assets_dir)),
            name="frontend-assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(request: Request, full_path: str):
        """
        前端 SPA 路由兜底

        处理逻辑：
            1. 如果请求的是一个真实存在的静态文件 → 直接返回该文件
            2. 否则 → 返回 index.html（由前端路由器处理）

        说明：
            - 此路由必须注册在所有 API 路由之后
            - /api/* 路径已被上面的路由匹配，不会走到这里
            - /docs 和 /redoc 也不会被拦截
        """
        # 尝试返回静态文件
        file_path = _FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))

        # 兜底返回 index.html（SPA 路由）
        return FileResponse(str(_FRONTEND_DIR / "index.html"))

else:
    # 未找到前端构建产物，提供友好的根路径提示
    @app.get("/", include_in_schema=False)
    async def root_redirect():
        """根路径提示"""
        return JSONResponse({
            "message": "AI 智能作业管理系统 API 服务运行中",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/api/health",
            "hint": "前端构建产物未找到，请先构建前端项目后重启服务",
        })
