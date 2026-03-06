// ============================================================
// API 客户端 — 真实网络请求层 (Vue 3 版本)
// 功能：
//   1. 所有请求自动附带 Authorization: Bearer <token>
//   2. 文件上传使用 FormData，不手动设置 Content-Type
//   3. 打包下载通过 window.open 触发真实文件流
//   4. AI 对话调用真实 POST /api/chat/ask
//   5. 批量导入学生（Excel 上传）
//   6. 获取专业列表（发布作业用）
//   7. [新增] 教师查看某学生作业完成情况
//   8. [新增] 教师查看某作业提交统计（含未交名单）
//   9. [新增] 教师重置学生密码
// ============================================================

// ==================== 类型定义 ====================

/** 用户基本信息 */
export interface UserInfo {
  id: number
  username: string
  full_name: string
  role: 'teacher' | 'student'
}

/** 学生信息（教师端管理用） */
export interface Student {
  id: number
  username: string
  full_name: string
  role: string
  is_active: boolean
  major: string | null
  is_part_time: boolean
  created_at: string
}

/** 作业信息 */
export interface AssignmentItem {
  id: number
  course_name: string
  title: string
  description: string
  deadline: string
  allowed_extensions: string
  teacher_id: number
  created_at: string
  /** 目标专业列表，null 表示面向所有专业 */
  target_majors?: string[] | null
  /** 目标学习类型：null=全部，false=仅全日制，true=仅非全日制 */
  target_is_part_time?: boolean | null
  /** 学生端：提交状态（未交/已交/已截止） */
  status?: string
  submitted_at?: string | null
}

/** 提交记录（教师端查看用） */
export interface SubmissionItem {
  id: number
  student_id: number
  student_name: string
  student_username: string
  major: string | null
  is_part_time: boolean
  file_path: string
  submitted_at: string
  status: string
}

/** 批量导入结果 */
export interface ImportResult {
  message: string
  success_count: number
  fail_count: number
  fail_details: Array<{
    row: number
    username: string
    reason: string
  }>
}

/** [新增] 学生作业完成情况中的单项作业 */
export interface StudentAssignmentStatusItem {
  id: number
  course_name: string
  title: string
  deadline: string
  status: string           // 已交/未交/已截止
  submitted_at: string | null
}

/** [新增] 教师查看某学生作业完成情况的响应 */
export interface StudentAssignmentStatusResponse {
  student_id: number
  username: string
  full_name: string
  major: string | null
  is_part_time: boolean
  assignments: StudentAssignmentStatusItem[]
}

/** [新增] 提交统计中的已交学生 */
export interface SubmittedStudentInfo {
  student_id: number
  username: string
  full_name: string
  major: string | null
  is_part_time: boolean
  submitted_at: string | null
}

/** [新增] 提交统计中的未交学生 */
export interface NotSubmittedStudentInfo {
  student_id: number
  username: string
  full_name: string
  major: string | null
  is_part_time: boolean
}

/** [新增] 作业提交统计响应 */
export interface AssignmentSubmitStatsResponse {
  total_should_submit: number
  submitted_count: number
  not_submitted_count: number
  submitted_students: SubmittedStudentInfo[]
  not_submitted_students: NotSubmittedStudentInfo[]
}

// ==================== Token 管理 ====================

const TOKEN_KEY = 'hw_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// ==================== 基础请求封装 ====================

// 从环境变量读取 API 基础路径，默认 /api
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

/**
 * 统一请求函数
 * - 自动附带 Authorization 头
 * - 非 FormData 请求自动设置 JSON Content-Type
 * - 统一错误处理与响应解析
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  }

  // 自动附带 Bearer Token
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // 非 FormData 请求默认设置 JSON Content-Type
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    const message =
      errorBody?.detail || errorBody?.message || `请求失败 (${res.status})`
    throw new Error(message)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json()
}

// ==================== 认证 API ====================

/**
 * 用户登录
 * 调用 POST /api/auth/login，返回 token + 用户信息
 */
export async function login(
  username: string,
  password: string,
): Promise<{ access_token: string; user: UserInfo }> {
  const data = await request<{ access_token: string; user: UserInfo }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  // 登录成功后自动存储 Token
  setToken(data.access_token)
  return data
}

// ==================== 学生管理 API（教师端） ====================

/** 获取学生列表（可选关键字搜索） */
export async function getStudents(keyword?: string): Promise<Student[]> {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''
  return request<Student[]>(`/admin/students${query}`)
}

