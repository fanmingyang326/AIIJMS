<!-- ============================================================
  教师管理后台 (TeacherDashboard.vue)
  功能：
    1. 学生管理 — 列表展示 + 录入/编辑/删除学生 + 批量导入（Excel）
       - [新增] 序号列 + 排序下拉 + 专业多选筛选
       - [新增] 点击学生行 → 弹窗查看该学生的作业完成情况
    2. 作业管理 — 发布/编辑/删除作业 + 查看提交 + 打包下载
       - 支持按专业发布作业（多选目标专业）
       - 支持按学习类型发布作业（全日制/非全日制/全部）
       - [新增] 点击作业行 → 弹窗查看提交统计（含未交名单）
    3. 顶部导航栏含用户信息和登出
    4. AI 对话入口
============================================================ -->

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Users, BookOpen, LogOut, Plus, Pencil, Trash2, Search, Download,
  Eye, X, GraduationCap, Calendar, FileText, Clock, UserCheck, UserX,
  CheckCircle2, AlertTriangle, MessageCircle, Upload, Target,
  ChevronDown, ChevronRight, Filter, ArrowUpDown, KeyRound
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import {
  getStudents, createStudent, updateStudent, deleteStudent, importStudents,
  getAssignments, createAssignment, updateAssignment, deleteAssignment,
  getSubmissions, downloadSubmissions, getMajors,
  getStudentAssignmentStatus, getAssignmentSubmitStats,
  resetStudentPassword,
  type Student, type AssignmentItem, type SubmissionItem, type ImportResult,
  type StudentAssignmentStatusResponse, type AssignmentSubmitStatsResponse,
} from '@/api/client'
import ChatBox from '@/components/ChatBox.vue'

const router = useRouter()
const auth = useAuthStore()

// ==================== 全局状态 ====================

const tab = ref<'students' | 'assignments'>('students')
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)
const showChat = ref(false)

function showToast(msg: string, type: 'success' | 'error' = 'success') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 2500)
}

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

// ==================== 学生管理状态 ====================

const students = ref<Student[]>([])
const studentKeyword = ref('')
const studentModal = ref<'add' | 'edit' | null>(null)
const editingStudent = ref<Student | null>(null)
const studentForm = ref({
  username: '', full_name: '', major: '', is_part_time: false, is_active: true,
})

// 批量导入状态
const importModal = ref(false)
const importLoading = ref(false)
const importResult = ref<ImportResult | null>(null)

// [新增] 排序 + 专业筛选状态
const studentSortBy = ref<'created_at' | 'full_time_first' | 'part_time_first' | 'major'>('created_at')
const selectedFilterMajors = ref<string[]>([])
const showMajorFilter = ref(false)

// [新增] 学生作业情况弹窗状态
const studentAssignModal = ref(false)
const studentAssignData = ref<StudentAssignmentStatusResponse | null>(null)
const studentAssignLoading = ref(false)

// ==================== 专业列表（从后端加载） ====================

const majorsList = ref<string[]>([])

async function refreshMajors() {
  try {
    majorsList.value = await getMajors()
  } catch {
    // 静默失败，不影响主流程
  }
}

// ==================== [新增] 学生列表排序 + 筛选 computed ====================

const filteredAndSortedStudents = computed(() => {
  let list = [...students.value]

  // 专业筛选
  if (selectedFilterMajors.value.length > 0) {
    list = list.filter(s =>
      s.major && selectedFilterMajors.value.includes(s.major)
    )
  }

  // 排序
  switch (studentSortBy.value) {
    case 'full_time_first':
      list.sort((a, b) => {
        if (a.is_part_time === b.is_part_time) return 0
        return a.is_part_time ? 1 : -1
      })
      break
    case 'part_time_first':
      list.sort((a, b) => {
        if (a.is_part_time === b.is_part_time) return 0
        return a.is_part_time ? -1 : 1
      })
      break
    case 'major':
      list.sort((a, b) => {
        const ma = a.major || ''
        const mb = b.major || ''
        return ma.localeCompare(mb, 'zh-CN')
      })
      break
    case 'created_at':
    default:
      // 保持原始排序（后端已按 created_at desc）
      break
  }

  return list
})

// [新增] 切换专业筛选
function toggleFilterMajor(major: string) {
  const idx = selectedFilterMajors.value.indexOf(major)
  if (idx >= 0) {
    selectedFilterMajors.value.splice(idx, 1)
  } else {
    selectedFilterMajors.value.push(major)
  }
}

function clearMajorFilter() {
  selectedFilterMajors.value = []
}

// ==================== 学生管理逻辑 ====================

async function refreshStudents() {
  try {
    students.value = await getStudents(studentKeyword.value || undefined)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '获取学生列表失败', 'error')
  }
}

function openAddStudent() {
  studentForm.value = { username: '', full_name: '', major: '', is_part_time: false, is_active: true }
  studentModal.value = 'add'
}

function openEditStudent(s: Student) {
  editingStudent.value = s
  studentForm.value = {
    username: s.username,
    full_name: s.full_name,
    major: s.major || '',
    is_part_time: s.is_part_time,
    is_active: s.is_active,
  }
  studentModal.value = 'edit'
}

