# ============================================================
# LangChain Agent 服务模块
# 功能：构建具备 Tool Calling 能力的 ReAct 智能体
# 核心架构：
#   1. 安全上下文注入 — student_id 通过闭包硬性绑定给 Tool，
#      绝不由大模型从提示词中提取
#   2. 三个核心 Tool —
#      get_pending_assignments  查询未交作业
#      get_assignment_details   查询作业详情
#      check_submission_status  检查提交状态
#   3. Agent Executor — 组装 LLM + Tools + Prompt，
#      开启 Memory 支持多轮追问
#
# 大模型配置：
#   使用阿里通义千问 API（DashScope 兼容 OpenAI 接口）
#   base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
#   通过 ChatOpenAI 模块调用，完美支持 Tool Calling
# ============================================================

import json
import uuid
from typing import Dict, Optional

from sqlalchemy.orm import Session

from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from langchain_classic.memory import ConversationBufferWindowMemory

from backend.app.core.config import settings


# ============================================================
# 一、会话记忆管理（全局缓存）
# ============================================================

# 全局会话记忆存储字典
# key: session_id (str)
# value: ConversationBufferWindowMemory 对象
# 说明：
#   - 使用 BufferWindowMemory 限制记忆窗口大小，避免上下文过长
#   - 生产环境建议使用 Redis 替代内存存储
_session_memories: Dict[str, ConversationBufferWindowMemory] = {}

# 最大记忆窗口大小（保留最近 10 轮对话）
_MEMORY_WINDOW_SIZE = 10

# 最大缓存会话数（超过时清理最早的会话）
_MAX_SESSIONS = 200


def _get_or_create_memory(session_id: str) -> ConversationBufferWindowMemory:
    """
    获取或创建对话会话的记忆对象

    参数：
        session_id - 对话会话 ID

    返回：
        ConversationBufferWindowMemory 对象

    说明：
        - 首次调用时创建新的 Memory 对象
        - 后续调用返回已有 Memory（保持多轮对话上下文）
        - 超过最大缓存会话数时清理最早的会话
    """
    if session_id not in _session_memories:
        # 缓存清理：超过最大会话数时删除最早的
        if len(_session_memories) >= _MAX_SESSIONS:
            # 删除第一个（最早的）会话
            oldest_key = next(iter(_session_memories))
            del _session_memories[oldest_key]

        # 创建新的记忆对象
        _session_memories[session_id] = ConversationBufferWindowMemory(
            k=_MEMORY_WINDOW_SIZE,         # 保留最近 k 轮对话
            memory_key="chat_history",     # 在 Prompt 中的占位符名称
            return_messages=True,          # 返回 Message 对象（非字符串）
            output_key="output",           # Agent 输出的 key
        )

    return _session_memories[session_id]


# ============================================================
# 二、Tool 工厂函数（核心安全设计）
# ============================================================
# 设计理念：
#   通过闭包（Closure）将 student_id 和 db 硬性绑定到 Tool 内部。
#   大模型在推理过程中只能决定"调用哪个 Tool"和"传什么参数"，
#   但 student_id 始终来自 JWT Token 解析的安全上下文，
#   大模型无法篡改或伪造，从根本上杜绝越权访问。
#
# 异步设计：
#   所有 Tool 函数均使用 async def 声明。
#   LangChain 的异步 Agent (ainvoke) 在主事件循环中调用 Tool，
#   如果 Tool 是同步函数，Agent 会将其放入线程池执行，
#   导致 SQLAlchemy 的单线程 Session 跨线程使用，
#   引发 DetachedInstanceError。
#   将 Tool 改为 async 后，它们在主事件循环中直接执行，
#   与 Session 保持在同一线程，彻底解决此问题。
# ============================================================


