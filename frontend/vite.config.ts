import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'
import { fileURLToPath, URL } from 'node:url' // 🌟 替换了 path 的引入方式

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    viteSingleFile(),
  ],
  resolve: {
    alias: {
      // 🌟 改用官方推荐的 ESM 模块路径解析方式
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
   server: {
    proxy: {
      '/api': {
        target: 'http://host.docker.internal:8000',
        changeOrigin: true
        // 如果你后端本身就是 /api/auth/login，就不用 rewrite
        // 如果你后端是 /auth/login，再打开下面这行：
        // rewrite: path => path.replace(/^\/api/, '')
      }
    }, host: true
  }
})