async function handleSaveStudent() {
  if (!studentForm.value.full_name.trim()) {
    showToast('请填写姓名', 'error')
    return
  }
  try {
    if (studentModal.value === 'add') {
      if (!studentForm.value.username.trim()) {
        showToast('请填写学号', 'error')
        return
      }
      await createStudent({
        username: studentForm.value.username.trim(),
        full_name: studentForm.value.full_name.trim(),
        major: studentForm.value.major || undefined,
        is_part_time: studentForm.value.is_part_time,
      })
      showToast('学生录入成功')
    } else if (editingStudent.value) {
      await updateStudent(editingStudent.value.id, {
        full_name: studentForm.value.full_name.trim(),
        major: studentForm.value.major || null,
        is_part_time: studentForm.value.is_part_time,
        is_active: studentForm.value.is_active,
      })
      showToast('学生信息已更新')
    }
    studentModal.value = null
    refreshStudents()
    refreshMajors()  // 刷新专业列表
  } catch (err) {
    showToast(err instanceof Error ? err.message : '操作失败', 'error')
  }
}

async function handleDeleteStudent(s: Student) {
  if (confirm(`确定删除学生 ${s.full_name}（${s.username}）吗？此操作不可逆。`)) {
    try {
      await deleteStudent(s.id)
      showToast('学生已删除')
      refreshStudents()
    } catch (err) {
      showToast(err instanceof Error ? err.message : '删除失败', 'error')
    }
  }
}

// [新增] 重置学生密码
async function handleResetPassword(s: Student) {
  if (confirm(`确定将学生 ${s.full_name}（${s.username}）的密码重置为 123456 吗？`)) {
    try {
      await resetStudentPassword(s.id)
      showToast(`${s.full_name} 的密码已重置为 123456`)
    } catch (err) {
      showToast(err instanceof Error ? err.message : '重置密码失败', 'error')
    }
  }
}

// [新增] 点击学生行查看作业情况
async function handleClickStudent(s: Student) {
  studentAssignLoading.value = true
  studentAssignData.value = null
  studentAssignModal.value = true
  try {
    studentAssignData.value = await getStudentAssignmentStatus(s.id)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '获取学生作业情况失败', 'error')
    studentAssignModal.value = false
  } finally {
    studentAssignLoading.value = false
  }
}

// ==================== 批量导入逻辑 ====================

function openImportModal() {
  importResult.value = null
  importModal.value = true
}

async function handleImportFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  importLoading.value = true
  importResult.value = null

  try {
    importResult.value = await importStudents(file)
    showToast(importResult.value.message)
    refreshStudents()
    refreshMajors()
  } catch (err) {
    showToast(err instanceof Error ? err.message : '导入失败', 'error')
  } finally {
    importLoading.value = false
    input.value = ''
  }
}

// ==================== 作业管理状态 ====================

const assignments = ref<AssignmentItem[]>([])
const subCounts = ref<Record<number, number>>({})
const assignModal = ref<'add' | 'edit' | 'subs' | null>(null)
const editingAssign = ref<AssignmentItem | null>(null)
const subs = ref<SubmissionItem[]>([])
const subsTitle = ref('')
const subsAssignmentId = ref<number | null>(null)
const assignForm = ref({
  course_name: '',
  title: '',
  description: '',
  deadline: '',
  allowed_extensions: '.pdf,.zip',
  target_majors: [] as string[],
  target_is_part_time: null as boolean | null,
})

// [新增] 作业提交统计弹窗状态
const submitStatsModal = ref(false)
const submitStatsData = ref<AssignmentSubmitStatsResponse | null>(null)
const submitStatsLoading = ref(false)
const submitStatsTitle = ref('')
const showSubmittedList = ref(false)
const showNotSubmittedList = ref(false)

// ==================== 作业管理逻辑 ====================

async function refreshAssignments() {
  try {
    const data = await getAssignments()
    assignments.value = data
    // 批量获取提交数量
    const counts: Record<number, number> = {}
    await Promise.all(
      data.map(async (a) => {
        try {
          const submissions = await getSubmissions(a.id)
          counts[a.id] = submissions.length
        } catch {
          counts[a.id] = 0
        }
      })
    )
    subCounts.value = counts
  } catch (err) {
    showToast(err instanceof Error ? err.message : '获取作业列表失败', 'error')
  }
}

function openAddAssign() {
  const defaultDate = new Date(Date.now() + 7 * 24 * 3600000)
  assignForm.value = {
    course_name: '', title: '', description: '',
    deadline: defaultDate.toISOString().slice(0, 16),
    allowed_extensions: '.pdf,.zip',
    target_majors: [],
    target_is_part_time: null,
  }
  assignModal.value = 'add'
}

function openEditAssign(a: AssignmentItem) {
  editingAssign.value = a
  assignForm.value = {
    course_name: a.course_name,
    title: a.title,
    description: a.description,
    deadline: a.deadline.slice(0, 16),
    allowed_extensions: a.allowed_extensions,
    target_majors: a.target_majors ?? [],
    target_is_part_time: a.target_is_part_time ?? null,
  }
  assignModal.value = 'edit'
}

async function openSubs(a: AssignmentItem) {
  subsTitle.value = `${a.course_name} — ${a.title}`
  subsAssignmentId.value = a.id
  try {
    subs.value = await getSubmissions(a.id)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '获取提交记录失败', 'error')
    subs.value = []
  }
  assignModal.value = 'subs'
}

function handleDownload(a: AssignmentItem) {
  downloadSubmissions(a.id)
}