def _create_tools(student_id: int, db: Session):
    """
    创建绑定了安全上下文的 Tool 列表

    参数：
        student_id - 当前登录学生的 ID（从 JWT Token 解析，安全注入）
        db         - 数据库会话

    返回：
        包含 3 个 Tool 的列表

    安全说明：
        student_id 通过 Python 闭包机制绑定到每个 Tool 内部，
        大模型的提示词中不包含也无法修改此值。
        即使恶意用户在对话中声称自己是另一个学生，
        Tool 实际操作的仍然是 JWT Token 对应的学生数据。
    """

    # -------------------- Tool 1: 查询未交作业 --------------------
    @tool
    async def get_pending_assignments() -> str:
        """查询当前学生所有未过期且未提交的作业列表。

        该工具会返回学生当前需要完成的所有作业，包括：
        - 课程名称
        - 作业标题
        - 截止时间
        - 距截止的剩余时间
        - 允许的文件格式

        当学生询问"我还有哪些作业没交"、"有什么待完成的作业"、
        "还有多少作业要交"等问题时，请调用此工具。

        无需传入任何参数，学生身份已由系统自动识别。
        """
        from backend.app.crud.crud_assignment import get_pending_assignments_for_student

        # student_id 通过闭包从安全上下文获取
        pending = get_pending_assignments_for_student(
            db=db,
            student_id=student_id,  # ✅ 安全注入，非大模型提取
        )

        if not pending:
            return "你目前没有未交的作业，所有作业都已提交或已截止。太棒了！🎉"

        # 格式化输出
        result_lines = [f"你当前有 {len(pending)} 个未提交的作业：\n"]

        for i, item in enumerate(pending, 1):
            result_lines.append(
                f"{i}. 【{item['course_name']}】{item['title']}\n"
                f"   📅 截止时间：{item['deadline']}\n"
                f"   ⏰ {item['remaining']}\n"
                f"   📎 允许格式：{item['allowed_extensions']}\n"
            )

        return "\n".join(result_lines)

    # -------------------- Tool 2: 查询作业详情 --------------------
    @tool
    async def get_assignment_details(keyword: str) -> str:
        """根据模糊关键词搜索并返回作业的详细信息。

        参数：
            keyword: 搜索关键词，可以是课程名称的一部分（如"数据库"）
                     或作业标题的一部分（如"实验报告"）。

        返回作业的完整信息，包括：
        - 课程名称
        - 作业标题
        - 作业要求（详细描述）
        - 截止时间
        - 允许提交的文件格式

        当学生询问"数据库作业要求是什么"、"操作系统实验要交什么格式"、
        "第三次作业的具体要求"等问题时，请调用此工具。

        请从学生问题中提取最关键的课程名或作业名作为 keyword 参数。
        """
        from backend.app.crud.crud_assignment import search_assignment_by_keyword

        # 根据关键词搜索作业
        assignments = search_assignment_by_keyword(db=db, keyword=keyword)

        if not assignments:
            return f"未找到与「{keyword}」相关的作业。请尝试使用其他关键词，比如课程名或作业标题中的关键字。"

        # 格式化输出
        result_lines = [f"找到 {len(assignments)} 个与「{keyword}」相关的作业：\n"]

        for i, assignment in enumerate(assignments, 1):
            result_lines.append(
                f"{i}. 【{assignment.course_name}】{assignment.title}\n"
                f"   📝 作业要求：{assignment.description}\n"
                f"   📅 截止时间：{assignment.deadline.strftime('%Y-%m-%d %H:%M')}\n"
                f"   📎 允许格式：{assignment.allowed_extensions}\n"
            )

        return "\n".join(result_lines)

    # -------------------- Tool 3: 检查提交状态 --------------------
    @tool
    async def check_submission_status(keyword: str) -> str:
        """检查当前学生针对某个作业的提交状态。

        参数：
            keyword: 搜索关键词，可以是课程名称的一部分（如"操作系统"）
                     或作业标题的一部分（如"实验"）。

        返回该学生对匹配作业的提交详情，包括：
        - 是否已提交
        - 提交时间
        - 提交的文件名
        - 截止时间
        - 是否已过期

        当学生询问"我操作系统的作业交了没"、"数据库实验提交了吗"、
        "我的第三次作业交过了吗"等问题时，请调用此工具。

        请从学生问题中提取最关键的课程名或作业名作为 keyword 参数。
        无需传入学生身份信息，系统会自动识别当前学生。
        """
        from backend.app.crud.crud_submission import check_student_submission_status

        # student_id 通过闭包从安全上下文获取
        status_list = check_student_submission_status(
            db=db,
            student_id=student_id,  # ✅ 安全注入，非大模型提取
            keyword=keyword,
        )

        if not status_list:
            return f"未找到与「{keyword}」相关的作业。请尝试使用其他关键词，比如课程名或作业标题中的关键字。"

        # 格式化输出
        result_lines = []

        for item in status_list:
            status_emoji = "✅ 已提交" if item["has_submitted"] else "❌ 未提交"
            expired_tag = "（已截止）" if item["is_expired"] else ""

            result_lines.append(
                f"【{item['course_name']}】{item['title']} {expired_tag}\n"
                f"   状态：{status_emoji}\n"
                f"   截止时间：{item['deadline']}"
            )

            if item["has_submitted"]:
                result_lines.append(
                    f"   提交时间：{item['submitted_at']}\n"
                    f"   提交文件：{item['file_name']}"
                )

            result_lines.append("")  # 空行分隔

        return "\n".join(result_lines)

    # 返回 3 个 Tool 的列表
    return [
        get_pending_assignments,
        get_assignment_details,
        check_submission_status,
    ]


