<!-- ============================================================
  登录页面 Login.vue
  功能：
    1. 教师和学生统一登录入口
    2. 演示账号快速填入
    3. 登录成功后根据角色跳转到对应 Dashboard
  修复：
    - 移除 mockLogin，调用真实后端 /api/auth/login
    - 移除 setTimeout 假延迟，使用 async/await 真实网络请求
============================================================ -->

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, User, Lock, LogIn, Eye, EyeOff, AlertCircle } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

// ==================== 响应式状态 ====================
const username = ref('')
const password = ref('')
const showPwd = ref(false)
const error = ref('')
const loading = ref(false)

// ==================== 登录逻辑 ====================

async function handleLogin() {
  if (!username.value.trim() || !password.value.trim()) {
    error.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    // 调用真实后端登录接口
    await auth.login(username.value.trim(), password.value)
    // 登录成功，根据角色跳转
    const target = auth.user?.role === 'teacher' ? '/teacher' : '/student'
    router.replace(target)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '用户名或密码错误，或账号已被停用'
  } finally {
    loading.value = false
  }
}

// ==================== 快速填入演示账号 ====================

function quickLogin(u: string, p: string) {
  username.value = u
  password.value = p
  error.value = ''
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-violet-50 flex items-center justify-center p-4">
    <!-- 背景装饰 -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute -top-40 -right-40 w-80 h-80 bg-indigo-200/30 rounded-full blur-3xl" />
      <div class="absolute -bottom-40 -left-40 w-80 h-80 bg-violet-200/30 rounded-full blur-3xl" />
    </div>

    <div class="relative w-full max-w-md">
      <!-- Logo + 标题 -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-200/50 mb-4">
          <BookOpen :size="32" class="text-white" />
        </div>
        <h1 class="text-2xl font-bold text-slate-800">AI 智能作业管理系统</h1>
        <p class="text-sm text-slate-400 mt-1">具备 AI 智能体的双角色教学管理平台</p>
      </div>

      <!-- 登录卡片 -->
      <div class="bg-white rounded-2xl shadow-xl border border-slate-200/60 p-8">
        <h2 class="text-lg font-bold text-slate-700 mb-6 text-center">账号登录</h2>

        <form @submit.prevent="handleLogin" class="space-y-5">
          <!-- 用户名 -->
          <div>
            <label class="block text-sm font-medium text-slate-600 mb-1.5">用户名</label>
            <div class="relative">
              <User :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="username"
                type="text"
                placeholder="教师输入工号 / 学生输入学号"
                class="w-full pl-10 pr-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>
          </div>

          <!-- 密码 -->
          <div>
            <label class="block text-sm font-medium text-slate-600 mb-1.5">密码</label>
            <div class="relative">
              <Lock :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                v-model="password"
                :type="showPwd ? 'text' : 'password'"
                placeholder="请输入密码"
                class="w-full pl-10 pr-10 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
              <button
                type="button"
                @click="showPwd = !showPwd"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <EyeOff v-if="showPwd" :size="16" />
                <Eye v-else :size="16" />
              </button>
            </div>
          </div>

          <!-- 错误提示 -->
          <div v-if="error" class="flex items-center gap-2 text-red-600 bg-red-50 rounded-xl px-4 py-2.5 text-sm">
            <AlertCircle :size="16" class="flex-shrink-0" />
            <span>{{ error }}</span>
          </div>

          <!-- 登录按钮 -->
          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2.5 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-medium rounded-xl shadow-lg shadow-indigo-200/50 hover:shadow-indigo-300/50 transition-all disabled:opacity-60 flex items-center justify-center gap-2 cursor-pointer"
          >
            <div v-if="loading" class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <template v-else>
              <LogIn :size="16" />
              <span>登 录</span>
            </template>
          </button>
        </form>

        <!-- 演示账号提示 -->
        <div class="mt-6 pt-6 border-t border-slate-100">
          <p class="text-xs text-slate-400 text-center mb-3">演示账号（点击快速填入）</p>
          <div class="grid grid-cols-2 gap-3">
            <button
              type="button"
              @click="quickLogin('admin', 'admin123')"
              class="flex flex-col items-center gap-1 px-3 py-2.5 bg-indigo-50 hover:bg-indigo-100 rounded-xl transition cursor-pointer"
            >
              <span class="text-xs font-medium text-indigo-700">👨‍🏫 教师端</span>
              <span class="text-[10px] text-indigo-500">admin / admin123</span>
            </button>
            <button
              type="button"
              @click="quickLogin('250721016', '123456')"
              class="flex flex-col items-center gap-1 px-3 py-2.5 bg-violet-50 hover:bg-violet-100 rounded-xl transition cursor-pointer"
            >
              <span class="text-xs font-medium text-violet-700">👨‍🎓 学生端</span>
              <span class="text-[10px] text-violet-500">2024001 / 123456</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 底部信息 -->
      <p class="text-center text-xs text-slate-400 mt-6">
        AI 智能作业管理系统 v1.0 · FastAPI + Vue 3 + LangChain
      </p>
    </div>
  </div>
</template>