async function handleSaveAssign() {
  const f = assignForm.value
  if (!f.course_name.trim() || !f.title.trim() || !f.description.trim() || !f.deadline) {
    showToast('请填写所有必填字段', 'error')
    return
  }
  try {
    // 构造请求数据，空数组表示面向所有专业
    const targetMajors = f.target_majors.length > 0 ? f.target_majors : null

    if (assignModal.value === 'add') {
      await createAssignment({
        course_name: f.course_name.trim(),
        title: f.title.trim(),
        description: f.description.trim(),
        deadline: new Date(f.deadline).toISOString(),
        allowed_extensions: f.allowed_extensions.trim(),
        target_majors: targetMajors,
        target_is_part_time: f.target_is_part_time,
      })
      showToast('作业发布成功')
    } else if (editingAssign.value) {
      await updateAssignment(editingAssign.value.id, {
        course_name: f.course_name.trim(),
        title: f.title.trim(),
        description: f.description.trim(),
        deadline: new Date(f.deadline).toISOString(),
        allowed_extensions: f.allowed_extensions.trim(),
        target_majors: targetMajors,
        target_is_part_time: f.target_is_part_time,
      })
      showToast('作业已更新')
    }
    assignModal.value = null
    refreshAssignments()
  } catch (err) {
    showToast(err instanceof Error ? err.message : '操作失败', 'error')
  }
}

async function handleDelAssign(a: AssignmentItem) {
  if (confirm(`确定删除作业「${a.title}」吗？此操作不可逆。`)) {
    try {
      await deleteAssignment(a.id)
      showToast('作业已删除')
      refreshAssignments()
    } catch (err) {
      showToast(err instanceof Error ? err.message : '删除失败', 'error')
    }
  }
}

// [新增] 点击作业行查看提交统计
async function handleClickAssignment(a: AssignmentItem) {
  submitStatsTitle.value = `${a.course_name} — ${a.title}`
  submitStatsLoading.value = true
  submitStatsData.value = null
  showSubmittedList.value = false
  showNotSubmittedList.value = false
  submitStatsModal.value = true
  try {
    submitStatsData.value = await getAssignmentSubmitStats(a.id)
  } catch (err) {
    showToast(err instanceof Error ? err.message : '获取提交统计失败', 'error')
    submitStatsModal.value = false
  } finally {
    submitStatsLoading.value = false
  }
}

// ==================== 专业多选辅助 ====================

function toggleMajor(major: string) {
  const idx = assignForm.value.target_majors.indexOf(major)
  if (idx >= 0) {
    assignForm.value.target_majors.splice(idx, 1)
  } else {
    assignForm.value.target_majors.push(major)
  }
}

// ==================== 工具函数 ====================

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

/** 获取学习类型标签文案 */
function getStudyTypeLabel(val: boolean | null | undefined): string {
  if (val === null || val === undefined) return '全部学生'
  return val ? '仅非全日制' : '仅全日制'
}

/** 获取目标专业展示文案 */
function getTargetMajorsLabel(majors: string[] | null | undefined): string {
  if (!majors || majors.length === 0) return '所有专业'
  return majors.join('、')
}

// ==================== 初始化 ====================