# ============================================================
# 三、构建 LLM 实例
# ============================================================

def _create_llm() -> ChatOpenAI:
    """
    创建通义千问 LLM 实例

    配置说明：
        - 使用 ChatOpenAI 模块（LangChain 原生支持）
        - base_url 指向 DashScope 兼容 OpenAI 的接口地址
        - 该接口完美支持 Tool Calling（Function Calling）
        - model 默认使用 qwen-plus（可通过环境变量配置）

    返回：
        ChatOpenAI 实例

    注意：
        必须配置 DASHSCOPE_API_KEY 环境变量，否则无法调用
    """
    if not settings.DASHSCOPE_API_KEY:
        raise ValueError(
            "未配置通义千问 API 密钥！\n"
            "请设置环境变量 DASHSCOPE_API_KEY，\n"
            "或在 backend/app/core/config.py 中配置。"
        )

    return ChatOpenAI(
        # 使用阿里通义千问的 OpenAI 兼容接口
        openai_api_base=settings.DASHSCOPE_BASE_URL,
        openai_api_key=settings.DASHSCOPE_API_KEY,
        model_name=settings.DASHSCOPE_MODEL,
        # 温度参数：0.3 保持回复的准确性，同时允许少量创造性
        temperature=0.3,
        # 流式输出关闭（Agent 需要完整响应来决定下一步）
        streaming=False,
        # 请求超时时间（秒）
        request_timeout=60,
    )


# ============================================================
# 四、构建 Agent Prompt（人设提示词）
# ============================================================

