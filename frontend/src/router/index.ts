// ============================================================
// 路由配置 (vue-router v4)
// 功能：
//   1. 定义登录、学生端、教师端三个路由
//   2. 全局前置守卫（Navigation Guard）：
//      - 未登录 → 强制跳转 /login
//      - 学生只能访问 /student，教师只能访问 /teacher
//      - 已登录用户访问 /login → 自动跳转到对应 Dashboard
// ============================================================

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// ==================== 路由定义 ====================

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/student',
    name: 'StudentDashboard',
    component: () => import('@/views/StudentDashboard.vue'),
    meta: { requiresAuth: true, role: 'student' },
  },
  {
    path: '/teacher',
    name: 'TeacherDashboard',
    component: () => import('@/views/TeacherDashboard.vue'),
    meta: { requiresAuth: true, role: 'teacher' },
  },
  {
    // 根路径重定向到登录
    path: '/',
    redirect: '/login',
  },
  {
    // 未匹配路由 → 回到登录
    path: '/:pathMatch(.*)*',
    redirect: '/login',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ==================== 全局前置守卫 ====================

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()

  // 确保 auth store 已初始化（从 localStorage 恢复状态）
  if (!auth.ready) {
    auth.init()
  }

  const isLoggedIn = auth.isLoggedIn
  const userRole = auth.user?.role

  // 情况 1：访问需要认证的页面，但未登录 → 跳转登录
  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ name: 'Login' })
    return
  }

  // 情况 2：已登录用户访问登录页 → 跳转到对应 Dashboard
  if (to.name === 'Login' && isLoggedIn) {
    next({ name: userRole === 'teacher' ? 'TeacherDashboard' : 'StudentDashboard' })
    return
  }

  // 情况 3：角色权限校验（学生不能访问教师页，反之亦然）
  if (to.meta.role && to.meta.role !== userRole) {
    const targetName = userRole === 'teacher' ? 'TeacherDashboard' : 'StudentDashboard'

    // 【修改点 2】：增加判断，如果当前正要去的就是目标页，就直接放行，避免陷入死循环重定向
    if (to.name === targetName) {
      next()
      return
    }

    next({ name: targetName })
    return
  }

  next()
})

export default router
