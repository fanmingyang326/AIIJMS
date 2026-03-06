<!-- ============================================================
  AI 对话组件 (ChatBox.vue)
  功能：
    1. 右下角悬浮聊天窗口
    2. 调用真实 POST /api/chat/ask 接口
    3. 管理并传递 session_id 保持会话上下文
  修复：
    - 移除了基于正则的本地假 AI 回复逻辑
    - sendMessage 函数发起真实 POST 请求
    - 从后端返回值中提取 reply 和 session_id
============================================================ -->

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { X, Send, Bot, User, Loader2 } from 'lucide-vue-next'
import { chatAsk } from '@/api/client'

// ==================== 事件定义 ====================
const emit = defineEmits<{
  close: []
}>()

// ==================== 消息类型 ====================

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

// ==================== 响应式状态 ====================

const messages = ref<ChatMessage[]>([
  {
    role: 'assistant',
    content: '你好！我是 AI 智能助手，有任何关于作业的问题都可以问我 😊',
    timestamp: new Date(),
  },
])

const inputText = ref('')
const loading = ref(false)
const sessionId = ref<string | undefined>(undefined)  // 会话 ID，由后端返回
const chatBody = ref<HTMLElement | null>(null)

// ==================== 自动滚动到底部 ====================

async function scrollToBottom() {
  await nextTick()
  if (chatBody.value) {
    chatBody.value.scrollTop = chatBody.value.scrollHeight
  }
}

onMounted(scrollToBottom)

// ==================== 发送消息 ====================

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // 1. 添加用户消息到列表
  messages.value.push({
    role: 'user',
    content: text,
    timestamp: new Date(),
  })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    // 2. 调用真实后端 AI 对话接口
    const data = await chatAsk(text, sessionId.value)

    // 3. 更新 session_id（保持会话上下文）
    sessionId.value = data.session_id

    // 4. 添加 AI 回复到消息列表
    messages.value.push({
      role: 'assistant',
      content: data.reply,
      timestamp: new Date(),
    })
  } catch (err) {
    // 网络或后端错误时给出友好提示
    messages.value.push({
      role: 'assistant',
      content: `抱歉，请求出现了问题：${err instanceof Error ? err.message : '未知错误'}。请稍后再试。`,
      timestamp: new Date(),
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// ==================== 回车发送 ====================

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <!-- 悬浮聊天窗口 -->
  <div class="fixed bottom-6 right-6 z-50 w-96 h-[500px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white">
      <div class="flex items-center gap-2">
        <Bot :size="18" />
        <span class="font-medium text-sm">AI 智能助手</span>
      </div>
      <button @click="emit('close')" class="hover:bg-white/20 rounded-lg p-1 transition cursor-pointer">
        <X :size="16" />
      </button>
    </div>

    <!-- 消息列表 -->
    <div ref="chatBody" class="flex-1 overflow-y-auto p-4 space-y-3">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['flex gap-2', msg.role === 'user' ? 'justify-end' : 'justify-start']"
      >
        <!-- AI 头像 -->
        <div v-if="msg.role === 'assistant'" class="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
          <Bot :size="14" class="text-indigo-600" />
        </div>

        <!-- 消息气泡 -->
        <div :class="[
          'max-w-[75%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
          msg.role === 'user'
            ? 'bg-indigo-500 text-white rounded-tr-md'
            : 'bg-slate-100 text-slate-700 rounded-tl-md'
        ]">
          <!-- 支持简单的换行渲染 -->
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
          <div :class="['text-[10px] mt-1', msg.role === 'user' ? 'text-indigo-200' : 'text-slate-400']">
            {{ msg.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
          </div>
        </div>

        <!-- 用户头像 -->
        <div v-if="msg.role === 'user'" class="w-7 h-7 rounded-full bg-violet-100 flex items-center justify-center flex-shrink-0">
          <User :size="14" class="text-violet-600" />
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="loading" class="flex gap-2 justify-start">
        <div class="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
          <Bot :size="14" class="text-indigo-600" />
        </div>
        <div class="bg-slate-100 rounded-2xl rounded-tl-md px-4 py-3">
          <Loader2 :size="16" class="text-indigo-500 animate-spin" />
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="border-t border-slate-200 px-4 py-3">
      <div class="flex items-center gap-2">
        <textarea
          v-model="inputText"
          @keydown="handleKeydown"
          placeholder="输入你的问题..."
          rows="1"
          class="flex-1 resize-none border border-slate-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 max-h-20"
        />
        <button
          @click="sendMessage"
          :disabled="loading || !inputText.trim()"
          class="p-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl disabled:opacity-50 transition cursor-pointer"
        >
          <Send :size="16" />
        </button>
      </div>
      <p class="text-[10px] text-slate-400 mt-1.5 text-center">
        由 LangChain AI 智能体驱动 · 支持多轮对话
      </p>
    </div>
  </div>
</template>