onMounted(() => {
  refreshStudents()
  refreshAssignments()
  refreshMajors()
})
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Toast -->
    <Transition name="fade">
      <div
        v-if="toast"
        :class="[
          'fixed top-4 right-4 z-[60] flex items-center gap-2 px-4 py-3 rounded-xl shadow-lg text-sm font-medium',
          toast.type === 'success' ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'
        ]"
      >
        <CheckCircle2 v-if="toast.type === 'success'" :size="16" />
        <AlertTriangle v-else :size="16" />
        {{ toast.msg }}
      </div>
    </Transition>

    <!-- 顶部导航 -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div class="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="p-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
            <BookOpen :size="18" class="text-white" />
          </div>
          <span class="font-bold text-slate-800">AI 智能作业管理系统</span>
          <span class="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">教师端</span>
        </div>
        <div class="flex items-center gap-4">
          <button @click="showChat = !showChat" class="flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-500 cursor-pointer">
            <MessageCircle :size="14" /><span>AI 助手</span>
          </button>
          <span class="text-sm text-slate-600">👨‍🏫 {{ auth.user?.full_name }}</span>
          <button @click="handleLogout" class="flex items-center gap-1 text-sm text-slate-500 hover:text-red-500 cursor-pointer">
            <LogOut :size="14" /><span>退出</span>
          </button>
        </div>
      </div>
    </header>

    <!-- Tab 导航 -->
    <div class="bg-white border-b border-slate-200">
      <div class="max-w-7xl mx-auto px-6 flex gap-1">
        <button
          @click="tab = 'students'"
          :class="[
            'flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition cursor-pointer',
            tab === 'students'
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          ]"
        >
          <Users :size="16" />学生管理
        </button>
        <button
          @click="tab = 'assignments'"
          :class="[
            'flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition cursor-pointer',
            tab === 'assignments'
              ? 'border-indigo-500 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          ]"
        >
          <FileText :size="16" />作业管理
        </button>
      </div>
    </div>

    <!-- ==================== 内容区 ==================== -->
    <main class="max-w-7xl mx-auto px-6 py-6">

      <!-- ========== 学生管理面板 ========== -->
      <div v-if="tab === 'students'">
        <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div class="flex items-center gap-3 flex-wrap">
            <!-- 搜索框 -->
            <div class="relative">
              <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="studentKeyword"
                @input="refreshStudents"
                placeholder="搜索学号或姓名..."
                class="pl-9 pr-4 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-56"
              />
            </div>

            <!-- [新增] 排序下拉 -->
            <div class="relative">
              <div class="flex items-center gap-1.5 px-3 py-2 border border-slate-300 rounded-xl text-sm bg-white">
                <ArrowUpDown :size="14" class="text-slate-400" />
                <select
                  v-model="studentSortBy"
                  class="bg-transparent outline-none text-slate-700 cursor-pointer pr-1"
                >
                  <option value="created_at">录入时间</option>
                  <option value="full_time_first">全日制优先</option>
                  <option value="part_time_first">非全日制优先</option>
                  <option value="major">按专业排序</option>
                </select>
              </div>
            </div>

            <!-- [新增] 专业筛选下拉 -->
            <div class="relative">
              <button
                @click="showMajorFilter = !showMajorFilter"
                :class="[
                  'flex items-center gap-1.5 px-3 py-2 border rounded-xl text-sm cursor-pointer transition',
                  selectedFilterMajors.length > 0
                    ? 'border-indigo-400 bg-indigo-50 text-indigo-700'
                    : 'border-slate-300 bg-white text-slate-700'
                ]"
              >
                <Filter :size="14" />
                <span v-if="selectedFilterMajors.length === 0">专业筛选</span>
                <span v-else>已选 {{ selectedFilterMajors.length }} 个专业</span>
                <ChevronDown :size="14" />
              </button>
              <!-- 下拉面板 -->
              <div
                v-if="showMajorFilter"
                class="absolute top-full left-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-lg z-20 p-3 min-w-[200px]"
              >
                <div v-if="majorsList.length === 0" class="text-xs text-slate-400 py-2">暂无专业数据</div>
                <div v-else class="space-y-1.5 max-h-48 overflow-y-auto">
                  <label
                    v-for="m in majorsList"
                    :key="m"
                    class="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-slate-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      :checked="selectedFilterMajors.includes(m)"
                      @change="toggleFilterMajor(m)"
                      class="w-3.5 h-3.5 rounded border-slate-300 text-indigo-500 focus:ring-indigo-500"
                    />
                    <span class="text-sm text-slate-700">{{ m }}</span>
                  </label>
                </div>
                <div class="flex justify-between items-center mt-2 pt-2 border-t border-slate-100">
                  <button @click="clearMajorFilter" class="text-xs text-slate-500 hover:text-indigo-500 cursor-pointer">清除筛选</button>
                  <button @click="showMajorFilter = false" class="text-xs text-indigo-600 font-medium cursor-pointer">确定</button>
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <!-- 批量导入按钮 -->
            <button @click="openImportModal" class="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-sm font-medium cursor-pointer transition">
              <Upload :size="16" />批量导入
            </button>
            <button @click="openAddStudent" class="flex items-center gap-1.5 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-medium cursor-pointer transition">
              <Plus :size="16" />录入学生
            </button>
          </div>
        </div>

        <!-- 学生列表表格 -->
        <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 text-slate-600">
              <tr>
                <th class="text-center px-3 py-3 font-medium w-14">序号</th>
                <th class="text-left px-4 py-3 font-medium">学号</th>
                <th class="text-left px-4 py-3 font-medium">姓名</th>
                <th class="text-left px-4 py-3 font-medium">专业</th>
                <th class="text-center px-4 py-3 font-medium">类型</th>
                <th class="text-center px-4 py-3 font-medium">状态</th>
                <th class="text-center px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr
                v-for="(s, index) in filteredAndSortedStudents"
                :key="s.id"
                class="hover:bg-indigo-50/30 cursor-pointer transition"
                @click="handleClickStudent(s)"
              >
                <td class="px-3 py-3 text-center text-slate-400 text-xs">{{ index + 1 }}</td>
                <td class="px-4 py-3 font-mono text-indigo-600">{{ s.username }}</td>
                <td class="px-4 py-3 font-medium text-slate-800">{{ s.full_name }}</td>
                <td class="px-4 py-3 text-slate-600">{{ s.major || '—' }}</td>
                <td class="px-4 py-3 text-center">
                  <span :class="['px-2 py-0.5 rounded-full text-xs', s.is_part_time ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700']">
                    {{ s.is_part_time ? '非全日制' : '全日制' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span v-if="s.is_active" class="inline-flex items-center gap-1 text-emerald-600 text-xs"><UserCheck :size="12" />启用</span>
                  <span v-else class="inline-flex items-center gap-1 text-red-500 text-xs"><UserX :size="12" />停用</span>
                </td>
                <td class="px-4 py-3 text-center" @click.stop>
                  <div class="flex items-center justify-center gap-2">
                    <button @click="openEditStudent(s)" class="p-1.5 hover:bg-indigo-50 text-indigo-500 rounded-lg cursor-pointer" title="编辑">
                      <Pencil :size="14" />
                    </button>
                    <button @click="handleResetPassword(s)" class="p-1.5 hover:bg-amber-50 text-amber-500 rounded-lg cursor-pointer" title="重置密码">
                      <KeyRound :size="14" />
                    </button>
                    <button @click="handleDeleteStudent(s)" class="p-1.5 hover:bg-red-50 text-red-500 rounded-lg cursor-pointer" title="删除">
                      <Trash2 :size="14" />
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="filteredAndSortedStudents.length === 0">
                <td colspan="7" class="px-4 py-12 text-center text-slate-400">暂无学生数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 学生录入/编辑模态框 -->
        <Teleport to="body">
          <div
            v-if="studentModal"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            @click="studentModal = null"
          >
            <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
              <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <h3 class="text-lg font-bold text-slate-800">{{ studentModal === 'add' ? '录入新学生' : '编辑学生信息' }}</h3>
                <button @click="studentModal = null" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X :size="20" /></button>
              </div>
              <div class="p-6 space-y-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">学号 *</label>
                  <input v-model="studentForm.username" :disabled="studentModal === 'edit'" placeholder="如 2024006"
                    class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">姓名 *</label>
                  <input v-model="studentForm.full_name" placeholder="学生真实姓名"
                    class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">专业</label>
                  <input v-model="studentForm.major" placeholder="如 计算机科学与技术"
                    class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
                <div class="flex items-center gap-6">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" v-model="studentForm.is_part_time"
                      class="w-4 h-4 rounded border-slate-300 text-indigo-500 focus:ring-indigo-500" />
                    <span class="text-sm text-slate-700">非全日制</span>
                  </label>
                  <label v-if="studentModal === 'edit'" class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" v-model="studentForm.is_active"
                      class="w-4 h-4 rounded border-slate-300 text-indigo-500 focus:ring-indigo-500" />
                    <span class="text-sm text-slate-700">启用账号</span>
                  </label>
                </div>
                <p v-if="studentModal === 'add'" class="text-xs text-slate-400">💡 系统将自动生成默认密码：123456</p>
                <div class="flex justify-end gap-3 pt-2">
                  <button @click="studentModal = null" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer">取消</button>
                  <button @click="handleSaveStudent" class="px-4 py-2 text-sm bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl cursor-pointer font-medium">
                    {{ studentModal === 'add' ? '录入' : '保存' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Teleport>

        <!-- ==================== 批量导入模态框 ==================== -->
        <Teleport to="body">
          <div
            v-if="importModal"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            @click="importModal = false"
          >
            <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
              <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <h3 class="text-lg font-bold text-slate-800">批量导入学生</h3>
                <button @click="importModal = false" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X :size="20" /></button>
              </div>
              <div class="p-6">
                <!-- Excel 格式说明 -->
                <div class="bg-blue-50 rounded-xl p-4 mb-4">
                  <p class="text-sm font-medium text-blue-800 mb-2">📋 Excel 格式要求</p>
                  <p class="text-xs text-blue-700">第一行为表头，从第二行开始填写学生数据：</p>
                  <div class="mt-2 bg-white rounded-lg p-3 overflow-x-auto">
                    <table class="text-xs text-slate-600 w-full">
                      <thead>
                        <tr class="border-b border-slate-200">
                          <th class="text-left py-1 px-2 font-medium">学号</th>
                          <th class="text-left py-1 px-2 font-medium">姓名</th>
                          <th class="text-left py-1 px-2 font-medium">专业</th>
                          <th class="text-left py-1 px-2 font-medium">是否非全日制</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr class="text-slate-500">
                          <td class="py-1 px-2">2024001</td>
                          <td class="py-1 px-2">张三</td>
                          <td class="py-1 px-2">软件工程</td>
                          <td class="py-1 px-2">否</td>
                        </tr>
                        <tr class="text-slate-500">
                          <td class="py-1 px-2">2024002</td>
                          <td class="py-1 px-2">李四</td>
                          <td class="py-1 px-2">计算机科学</td>
                          <td class="py-1 px-2">是</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <p class="text-xs text-blue-600 mt-2">💡 "是否非全日制"填"是"或"否"，不填默认为全日制</p>
                </div>

                <!-- 上传区域 -->
                <div class="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-emerald-400 transition">
                  <Upload :size="32" class="mx-auto text-slate-400 mb-3" />
                  <p class="text-sm text-slate-600 mb-1">点击选择 Excel 文件</p>
                  <p class="text-xs text-slate-400">仅支持 .xlsx 格式</p>
                  <label class="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-sm font-medium cursor-pointer transition">
                    <Upload :size="14" />
                    {{ importLoading ? '导入中...' : '选择文件并导入' }}
                    <input
                      type="file"
                      class="hidden"
                      accept=".xlsx,.xls"
                      :disabled="importLoading"
                      @change="handleImportFile"
                    />
                  </label>
                </div>

                <!-- 导入结果 -->
                <div v-if="importResult" class="mt-4">
                  <div class="flex items-center gap-4 mb-3">
                    <div class="flex items-center gap-1.5 text-sm">
                      <CheckCircle2 :size="14" class="text-emerald-500" />
                      <span class="text-emerald-700 font-medium">成功 {{ importResult.success_count }} 条</span>
                    </div>
                    <div v-if="importResult.fail_count > 0" class="flex items-center gap-1.5 text-sm">
                      <AlertTriangle :size="14" class="text-red-500" />
                      <span class="text-red-600 font-medium">失败 {{ importResult.fail_count }} 条</span>
                    </div>
                  </div>

                  <!-- 失败详情 -->
                  <div v-if="importResult.fail_details.length > 0" class="bg-red-50 rounded-xl p-3 max-h-40 overflow-y-auto">
                    <p class="text-xs font-medium text-red-700 mb-2">失败详情：</p>
                    <div v-for="(item, idx) in importResult.fail_details" :key="idx" class="text-xs text-red-600 py-0.5">
                      第 {{ item.row }} 行（{{ item.username }}）：{{ item.reason }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Teleport>

        <!-- ==================== [新增] 学生作业情况弹窗 ==================== -->
        <Teleport to="body">
          <div
            v-if="studentAssignModal"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            @click="studentAssignModal = false"
          >
            <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
              <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <h3 class="text-lg font-bold text-slate-800">
                  <template v-if="studentAssignData">
                    {{ studentAssignData.full_name }}（{{ studentAssignData.username }}）的作业情况
                  </template>
                  <template v-else>加载中...</template>
                </h3>
                <button @click="studentAssignModal = false" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X :size="20" /></button>
              </div>
              <div class="p-6">
                <!-- Loading -->
                <div v-if="studentAssignLoading" class="text-center py-8 text-slate-400">加载中...</div>

                <template v-else-if="studentAssignData">
                  <!-- 统计栏 -->
                  <div class="grid grid-cols-3 gap-3 mb-4">
                    <div class="bg-amber-50 rounded-xl p-3 text-center">
                      <p class="text-2xl font-bold text-amber-600">
                        {{ studentAssignData.assignments.filter(a => a.status === '未交').length }}
                      </p>
                      <p class="text-xs text-amber-500 mt-0.5">待交</p>
                    </div>
                    <div class="bg-emerald-50 rounded-xl p-3 text-center">
                      <p class="text-2xl font-bold text-emerald-600">
                        {{ studentAssignData.assignments.filter(a => a.status === '已交').length }}
                      </p>
                      <p class="text-xs text-emerald-500 mt-0.5">已交</p>
                    </div>
                    <div class="bg-red-50 rounded-xl p-3 text-center">
                      <p class="text-2xl font-bold text-red-500">
                        {{ studentAssignData.assignments.filter(a => a.status === '已截止').length }}
                      </p>
                      <p class="text-xs text-red-400 mt-0.5">已截止</p>
                    </div>
                  </div>

                  <!-- 作业列表 -->
                  <div v-if="studentAssignData.assignments.length === 0" class="text-center py-6 text-slate-400 text-sm">
                    暂无可见作业
                  </div>
                  <div v-else class="space-y-2">
                    <div
                      v-for="a in studentAssignData.assignments"
                      :key="a.id"
                      class="flex items-center justify-between px-4 py-3 bg-slate-50 rounded-xl"
                    >
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                          <span class="text-xs bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">{{ a.course_name }}</span>
                          <span class="text-sm font-medium text-slate-800 truncate">{{ a.title }}</span>
                        </div>
                        <p class="text-xs text-slate-400 mt-0.5">截止：{{ a.deadline }}</p>
                      </div>
                      <span :class="[
                        'px-2.5 py-1 rounded-full text-xs font-medium ml-3 whitespace-nowrap',
                        a.status === '已交' ? 'bg-emerald-100 text-emerald-700' :
                        a.status === '未交' ? 'bg-amber-100 text-amber-700' :
                        'bg-red-100 text-red-600'
                      ]">
                        {{ a.status }}
                      </span>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </Teleport>
      </div>

      <!-- ========== 作业管理面板 ========== -->
      <div v-if="tab === 'assignments'">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-slate-800 flex items-center gap-2">
            <FileText :size="20" class="text-indigo-500" />
            作业列表（{{ assignments.length }}）
          </h2>
          <button @click="openAddAssign" class="flex items-center gap-1.5 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-medium cursor-pointer transition">
            <Plus :size="16" />发布作业
          </button>
        </div>

        <div class="grid gap-4">
          <div
            v-for="a in assignments"
            :key="a.id"
            class="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition cursor-pointer"
            @click="handleClickAssignment(a)"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1 flex-wrap">
                  <span class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">{{ a.course_name }}</span>
                  <span v-if="new Date(a.deadline) < new Date()" class="px-2 py-0.5 bg-red-100 text-red-600 rounded-full text-xs">已截止</span>
                  <!-- 目标专业标签 -->
                  <span v-if="a.target_majors && a.target_majors.length > 0"
                    class="px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs flex items-center gap-0.5"
                    :title="'面向专业：' + a.target_majors.join('、')"
                  >
                    <Target :size="10" />{{ a.target_majors.length }}个专业
                  </span>
                  <span v-else class="px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full text-xs">所有专业</span>
                  <!-- 学习类型标签 -->
                  <span v-if="a.target_is_part_time === false" class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs">仅全日制</span>
                  <span v-else-if="a.target_is_part_time === true" class="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs">仅非全日制</span>
                </div>
                <h3 class="text-base font-bold text-slate-800 mt-1">{{ a.title }}</h3>
                <p class="text-sm text-slate-500 mt-1 line-clamp-2">{{ a.description }}</p>
                <div class="flex items-center gap-4 mt-3 text-xs text-slate-500 flex-wrap">
                  <span class="flex items-center gap-1"><Calendar :size="12" />截止：{{ formatDate(a.deadline) }}</span>
                  <span class="flex items-center gap-1"><FileText :size="12" />格式：{{ a.allowed_extensions }}</span>
                  <span class="flex items-center gap-1"><GraduationCap :size="12" />已交：{{ subCounts[a.id] ?? 0 }} 人</span>
                </div>
              </div>
              <div class="flex items-center gap-1 ml-4" @click.stop>
                <button @click="openSubs(a)" class="p-2 hover:bg-blue-50 text-blue-500 rounded-lg cursor-pointer" title="查看提交">
                  <Eye :size="16" />
                </button>
                <button @click="handleDownload(a)" class="p-2 hover:bg-emerald-50 text-emerald-500 rounded-lg cursor-pointer" title="打包下载">
                  <Download :size="16" />
                </button>
                <button @click="openEditAssign(a)" class="p-2 hover:bg-indigo-50 text-indigo-500 rounded-lg cursor-pointer" title="编辑">
                  <Pencil :size="16" />
                </button>
                <button @click="handleDelAssign(a)" class="p-2 hover:bg-red-50 text-red-500 rounded-lg cursor-pointer" title="删除">
                  <Trash2 :size="16" />
                </button>
              </div>
            </div>
          </div>
          <div v-if="assignments.length === 0" class="text-center py-12 text-slate-400">
            暂无作业，点击右上角发布第一个作业
          </div>
        </div>

        <!-- ==================== 发布/编辑作业模态框 ==================== -->
        <Teleport to="body">
          <div
            v-if="assignModal === 'add' || assignModal === 'edit'"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            @click="assignModal = null"
          >
            <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
              <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <h3 class="text-lg font-bold text-slate-800">{{ assignModal === 'add' ? '发布新作业' : '编辑作业' }}</h3>
                <button @click="assignModal = null" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X :size="20" /></button>
              </div>
              <div class="p-6 space-y-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">课程名称 *</label>
                  <input v-model="assignForm.course_name" placeholder="如 数据库原理"
                    class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">作业标题 *</label>
                  <input v-model="assignForm.title" placeholder="如 第三次实验报告"
                    class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">作业要求 *</label>
                  <textarea v-model="assignForm.description" rows="4" placeholder="请详细描述作业要求..."
                    class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">截止时间 *</label>
                    <input type="datetime-local" v-model="assignForm.deadline"
                      class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">允许文件后缀 *</label>
                    <input v-model="assignForm.allowed_extensions" placeholder=".pdf,.zip,.docx"
                      class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                </div>

                <!-- ====== 目标专业选择 ====== -->
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">
                    <span class="flex items-center gap-1"><Target :size="14" />面向专业</span>
                  </label>
                  <p class="text-xs text-slate-400 mb-2">不选择任何专业则面向所有学生</p>
                  <div v-if="majorsList.length > 0" class="flex flex-wrap gap-2">
                    <button
                      v-for="m in majorsList"
                      :key="m"
                      @click="toggleMajor(m)"
                      :class="[
                        'px-3 py-1.5 rounded-lg text-xs font-medium border transition cursor-pointer',
                        assignForm.target_majors.includes(m)
                          ? 'bg-indigo-500 text-white border-indigo-500'
                          : 'bg-white text-slate-600 border-slate-300 hover:border-indigo-300'
                      ]"
                    >
                      {{ m }}
                    </button>
                  </div>
                  <p v-else class="text-xs text-slate-400">暂无专业数据（请先录入学生并设置专业）</p>
                  <p v-if="assignForm.target_majors.length > 0" class="text-xs text-indigo-600 mt-1.5">
                    已选 {{ assignForm.target_majors.length }} 个专业：{{ assignForm.target_majors.join('、') }}
                  </p>
                </div>

                <!-- ====== 目标学习类型 ====== -->
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-1">面向学习类型</label>
                  <div class="flex items-center gap-4">
                    <label class="flex items-center gap-1.5 cursor-pointer">
                      <input type="radio" name="studyType" :checked="assignForm.target_is_part_time === null"
                        @change="assignForm.target_is_part_time = null"
                        class="w-4 h-4 text-indigo-500 focus:ring-indigo-500" />
                      <span class="text-sm text-slate-700">全部学生</span>
                    </label>
                    <label class="flex items-center gap-1.5 cursor-pointer">
                      <input type="radio" name="studyType" :checked="assignForm.target_is_part_time === false"
                        @change="assignForm.target_is_part_time = false"
                        class="w-4 h-4 text-indigo-500 focus:ring-indigo-500" />
                      <span class="text-sm text-slate-700">仅全日制</span>
                    </label>
                    <label class="flex items-center gap-1.5 cursor-pointer">
                      <input type="radio" name="studyType" :checked="assignForm.target_is_part_time === true"
                        @change="assignForm.target_is_part_time = true"
                        class="w-4 h-4 text-indigo-500 focus:ring-indigo-500" />
                      <span class="text-sm text-slate-700">仅非全日制</span>
                    </label>
                  </div>
                </div>

                <div class="flex justify-end gap-3 pt-2">
                  <button @click="assignModal = null" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer">取消</button>
                  <button @click="handleSaveAssign" class="px-4 py-2 text-sm bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl cursor-pointer font-medium">
                    {{ assignModal === 'add' ? '发布' : '保存' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Teleport>

        <!-- ==================== 提交记录模态框 ==================== -->
        <Teleport to="body">
          <div
            v-if="assignModal === 'subs'"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            @click="assignModal = null"
          >
            <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
              <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <h3 class="text-lg font-bold text-slate-800">提交情况 — {{ subsTitle }}</h3>
                <button @click="assignModal = null" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X :size="20" /></button>
              </div>
              <div class="p-6">
                <div v-if="subs.length === 0" class="text-center py-8 text-slate-400">暂无学生提交</div>
                <div v-else class="space-y-3">
                  <p class="text-sm text-slate-600 mb-3">共 {{ subs.length }} 人已提交</p>
                  <div v-for="s in subs" :key="s.id" class="flex items-center gap-3 px-4 py-3 bg-slate-50 rounded-xl">
                    <div class="w-8 h-8 bg-indigo-100 rounded-lg flex items-center justify-center text-indigo-600 text-xs font-bold">
                      {{ s.student_name[0] }}
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <span class="font-medium text-sm text-slate-800">{{ s.student_name }}</span>
                        <span class="text-xs text-slate-400">{{ s.student_username }}</span>
                        <span v-if="s.is_part_time" class="text-xs bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded">非全</span>
                      </div>
                      <div class="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                        <span>{{ s.major || '—' }}</span>
                        <span>·</span>
                        <span class="flex items-center gap-1"><Clock :size="10" />{{ formatDate(s.submitted_at) }}</span>
                      </div>
                    </div>
                    <CheckCircle2 :size="16" class="text-emerald-500" />
                  </div>
                  <button
                    @click="subsAssignmentId !== null && downloadSubmissions(subsAssignmentId)"
                    class="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-sm font-medium cursor-pointer transition"
                  >
                    <Download :size="16" />打包下载所有文件 (.zip)
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Teleport>

        <!-- ==================== [新增] 作业提交统计弹窗 ==================== -->
        <Teleport to="body">
          <div
            v-if="submitStatsModal"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            @click="submitStatsModal = false"
          >
            <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" @click.stop>
              <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
                <h3 class="text-lg font-bold text-slate-800">提交统计 — {{ submitStatsTitle }}</h3>
                <button @click="submitStatsModal = false" class="text-slate-400 hover:text-slate-600 cursor-pointer"><X :size="20" /></button>
              </div>
              <div class="p-6">
                <!-- Loading -->
                <div v-if="submitStatsLoading" class="text-center py-8 text-slate-400">加载中...</div>

                <template v-else-if="submitStatsData">
                  <!-- 统计栏 -->
                  <div class="grid grid-cols-3 gap-3 mb-5">
                    <div class="bg-slate-50 rounded-xl p-3 text-center">
                      <p class="text-2xl font-bold text-slate-700">{{ submitStatsData.total_should_submit }}</p>
                      <p class="text-xs text-slate-400 mt-0.5">应交</p>
                    </div>
                    <div class="bg-emerald-50 rounded-xl p-3 text-center">
                      <p class="text-2xl font-bold text-emerald-600">{{ submitStatsData.submitted_count }}</p>
                      <p class="text-xs text-emerald-500 mt-0.5">已交</p>
                    </div>
                    <div class="bg-red-50 rounded-xl p-3 text-center">
                      <p class="text-2xl font-bold text-red-500">{{ submitStatsData.not_submitted_count }}</p>
                      <p class="text-xs text-red-400 mt-0.5">未交</p>
                    </div>
                  </div>

                  <!-- 已交名单（可折叠） -->
                  <div class="mb-3">
                    <button
                      @click="showSubmittedList = !showSubmittedList"
                      class="w-full flex items-center justify-between px-4 py-2.5 bg-emerald-50 hover:bg-emerald-100 rounded-xl text-sm font-medium text-emerald-700 cursor-pointer transition"
                    >
                      <span class="flex items-center gap-1.5">
                        <CheckCircle2 :size="14" />
                        已交（{{ submitStatsData.submitted_count }} 人）
                      </span>
                      <component :is="showSubmittedList ? ChevronDown : ChevronRight" :size="16" />
                    </button>
                    <div v-if="showSubmittedList" class="mt-2 space-y-1.5 pl-2">
                      <div
                        v-for="s in submitStatsData.submitted_students"
                        :key="s.student_id"
                        class="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg text-sm"
                      >
                        <div class="flex items-center gap-2">
                          <span class="font-mono text-xs text-indigo-600">{{ s.username }}</span>
                          <span class="font-medium text-slate-800">{{ s.full_name }}</span>
                          <span class="text-xs text-slate-400">{{ s.major || '—' }}</span>
                          <span v-if="s.is_part_time" class="text-xs bg-amber-100 text-amber-600 px-1 py-0.5 rounded">非全</span>
                        </div>
                        <span class="text-xs text-slate-400">{{ s.submitted_at }}</span>
                      </div>
                      <div v-if="submitStatsData.submitted_students.length === 0" class="text-center py-3 text-xs text-slate-400">
                        暂无提交记录
                      </div>
                    </div>
                  </div>

                  <!-- 未交名单（可折叠） -->
                  <div>
                    <button
                      @click="showNotSubmittedList = !showNotSubmittedList"
                      class="w-full flex items-center justify-between px-4 py-2.5 bg-red-50 hover:bg-red-100 rounded-xl text-sm font-medium text-red-600 cursor-pointer transition"
                    >
                      <span class="flex items-center gap-1.5">
                        <AlertTriangle :size="14" />
                        未交（{{ submitStatsData.not_submitted_count }} 人）
                      </span>
                      <component :is="showNotSubmittedList ? ChevronDown : ChevronRight" :size="16" />
                    </button>
                    <div v-if="showNotSubmittedList" class="mt-2 space-y-1.5 pl-2">
                      <div
                        v-for="s in submitStatsData.not_submitted_students"
                        :key="s.student_id"
                        class="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg text-sm"
                      >
                        <span class="font-mono text-xs text-indigo-600">{{ s.username }}</span>
                        <span class="font-medium text-slate-800">{{ s.full_name }}</span>
                        <span class="text-xs text-slate-400">{{ s.major || '—' }}</span>
                        <span v-if="s.is_part_time" class="text-xs bg-amber-100 text-amber-600 px-1 py-0.5 rounded">非全</span>
                      </div>
                      <div v-if="submitStatsData.not_submitted_students.length === 0" class="text-center py-3 text-xs text-slate-400">
                        全部已交 🎉
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </Teleport>
      </div>
    </main>

    <!-- 点击外部关闭专业筛选下拉 -->
    <div v-if="showMajorFilter" class="fixed inset-0 z-10" @click="showMajorFilter = false"></div>

    <!-- AI 对话面板 -->
    <ChatBox v-if="showChat" @close="showChat = false" />
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
