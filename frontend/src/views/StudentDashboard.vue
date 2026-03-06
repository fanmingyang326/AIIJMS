<!-- ============================================================
  学生 Dashboard (StudentDashboard.vue)
  功能：
    1. 作业列表展示（含动态状态：未交/已交/已截止）
    2. 文件上传提交（两步确认流程）
    3. 作业详情查看
    4. 修改密码
    5. AI 对话入口
  改动：
    [需求3] 统计卡片可点击筛选 + 作业行整行可点击
    [需求4] 文件上传改为两步：选文件 → 确认提交
============================================================ -->

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  BookOpen, LogOut, Upload, FileText, Calendar, Clock, CheckCircle2,
  AlertTriangle, XCircle, Eye, X, Lock, User, MessageCircle, Loader2, RotateCcw
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import {
  getStudentAssignments, submitAssignment, changePassword,
  type AssignmentItem
} from '@/api/client'
import ChatBox from '@/components/ChatBox.vue'

const router = useRouter()
const auth = useAuthStore()

// ==================== 响应式状态 ====================

const assignments = ref<AssignmentItem[]>([])
const selected = ref<AssignmentItem | null>(null)      // 详情弹窗
const uploadTarget = ref<AssignmentItem | null>(null)   // 上传弹窗
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)
const pwdModal = ref(false)
const showChat = ref(false)   // AI 对话面板

// 密码修改表单
const pwdForm = ref({ oldPwd: '', newPwd: '' })

// [需求3] 状态筛选
const activeFilter = ref<string | null>(null)  // null=全部, '未交'/'已交'/'已截止'

// [需求4] 两步上传状态
const selectedFile = ref<File | null>(null)
const uploadLoading = ref(false)

// ==================== Toast 提示 ====================

function showToast(msg: string, type: 'success' | 'error' = 'success') {
  toast.value = { msg, type }
  setTimeout(() => { toast.value = null }, 3000)
}

// ==================== 数据加载 ====================

async function refresh() {
  if (!auth.user) return
  try {
    assignments.value = await getStudentAssignments()
  } catch (err) {
    showToast(err instanceof Error ? err.message : '获取作业列表失败', 'error')
  }
}

onMounted(refresh)

// ==================== 统计 ====================

const pending = computed(() => assignments.value.filter(a => a.status === '未交').length)
const done = computed(() => assignments.value.filter(a => a.status === '已交').length)
const expired = computed(() => assignments.value.filter(a => a.status === '已截止').length)

// [需求3] 筛选后的作业列表
const filteredAssignments = computed(() => {
  if (!activeFilter.value) return assignments.value
  return assignments.value.filter(a => a.status === activeFilter.value)
})

// [需求3] 点击统计卡片切换筛选
function toggleFilter(status: string) {
  if (activeFilter.value === status) {
    activeFilter.value = null  // 再次点击取消筛选
  } else {
    activeFilter.value = status
  }
}

// ==================== 登出 ====================

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

// ==================== [需求4] 两步文件上传 ====================

/** 步骤1：选择文件，仅存储到 ref，不立即上传 */
function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  selectedFile.value = file
  // 清空 input 以允许重复选择同一文件
  input.value = ''
}

/** 重新选择文件 */
function resetFileSelection() {
  selectedFile.value = null
}

/** 步骤2：确认提交 */
async function handleConfirmUpload() {
  if (!selectedFile.value || !uploadTarget.value || !auth.user) return

  uploadLoading.value = true
  try {
    await submitAssignment(uploadTarget.value.id, selectedFile.value)
    showToast(`文件「${selectedFile.value.name}」提交成功！`)
    uploadTarget.value = null
    selectedFile.value = null
    refresh()
  } catch (err) {
    showToast(err instanceof Error ? err.message : '提交失败', 'error')
  } finally {
    uploadLoading.value = false
  }
}

/** 关闭上传弹窗时清理状态 */
function closeUploadModal() {
  uploadTarget.value = null
  selectedFile.value = null
  uploadLoading.value = false
}

/** 格式化文件大小 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ==================== 修改密码 ====================

async function handleChangePwd() {
  if (!pwdForm.value.oldPwd || !pwdForm.value.newPwd) {
    showToast('请填写完整', 'error')
    return
  }
  if (pwdForm.value.newPwd.length < 6) {
    showToast('新密码至少 6 位', 'error')
    return
  }
  try {
    await changePassword(pwdForm.value.oldPwd, pwdForm.value.newPwd)
    showToast('密码修改成功')
    pwdModal.value = false
    pwdForm.value = { oldPwd: '', newPwd: '' }
  } catch (err) {
    showToast(err instanceof Error ? err.message : '密码修改失败', 'error')
  }
}

// ==================== 工具函数 ====================

/** 计算截止日期倒计时文案 */
function getTimeLeft(deadline: string) {
  const remaining = new Date(deadline).getTime() - Date.now()
  if (remaining <= 0) return ''
  const days = Math.floor(remaining / 86400000)
  const hours = Math.floor((remaining % 86400000) / 3600000)
  return days > 0 ? `还剩 ${days}天${hours}小时` : `还剩 ${hours}小时`
}

