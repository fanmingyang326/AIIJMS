// ============================================================
// 认证状态管理 (Pinia Store)
// 功能：
//   1. 管理用户登录状态（token + 用户信息）
//   2. 提供 login / logout 动作
//   3. Token 持久化到 localStorage，刷新页面不丢失状态
//   4. 在任意组件中通过 useAuthStore() 获取认证状态
//
// 【修复】移除了 mockLogin / initDemoData 等 Mock 逻辑
//         登录调用真实 POST /api/auth/login 接口
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  login as apiLogin,
  getToken,
  setToken,
  clearToken,
  type UserInfo,
} from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  // ==================== 响应式状态 ====================

  /** 当前登录用户信息 */
  const user = ref<UserInfo | null>(null)

  /** JWT Token */
  const token = ref<string | null>(null)

  /** 是否已完成初始化加载（防止路由守卫闪烁） */
  const ready = ref(false)

  // ==================== 计算属性 ====================

  /** 是否已登录 */
  const isLoggedIn = computed(() => !!token.value && !!user.value)

  // ==================== 初始化 ====================

  /**
   * 从 localStorage 恢复登录状态
   * 在 App.vue 的 onMounted 或路由守卫中调用
   */
  function init() {
    const savedToken = getToken()
    const savedUser = localStorage.getItem('hw_user')

    if (savedToken && savedUser) {
      try {
        token.value = savedToken
        user.value = JSON.parse(savedUser)
      } catch {
        // JSON 解析失败则清除脏数据
        clearToken()
        localStorage.removeItem('hw_user')
      }
    }
    ready.value = true
  }

  // ==================== 登录 ====================

  /**
   * 调用后端真实登录接口
   * @param username 用户名（教师工号 / 学生学号）
   * @param password 密码
   */
  async function login(username: string, password: string) {
    const data = await apiLogin(username, password)

    // 【修改点 1】：使用 getToken() 作为兜底保障
    // 即使接口返回的 data 中没有 token 字段，也能从内部状态拿到正确的 Token
    token.value = data.access_token || getToken()

    // 同理，防止 data.user 为空导致 JSON.stringify 写入 undefined 报错
    user.value = data.user || data

    localStorage.setItem('hw_user', JSON.stringify(user.value))
  }

  // ==================== 登出 ====================

  function logout() {
    token.value = null
    user.value = null
    clearToken()
    localStorage.removeItem('hw_user')
  }

  return {
    user,
    token,
    ready,
    isLoggedIn,
    init,
    login,
    logout,
  }
})
