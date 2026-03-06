# ============================================================
# 应用全局配置
# 功能：集中管理所有配置项，包括数据库连接、JWT 密钥、文件上传等
# 说明：生产环境应通过环境变量覆盖默认值
# ============================================================

import os


class Settings:
    """
    应用全局配置类

    配置优先级：环境变量 > 默认值
    生产部署时通过 .env 文件或系统环境变量设置敏感信息
    """

    # -------------------- 项目基本信息 --------------------
    PROJECT_NAME: str = "AI 智能作业管理系统"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # -------------------- 数据库配置 --------------------
    # PostgreSQL 连接字符串格式：postgresql://用户名:密码@主机:端口/数据库名
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://Agr_farmer:Agr_farmer@localhost:5432/homework_system"
    )

    # -------------------- JWT 配置 --------------------
    # JWT 签名密钥（生产环境必须通过环境变量设置强随机密钥）
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "ai-homework-system-secret-key-change-in-production-2024"
    )
    # JWT 签名算法
    JWT_ALGORITHM: str = "HS256"
    # JWT Token 过期时间（分钟）：默认 24 小时
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES", "1440"
    ))

    # -------------------- 文件上传配置 --------------------
    # 上传文件存储根目录（相对于项目根目录）
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    # 单文件最大大小限制（字节）：默认 50MB
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))

    # -------------------- 默认密码配置 --------------------
    # 教师录入学生时，系统为学生生成的默认密码
    # 学生首次登录后应立即修改
    DEFAULT_STUDENT_PASSWORD: str = os.getenv(
        "DEFAULT_STUDENT_PASSWORD", "123456"
    )

    # -------------------- 通义千问 API 配置 --------------------
    # 阿里通义千问 API 密钥
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "sk-2e22994247ce4e1fa7b6b38323236cbc")
    # 通义千问兼容 OpenAI 接口的 Base URL
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 使用的模型名称
    DASHSCOPE_MODEL: str = os.getenv("DASHSCOPE_MODEL", "qwen-plus-2025-09-11")


# 全局配置单例
settings = Settings()