def _create_agent_prompt() -> ChatPromptTemplate:
    """
    创建 Agent 的提示词模板

    人设定义：
        - 友好的 AI 作业助手
        - 只帮助查询作业相关信息
        - 引导学生使用系统功能
        - 不帮写作业、不泄露其他学生信息

    模板结构：
        1. SystemMessage — 定义 Agent 的角色、能力和约束
        2. MessagesPlaceholder("chat_history") — 多轮对话历史
        3. HumanMessage — 当前学生的提问
        4. MessagesPlaceholder("agent_scratchpad") — Agent 推理过程

    返回：
        ChatPromptTemplate 对象
    """
    system_prompt = """你是一个友好、专业的 AI 作业助手，服务于一个高校作业管理系统。

## 你的身份
你叫"小智"，是学生的专属作业助手。你的语气应该亲切、鼓励，像一个热心的学长/学姐。

## 你的能力
你可以帮助学生：
1. 📋 **查询未交作业** — 告诉学生还有哪些作业没交，以及距截止还有多久
2. 📝 **查看作业详情** — 告诉学生某个作业的具体要求、提交格式等
3. ✅ **检查提交状态** — 告诉学生某个作业是否已经提交

## 你的约束（非常重要！）
- 你只能查询当前登录学生自己的数据，不能查看其他学生的信息
- 你不能帮学生写作业或提供作业答案
- 你不能修改任何数据（如修改截止时间、删除作业等）
- 如果学生的问题超出你的能力范围，请礼貌地告知并建议联系教师
- 学生的身份已由系统自动验证，你无需询问学号或姓名

## 回复风格
- 使用简体中文回复
- 回复简洁清晰，使用 emoji 增加可读性
- 对紧急的截止时间给予提醒和鼓励
- 当学生完成了所有作业时，给予表扬和鼓励

## 工具使用指南
- 当需要查询信息时，请主动调用合适的工具
- 如果关键词搜索没有结果，尝试使用更简短或更广泛的关键词
- 回答时基于工具返回的实际数据，不要编造信息"""

    return ChatPromptTemplate.from_messages([
        # 系统人设提示词
        SystemMessage(content=system_prompt),
        # 多轮对话历史（由 Memory 自动注入）
        MessagesPlaceholder(variable_name="chat_history"),
        # 当前学生的提问
        ("human", "{input}"),
        # Agent 推理过程（由 Agent 框架自动管理）
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


# ============================================================
# 五、Agent 执行入口（对外暴露的主函数）
# ============================================================

async def run_agent(
    question: str,
    student_id: int,
    session_id: str,
    db: Session,
) -> str:
    """
    运行 LangChain Agent 处理学生问题

    这是 Agent 模块对外暴露的唯一入口函数，由 chat.py 路由调用。

    参数：
        question   - 学生输入的问题文本
        student_id - 当前学生 ID（从 JWT Token 安全解析，绝非前端传递）
        session_id - 对话会话 ID（用于多轮对话记忆管理）
        db         - 数据库会话（传递给 Tool 用于数据查询）

    返回：
        AI 助手的回复文本

    完整执行流程：
        1. 创建绑定了 student_id 的 Tools（安全上下文注入）
        2. 创建通义千问 LLM 实例
        3. 构建 Agent Prompt（含人设和多轮对话历史）
        4. 获取或创建该 session 的 Memory
        5. 组装 Agent Executor
        6. 调用 Agent 处理问题
        7. 返回回复文本

    安全架构图：

        JWT Token
            │
            ▼
        FastAPI 路由 (chat.py)
            │ 解析出 student_id
            ▼
        run_agent(student_id=安全值)
            │
            ▼
        _create_tools(student_id)  ← 闭包绑定
            │
            ├─→ get_pending_assignments()    # async, 内部使用安全的 student_id
            ├─→ get_assignment_details(kw)   # async, 查询公共作业信息
            └─→ check_submission_status(kw)  # async, 内部使用安全的 student_id
            │
            ▼
        Agent Executor
            │ LLM 决策 → 调用 Tool → 获取结果 → 生成回复
            ▼
        返回回复文本

    异常处理：
        - API Key 未配置 → 返回友好提示
        - LLM 调用超时 → 返回重试提示
        - 其他异常 → 返回通用错误提示
    """
    try:
        # ---- 第 1 步：创建绑定安全上下文的 Tools ----
        # student_id 通过闭包机制注入到每个 Tool 内部
        # 大模型无法修改此值，确保数据访问安全
        tools = _create_tools(
            student_id=student_id,  # ✅ 来自 JWT Token，非用户输入
            db=db,
        )

        # ---- 第 2 步：创建通义千问 LLM 实例 ----
        llm = _create_llm()

        # ---- 第 3 步：构建 Agent Prompt ----
        prompt = _create_agent_prompt()

        # ---- 第 4 步：获取或创建对话记忆 ----
        memory = _get_or_create_memory(session_id)

        # ---- 第 5 步：创建 Tool Calling Agent ----
        # 使用 create_tool_calling_agent 构建 Agent
        # 该方法利用 OpenAI 兼容的 Tool Calling 接口
        # 通义千问通过 DashScope 兼容接口完美支持此功能
        agent = create_tool_calling_agent(
            llm=llm,
            tools=tools,
            prompt=prompt,
        )

        # ---- 第 6 步：组装 Agent Executor ----
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            # 允许的最大推理步骤数（防止无限循环）
            max_iterations=5,
            # 超过最大步骤时的处理方式
            handle_parsing_errors=True,
            # 是否在控制台输出推理过程（调试用）
            verbose=True,
        )

        # ---- 第 7 步：调用 Agent 处理问题 ----
        result = await agent_executor.ainvoke(
            {"input": question}
        )

        # 提取 Agent 的回复文本
        return result.get("output", "抱歉，我暂时无法回答这个问题。")

    except ValueError as e:
        # API Key 未配置等配置错误
        error_msg = str(e)
        if "API" in error_msg or "密钥" in error_msg:
            return (
                "⚠️ AI 助手暂时无法使用\n\n"
                "原因：系统尚未配置 AI 服务的 API 密钥。\n"
                "请联系系统管理员配置 DASHSCOPE_API_KEY 环境变量。"
            )
        return f"⚠️ 配置错误：{error_msg}"

    except TimeoutError:
        return (
            "⏰ AI 助手响应超时\n\n"
            "可能是网络波动或服务繁忙，请稍后重试。"
        )

    except Exception as e:
        # 捕获所有未预期的异常，返回友好提示
        print(f"❌ Agent 执行异常：{type(e).__name__}: {e}")
        return (
            "😅 抱歉，我在处理你的问题时遇到了一些困难。\n\n"
            "请尝试：\n"
            "1. 重新描述你的问题\n"
            "2. 使用更具体的关键词\n"
            "3. 如果问题持续，请联系教师获取帮助"
        )