/** 录入新学生 */
export async function createStudent(data: {
  username: string
  full_name: string
  major?: string
  is_part_time?: boolean
}): Promise<Student> {
  return request<Student>('/admin/students', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/** 更新学生信息 */
export async function updateStudent(
  id: number,
  data: Partial<Student>,
): Promise<Student> {
  return request<Student>(`/admin/students/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

/** 删除学生 */
export async function deleteStudent(id: number): Promise<void> {
  await request<void>(`/admin/students/${id}`, { method: 'DELETE' })
}

/** [新增] 重置学生密码为默认密码 */
export async function resetStudentPassword(id: number): Promise<{ message: string }> {
  return request<{ message: string }>(`/admin/students/${id}/reset-password`, {
    method: 'POST',
  })
}

/**
 * 批量导入学生（上传 Excel）
 * 使用 FormData 上传 .xlsx 文件
 */
export async function importStudents(file: File): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)

  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // ⚠️ 不手动设置 Content-Type，让浏览器自动生成含 boundary 的 multipart/form-data

  const res = await fetch(`${API_BASE}/admin/students/import`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    const message =
      errorBody?.detail || errorBody?.message || `导入失败 (${res.status})`
    throw new Error(message)
  }

  return res.json()
}

// ==================== 专业列表 API ====================

/** 获取所有学生的不重复专业列表（教师发布作业时使用） */
export async function getMajors(): Promise<string[]> {
  return request<string[]>('/admin/majors')
}

// ==================== 作业管理 API（教师端） ====================

/** 获取所有作业列表 */
export async function getAssignments(): Promise<AssignmentItem[]> {
  return request<AssignmentItem[]>('/teacher/assignments')
}

/** 创建新作业 */
export async function createAssignment(data: {
  course_name: string
  title: string
  description: string
  deadline: string
  allowed_extensions: string
  target_majors?: string[] | null
  target_is_part_time?: boolean | null
}): Promise<AssignmentItem> {
  return request<AssignmentItem>('/teacher/assignments', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/** 更新作业 */
export async function updateAssignment(
  id: number,
  data: Partial<AssignmentItem>,
): Promise<AssignmentItem> {
  return request<AssignmentItem>(`/teacher/assignments/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

/** 删除作业 */
export async function deleteAssignment(id: number): Promise<void> {
  await request<void>(`/teacher/assignments/${id}`, { method: 'DELETE' })
}

// ==================== 提交管理 API ====================

/** 获取某作业的提交记录（教师端） */
export async function getSubmissions(
  assignmentId: number,
): Promise<SubmissionItem[]> {
  return request<SubmissionItem[]>(
    `/teacher/assignments/${assignmentId}/submissions`,
  )
}

// ==================== [新增] 教师端详情查看 API ====================

/**
 * 查看某学生的作业完成情况（教师端）
 * GET /api/teacher/students/{studentId}/assignments
 */
export async function getStudentAssignmentStatus(
  studentId: number,
): Promise<StudentAssignmentStatusResponse> {
  return request<StudentAssignmentStatusResponse>(
    `/teacher/students/${studentId}/assignments`,
  )
}

/**
 * 查看某作业的提交统计（含未交名单）（教师端）
 * GET /api/teacher/assignments/{assignmentId}/submit-stats
 */
export async function getAssignmentSubmitStats(
  assignmentId: number,
): Promise<AssignmentSubmitStatsResponse> {
  return request<AssignmentSubmitStatsResponse>(
    `/teacher/assignments/${assignmentId}/submit-stats`,
  )
}

// ==================== 学生端作业 API ====================

/** 获取当前学生的作业列表（含提交状态） */
export async function getStudentAssignments(): Promise<AssignmentItem[]> {
  return request<AssignmentItem[]>('/student/assignments')
}

/**
 * 提交作业文件
 * 【安全修复】student_id 由后端从 JWT Token 中解析，前端绝不传递
 * 【文件流修复】使用 FormData 构建真实 multipart 上传，不手动设置 Content-Type
 */
export async function submitAssignment(
  assignmentId: number,
  file: File,
): Promise<{ message: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // ⚠️ 注意：不要手动设置 Content-Type，让浏览器自动生成含 boundary 的 multipart/form-data

  const res = await fetch(
    `${API_BASE}/student/assignments/${assignmentId}/submit`,
    {
      method: 'POST',
      headers,
      body: formData,
    },
  )

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    const message =
      errorBody?.detail || errorBody?.message || `提交失败 (${res.status})`
    throw new Error(message)
  }

  return res.json()
}

// ==================== AI 对话 API ====================

/**
 * 发送 AI 对话消息
 * 【修复】移除本地假 AI 回复逻辑，调用真实 POST /api/chat/ask
 * 传入 { message, session_id }，返回 { reply, session_id }
 */
export async function chatAsk(
  message: string,
  sessionId?: string,
): Promise<{ reply: string; session_id: string }> {
  return request<{ reply: string; session_id: string }>('/chat/ask', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

// ==================== 下载工具函数 ====================

/**
 * 打包下载某作业的所有提交文件（教师端）
 * 【修复】通过 window.open + URL 携带 token 触发真实跨域文件流下载
 */
export function downloadSubmissions(assignmentId: number): void {
  const token = getToken()
  const downloadUrl = `${API_BASE}/teacher/assignments/${assignmentId}/download?access_token=${token}`
  window.open(downloadUrl, '_blank')
}

// ==================== 修改密码 API ====================

/** 修改当前用户密码 */
export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<{ message: string }> {
  return request<{ message: string }>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  })
}
