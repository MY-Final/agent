<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { ChatDotRound, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { ApiRequestError, getErrorMessage } from '@/api/client'
import { taskApi } from '@/api/tasks'

const props = defineProps<{
  taskId: string
  hasResult: boolean
}>()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  error?: boolean
}

const messages = ref<ChatMessage[]>([])
const input = ref('')
const sending = ref(false)
const bodyRef = ref<HTMLElement | null>(null)

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = bodyRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send(): Promise<void> {
  const question = input.value.trim()
  if (!question || sending.value) return
  input.value = ''
  sending.value = true
  messages.value.push({ role: 'user', content: question })
  const answer: ChatMessage = { role: 'assistant', content: '' }
  messages.value.push(answer)
  await scrollToBottom()
  try {
    for await (const event of taskApi.chatAgentStream(props.taskId, question)) {
      if (event.type === 'delta') {
        answer.content += String(event.content ?? '')
        await scrollToBottom()
      } else if (event.type === 'error') {
        throw new ApiRequestError(
          String(event.message ?? '回答失败'),
          typeof event.code === 'number' ? event.code : undefined,
        )
      }
    }
    if (!answer.content) answer.content = '（没有收到回答内容）'
  } catch (error) {
    const message = getErrorMessage(error)
    answer.error = true
    answer.content = answer.content
      ? `${answer.content}\n\n[回答中断] ${message}`
      : message
    ElMessage.error(message)
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

watch(
  () => props.hasResult,
  (hasResult) => {
    if (!hasResult) messages.value = []
  },
)
</script>

<template>
  <div class="chat-panel">
    <div class="chat-heading">
      <div>
        <h3 class="chat-title">
          <el-icon><ChatDotRound /></el-icon>
          与 Agent 对话
        </h3>
        <p class="chat-subtitle">
          基于当前解析结果和标书原文继续提问，对话会保存在本次任务会话中。
        </p>
      </div>
    </div>

    <div ref="bodyRef" class="chat-body">
      <div v-if="!messages.length" class="chat-empty">
        <el-empty
          :description="hasResult ? '解析已完成，试试问：这个项目的资格要求有哪些？' : '先完成一次标书解析，就可以在这里继续提问了'"
          :image-size="72"
        />
      </div>
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="chat-row"
        :class="message.role"
      >
        <div class="chat-bubble" :class="{ error: message.error }">
          <span v-if="message.role === 'assistant' && sending && index === messages.length - 1 && !message.content" class="chat-cursor" />
          <span class="chat-text">{{ message.content || '正在思考…' }}</span>
        </div>
      </div>
    </div>

    <div class="chat-input-bar">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        :disabled="!hasResult || sending"
        :placeholder="hasResult ? '基于解析结果提问，Enter 发送，Shift+Enter 换行' : '请先完成标书解析'"
        @keydown.enter.exact.prevent="send"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        :loading="sending"
        :disabled="!hasResult"
        @click="send"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 480px;
}

.chat-heading {
  padding: 4px 2px 14px;
}

.chat-title {
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 0;
  font-size: 15px;
}

.chat-subtitle {
  margin: 6px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

.chat-body {
  flex: 1;
  min-height: 300px;
  max-height: 480px;
  padding: 14px;
  overflow: auto;
  background: var(--bg-secondary, #fafafa);
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 260px;
}

.chat-row {
  display: flex;
  margin-bottom: 12px;
}

.chat-row.user {
  justify-content: flex-end;
}

.chat-bubble {
  max-width: 82%;
  padding: 10px 13px;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  border-top-left-radius: 4px;
}

.chat-row.user .chat-bubble {
  color: #fff;
  background: var(--primary-color);
  border-color: var(--primary-color);
  border-radius: 12px;
  border-top-right-radius: 4px;
}

.chat-bubble.error {
  color: var(--danger-color);
  background: #fef0f0;
  border-color: #fde2e2;
}

.chat-text {
  word-break: break-word;
}

.chat-cursor {
  display: inline-block;
  width: 8px;
  height: 14px;
  margin-left: 2px;
  vertical-align: -2px;
  background: var(--primary-color);
  animation: chat-cursor-blink 0.8s steps(2) infinite;
}

.chat-input-bar {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding-top: 12px;
}

.chat-input-bar .el-input {
  flex: 1;
}

@keyframes chat-cursor-blink {
  50% { opacity: 0; }
}
</style>
