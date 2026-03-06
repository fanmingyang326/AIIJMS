// ============================================================
// 应用入口
// 初始化 Vue 3 + Pinia + Vue Router
// ============================================================

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './index.css'

const app = createApp(App)

// 注册 Pinia 状态管理（必须在 router 之前，因为路由守卫中会用到 store）
app.use(createPinia())

// 注册路由
app.use(router)

// 挂载到 DOM
app.mount('#app')