/** 是否紧急（距离截止不足 2 天） */
function isUrgent(deadline: string) {
  const remaining = new Date(deadline).getTime() - Date.now()
  return remaining > 0 && remaining < 2 * 86400000
}

/** 格式化日期 */
function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

// ==================== 状态徽章样式映射 ====================

const statusStyles: Record<string, string> = {
  '未交': 'bg-amber-100 text-amber-700 border-amber-200',
  '已交': 'bg-emerald-100 text-emerald-700 border-emerald-200',
  '已截止': 'bg-red-100 text-red-600 border-red-200',
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/20 to-violet-50/20">
    <!-- Toast 提示 -->
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
    <header class="bg-white/80 backdrop-blur-xl border-b border-slate-200/60 sticky top-0 z-40">
      <div class="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="p-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
            <BookOpen :size="18" class="text-white" />
          </div>
          <span class="font-bold text-slate-800">AI 智能作业管理系统</span>
          <span class="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">学生端</span>
        </div>
        <div class="flex items-center gap-4">
          <!-- AI 对话按钮 -->
          <button @click="showChat = !showChat" class="flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-500 cursor-pointer">
            <MessageCircle :size="14" /><span>AI 助手</span>
          </button>
          <button @click="pwdModal = true" class="flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-500 cursor-pointer">
            <Lock :size="14" /><span>改密</span>
          </button>
          <span class="text-sm text-slate-600 flex items-center gap-1">
            <User :size="14" />{{ auth.user?.full_name }}（{{ auth.user?.username }}）
          </span>
          <button @click="handleLogout" class="flex items-center gap-1 text-sm text-slate-500 hover:text-red-500 cursor-pointer">
            <LogOut :size="14" /><span>退出</span>
          </button>
        </div>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-6">
      <!-- [需求3] 统计卡片 — 可点击筛选 -->
      <div class="grid grid-cols-3 gap-4 mb-6">
        <div
          @click="toggleFilter('未交')"
          :class="[
            'rounded-xl p-4 text-white shadow-lg cursor-pointer transition-all',
            'bg-gradient-to-br from-amber-400 to-orange-500',
            activeFilter === '未交' ? 'ring-4 ring-amber-300 scale-[1.03]' : 'hover:scale-[1.01]'
          ]"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-white/80 text-sm">待提交</p>
              <p class="text-3xl font-bold mt-1">{{ pending }}</p>
            </div>
            <div class="p-2 bg-white/20 rounded-xl"><Clock :size="20" /></div>
          </div>
        </div>
        <div
          @click="toggleFilter('已交')"
          :class="[
            'rounded-xl p-4 text-white shadow-lg cursor-pointer transition-all',
            'bg-gradient-to-br from-emerald-400 to-teal-500',
            activeFilter === '已交' ? 'ring-4 ring-emerald-300 scale-[1.03]' : 'hover:scale-[1.01]'
          ]"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-white/80 text-sm">已提交</p>
              <p class="text-3xl font-bold mt-1">{{ done }}</p>
            </div>
            <div class="p-2 bg-white/20 rounded-xl"><CheckCircle2 :size="20" /></div>
          </div>
        </div>
        <div
          @click="toggleFilter('已截止')"
          :class="[
            'rounded-xl p-4 text-white shadow-lg cursor-pointer transition-all',
            'bg-gradient-to-br from-red-400 to-pink-500',
            activeFilter === '已截止' ? 'ring-4 ring-red-300 scale-[1.03]' : 'hover:scale-[1.01]'
          ]"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-white/80 text-sm">已截止</p>
              <p class="text-3xl font-bold mt-1">{{ expired }}</p>
            </div>
            <div class="p-2 bg-white/20 rounded-xl"><XCircle :size="20" /></div>
          </div>
        </div>
      </div>

      <!-- 筛选提示 -->
      <div v-if="activeFilter" class="mb-4 flex items-center gap-2">
        <span class="text-sm text-slate-500">当前筛选：</span>
        <span :class="[
          'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border',
          statusStyles[activeFilter] || 'bg-slate-100 text-slate-600'
        ]">
          {{ activeFilter }}
        </span>
        <button @click="activeFilter = null" class="text-xs text-indigo-500 hover:text-indigo-700 cursor-pointer ml-1">清除筛选</button>
      </div>

      <!-- 作业列表 -->
      <h2 class="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
        <FileText :size="20" class="text-indigo-500" />
        我的作业（{{ filteredAssignments.length }}）
      </h2>

      <div class="grid gap-4">
        <!-- [需求3] 整行可点击打开详情 -->
        <div
          v-for="a in filteredAssignments"
          :key="a.id"
          :class="[
            'bg-white rounded-xl border p-5 hover:shadow-md transition cursor-pointer',
            isUrgent(a.deadline) && a.status === '未交'
              ? 'border-amber-300 ring-1 ring-amber-100'
              : 'border-slate-200'
          ]"
          @click="selected = a"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">{{ a.course_name }}</span>
                <!-- 状态徽章 -->
                <span :class="[
                  'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border',
                  statusStyles[a.status || '未交'] || 'bg-slate-100 text-slate-600'
                ]">
                  <Clock v-if="a.status === '未交'" :size="12" />
                  <CheckCircle2 v-else-if="a.status === '已交'" :size="12" />
                  <XCircle v-else-if="a.status === '已截止'" :size="12" />
                  {{ a.status || '未交' }}
                </span>
                <span
                  v-if="isUrgent(a.deadline) && a.status === '未交'"
                  class="text-xs text-amber-600 flex items-center gap-0.5 animate-pulse"
                >
                  <AlertTriangle :size="12" />紧急
                </span>
              </div>

              <h3 class="text-base font-bold text-slate-800 mt-1">{{ a.title }}</h3>
              <p class="text-sm text-slate-500 mt-1 line-clamp-2">{{ a.description }}</p>

              <div class="flex items-center gap-4 mt-3 text-xs text-slate-500">
                <span class="flex items-center gap-1">
                  <Calendar :size="12" />截止：{{ formatDate(a.deadline) }}
                </span>
                <span v-if="getTimeLeft(a.deadline)" class="flex items-center gap-1">
                  <Clock :size="12" />{{ getTimeLeft(a.deadline) }}
                </span>
                <span class="flex items-center gap-1">
                  <FileText :size="12" />格式：{{ a.allowed_extensions }}
                </span>
                <span v-if="a.submitted_at" class="flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 :size="12" />提交于：{{ formatDate(a.submitted_at) }}
                </span>
              </div>
            </div>

            <!-- [需求3] 按钮用 @click.stop 阻止冒泡 -->
            <div class="flex items-center gap-1.5 ml-4" @click.stop>
              <button @click="selected = a" class="p-2 hover:bg-blue-50 text-blue-500 rounded-lg cursor-pointer" title="查看详情">
                <Eye :size="16" />
              </button>
              <button
                v-if="a.status === '未交'"
                @click="uploadTarget = a; selectedFile = null"
                class="flex items-center gap-1 px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-xs font-medium cursor-pointer"
              >
                <Upload :size="14" />提交
              </button>
              <button
                v-if="a.status === '已交' && new Date(a.deadline).getTime() > Date.now()"
                @click="uploadTarget = a; selectedFile = null"
                class="flex items-center gap-1 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-medium cursor-pointer"
              >
                <Upload :size="14" />重交
              </button>
            </div>
          </div>
        </div>

        <div v-if="filteredAssignments.length === 0" class="text-center py-12 text-slate-400">
          {{ activeFilter ? `没有「${activeFilter}」状态的作业` : '暂无作业' }}
        </div>
      </div>
    </main>

    <!-- ==================== [需求4] 文件上传模态框（两步确认） ==================== -->
    <Teleport to="body">
      <div
        v-if="uploadTarget"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
        @click="closeUploadModal"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6" @click.stop>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-slate-800">提交作业文件</h3>
            <button @click="closeUploadModal" class="text-slate-400 hover:text-slate-600 cursor-pointer">
              <X :size="20" />
            </button>
          </div>

          <div class="bg-slate-50 rounded-xl p-4 mb-4 text-sm">
            <p class="font-medium text-slate-700">【{{ uploadTarget.course_name }}】{{ uploadTarget.title }}</p>
            <p class="text-xs text-slate-500 mt-1">截止：{{ formatDate(uploadTarget.deadline) }}</p>
            <p class="text-xs text-slate-500">允许格式：{{ uploadTarget.allowed_extensions }}</p>
          </div>

          <!-- 步骤1：选择文件（未选文件时显示） -->
          <div v-if="!selectedFile" class="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-indigo-400 transition">
            <Upload :size="32" class="mx-auto text-slate-400 mb-3" />
            <p class="text-sm text-slate-600 mb-1">点击或拖拽文件到此处</p>
            <p class="text-xs text-slate-400">仅允许 {{ uploadTarget.allowed_extensions }} 格式</p>
            <label class="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-medium cursor-pointer transition">
              <Upload :size="14" />选择文件
              <input
                type="file"
                class="hidden"
                :accept="uploadTarget.allowed_extensions"
                @change="handleFileSelect"
              />
            </label>
          </div>

          <!-- 步骤2：已选文件，显示文件信息 + 确认/重选按钮 -->
          <div v-else class="space-y-4">
            <div class="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
              <div class="flex items-center gap-3">
                <div class="p-2 bg-indigo-100 rounded-lg">
                  <FileText :size="20" class="text-indigo-600" />
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-slate-800 truncate">{{ selectedFile.name }}</p>
                  <p class="text-xs text-slate-500 mt-0.5">{{ formatFileSize(selectedFile.size) }}</p>
                </div>
                <CheckCircle2 :size="18" class="text-emerald-500" />
              </div>
            </div>

            <div class="flex gap-3">
              <button
                @click="resetFileSelection"
                :disabled="uploadLoading"
                class="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-xl text-sm font-medium cursor-pointer transition disabled:opacity-50"
              >
                <RotateCcw :size="14" />重新选择
              </button>
              <button
                @click="handleConfirmUpload"
                :disabled="uploadLoading"
                class="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-sm font-medium cursor-pointer transition disabled:opacity-70"
              >
                <Loader2 v-if="uploadLoading" :size="14" class="animate-spin" />
                <Upload v-else :size="14" />
                {{ uploadLoading ? '提交中...' : '确认提交' }}
              </button>
            </div>
          </div>

          <!-- 重命名提示 -->
          <p class="text-xs text-slate-400 mt-3">
            💡 系统将自动重命名为：{{ auth.user?.username }}_{{ auth.user?.full_name }}_{{ uploadTarget.title }}.后缀
          </p>
          <p v-if="uploadTarget.status === '已交'" class="text-xs text-amber-600 mt-1">
            ⚠️ 你已提交过此作业，重新提交将覆盖之前的文件
          </p>
        </div>
      </div>
    </Teleport>

    <!-- ==================== 作业详情模态框 ==================== -->
    <Teleport to="body">
      <div
        v-if="selected"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
        @click="selected = null"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto p-6" @click.stop>
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">{{ selected.course_name }}</span>
              <span :class="[
                'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border',
                statusStyles[selected.status || '未交'] || 'bg-slate-100 text-slate-600'
              ]">
                {{ selected.status || '未交' }}
              </span>
            </div>
            <button @click="selected = null" class="text-slate-400 hover:text-slate-600 cursor-pointer">
              <X :size="20" />
            </button>
          </div>
          <h3 class="text-xl font-bold text-slate-800 mb-3">{{ selected.title }}</h3>
          <div class="prose prose-sm text-slate-700 mb-4 whitespace-pre-wrap">{{ selected.description }}</div>
          <div class="bg-slate-50 rounded-xl p-4 space-y-2 text-sm">
            <div class="flex items-center gap-2"><Calendar :size="14" class="text-slate-400" />截止时间：{{ formatDate(selected.deadline) }}</div>
            <div class="flex items-center gap-2"><FileText :size="14" class="text-slate-400" />文件格式：{{ selected.allowed_extensions }}</div>
            <div v-if="selected.submitted_at" class="flex items-center gap-2 text-emerald-600">
              <CheckCircle2 :size="14" />提交时间：{{ formatDate(selected.submitted_at) }}
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ==================== 修改密码模态框 ==================== -->
    <Teleport to="body">
      <div
        v-if="pwdModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
        @click="pwdModal = false"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6" @click.stop>
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-slate-800">修改密码</h3>
            <button @click="pwdModal = false" class="text-slate-400 hover:text-slate-600 cursor-pointer">
              <X :size="20" />
            </button>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">旧密码</label>
              <input
                v-model="pwdForm.oldPwd"
                type="password"
                placeholder="请输入当前密码"
                class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">新密码</label>
              <input
                v-model="pwdForm.newPwd"
                type="password"
                placeholder="至少 6 位"
                class="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div class="flex justify-end gap-3">
              <button @click="pwdModal = false" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl cursor-pointer">取消</button>
              <button
                @click="handleChangePwd"
                class="px-4 py-2 text-sm bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl cursor-pointer font-medium"
              >
                确认修改
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ==================== AI 对话面板 ==================== -->
    <ChatBox v-if="showChat" @close="showChat = false" />
  </div>
</template>

<style scoped>
/* Transition 动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
