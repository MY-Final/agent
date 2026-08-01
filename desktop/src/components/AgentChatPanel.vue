<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ChatDotRound, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { ApiRequestError, getErrorMessage } from '@/api/client'
import { taskApi } from '@/api/tasks'

const props = defineProps<{
  taskId: string
  hasResult: boolean
}>()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  error?: boolean
}

const SUGGEST_QUESTIONS = [
  '这个项目的资格要求有哪些？',
  '废标条款都有哪些？',
  '项目的关键时间节点是什么？',
]

const messages = ref<ChatMessage[]>([])
const input = ref('')
const sending = ref(false)
const bodyRef = ref<HTMLElement | null>(null)

const escapeText = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

marked.use({
  gfm: true,
  breaks: true,
  renderer: {
    html({ text }: { text?: string }) {
      // 只渲染 Markdown 生成的标签，原始 HTML 一律转义，防止注入。
      return escapeText(text ?? '')
    },
    link({ href, title, tokens }: { href?: string | null; title?: string | null; tokens: { raw: string }[] }) {
      const safe = href && /^(https?:|mailto:)/i.test(href) ? href : ''
      if (!safe) return tokens.map((token) => token.raw).join('')
      const text = tokens.map((token) => token.raw).join('')
      const titleAttr = title ? ` title="${escapeText(title)}"` : ''
      return `<a href="${escapeText(safe)}" target="_blank" rel="noopener noreferrer"${titleAttr}>${text}</a>`
    },
  },
})

function renderMarkdown(content: string): string {
  return marked.parse(content) as string
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = bodyRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send(question?: string): Promise<void> {
  const text = (question ?? input.value).trim()
  if (!text || sending.value) return
  input.value = ''
  sending.value = true
  messages.value.push({ role: 'user', content: text })
  const answer: ChatMessage = { role: 'assistant', content: '', thinking: '' }
  messages.value.push(answer)
  await scrollToBottom()
  try {
    for await (const event of taskApi.chatAgentStream(props.taskId, text)) {
      if (event.type === 'thinking') {
        answer.thinking = (answer.thinking ?? '') + String(event.content ?? '')
      } else if (event.type === 'delta') {
        answer.content += String(event.content ?? '')
      } else if (event.type === 'error') {
        throw new ApiRequestError(
          String(event.message ?? '回答失败'),
          typeof event.code === 'number' ? event.code : undefined,
        )
      }
      await scrollToBottom()
    }
    if (!answer.content.trim()) answer.content = '（没有收到回答内容）'
  } catch (error) {
    const message = getErrorMessage(error)
    answer.error = true
    answer.content = answer.content.trim()
      ? `${answer.content}\n\n[回答中断] ${message}`
      : message
    ElMessage.error(message)
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function loadHistory(): Promise<void> {
  if (!props.taskId) return
  try {
    const history = await taskApi.getChatHistory(props.taskId)
    messages.value = history.map((item) => ({
      role: item.role,
      content: item.content,
    }))
    await scrollToBottom()
  } catch {
    // 尚未启动过 Agent 或暂无历史时保持空状态
  }
}

watch(
  () => props.hasResult,
  (hasResult) => {
    if (!hasResult && !messages.value.length) return
    if (!hasResult) messages.value = []
  },
)

watch(() => props.taskId, loadHistory)
onMounted(loadHistory)

const isStreamingLast = computed(() => (index: number) =>
  sending.value && index === messages.value.length - 1,
)
</script>

<template>
  <div class="chat-panel">
    <header class="chat-header">
      <div class="chat-title">
        <el-icon><ChatDotRound /></el-icon>
        <div>
          <h3>与 Agent 对话</h3>
          <p>基于当前解析结果与标书原文继续提问，回答会保留在当前任务会话中。</p>
        </div>
      </div>
      <span class="chat-status" :class="{ ready: hasResult }">
        <i />
        {{ hasResult ? '可提问' : '等待解析' }}
      </span>
    </header>

    <div ref="bodyRef" class="chat-body">
      <div v-if="!messages.length" class="chat-empty">
        <el-empty
          :description="hasResult ? '解析已完成，可以从这里继续追问细节。' : '先完成一次标书解析，就可以在这里继续提问了'"
          :image-size="72"
        />
        <div v-if="hasResult" class="chat-suggest">
          <span class="chat-suggest-label">试试问</span>
          <button
            v-for="question in SUGGEST_QUESTIONS"
            :key="question"
            type="button"
            class="suggest-chip"
            :disabled="sending"
            @click="send(question)"
          >
            {{ question }}
          </button>
        </div>
      </div>

      <div
        v-for="(message, index) in messages"
        :key="index"
        class="chat-row"
        :class="[message.role, { error: message.error }]"
      >
        <div class="chat-meta">
          {{ message.role === 'user' ? '你' : 'Agent' }}
        </div>

        <div v-if="message.role === 'assistant'" class="assistant-card">
          <details
            v-if="message.thinking"
            class="thinking"
            :open="isStreamingLast(index)"
          >
            <summary>
              <span class="thinking-dot" />
              思考过程
              <span v-if="message.thinking && !isStreamingLast(index)" class="thinking-meta">
                {{ message.thinking.length }} 字
              </span>
            </summary>
            <div class="thinking-body">{{ message.thinking }}</div>
          </details>

          <div class="md-body">
            <div v-if="message.content" v-html="renderMarkdown(message.content)" />
            <span v-else-if="isStreamingLast(index)" class="waiting">
              正在思考<span class="waiting-dots"><i /><i /><i /></span>
            </span>
          </div>
        </div>

        <div v-else class="user-bubble">
          <span class="chat-text">{{ message.content }}</span>
        </div>
      </div>
    </div>

    <footer class="chat-footer">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        :disabled="!hasResult || sending"
        :placeholder="hasResult ? '基于解析结果提问，Enter 发送，Shift+Enter 换行' : '请先完成标书解析'"
        @keydown.enter.exact.prevent="send()"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        :loading="sending"
        :disabled="!hasResult"
        class="send-button"
        @click="send()"
      >
        发送
      </el-button>
    </footer>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 316px);
  min-height: 520px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-primary, #fff);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.chat-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.chat-title .el-icon {
  margin-top: 2px;
  color: var(--primary-color);
  font-size: 18px;
}

.chat-title h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.chat-title p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.chat-status {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px 10px;
  color: var(--text-tertiary);
  font-size: 11px;
  background: var(--bg-secondary, #f7f7f7);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  white-space: nowrap;
}

.chat-status i {
  width: 7px;
  height: 7px;
  background: #c0c4cc;
  border-radius: 50%;
}

.chat-status.ready i {
  background: var(--success-color, #67c23a);
}

.chat-body {
  flex: 1;
  padding: 20px;
  overflow: auto;
  background: var(--bg-secondary, #fafafa);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  gap: 18px;
  align-items: center;
  justify-content: center;
  min-height: 100%;
}

.chat-suggest {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: center;
}

.chat-suggest-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.suggest-chip {
  padding: 6px 12px;
  color: var(--primary-color);
  font-size: 12px;
  cursor: pointer;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.suggest-chip:hover:not(:disabled) {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.suggest-chip:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.chat-row {
  margin-bottom: 18px;
}

.chat-row.user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.chat-meta {
  margin: 0 2px 6px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.user-bubble {
  max-width: 76%;
  padding: 10px 14px;
  color: #fff;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--primary-color);
  border-radius: 12px;
  border-top-right-radius: 4px;
}

.assistant-card {
  max-width: 92%;
  overflow: hidden;
  background: #fff;
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--primary-color);
  border-radius: 10px;
}

.chat-row.error .assistant-card {
  border-left-color: var(--danger-color);
}

.thinking {
  border-bottom: 1px dashed var(--border-color);
}

.thinking summary {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 14px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.thinking summary::-webkit-details-marker {
  display: none;
}

.thinking-dot {
  width: 7px;
  height: 7px;
  background: var(--primary-color);
  border-radius: 50%;
  animation: thinking-pulse 1s ease-in-out infinite;
}

.thinking-meta {
  margin-left: auto;
  color: var(--text-tertiary);
  font-size: 10px;
}

.thinking-body {
  padding: 0 14px 10px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.md-body {
  padding: 12px 14px;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.85;
  word-break: break-word;
}

.waiting {
  color: var(--text-tertiary);
  font-size: 12px;
}

.waiting-dots {
  display: inline-flex;
  gap: 3px;
  margin-left: 6px;
}

.waiting-dots i {
  width: 4px;
  height: 4px;
  background: currentColor;
  border-radius: 50%;
  animation: waiting-bounce 1.2s ease-in-out infinite;
}

.waiting-dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.waiting-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

.md-body :deep(p) {
  margin: 0 0 10px;
}

.md-body :deep(p:last-child) {
  margin-bottom: 0;
}

.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin: 14px 0 8px;
  font-weight: 600;
  line-height: 1.4;
}

.md-body :deep(h1) {
  font-size: 16px;
}

.md-body :deep(h2) {
  font-size: 15px;
}

.md-body :deep(h3) {
  font-size: 14px;
}

.md-body :deep(h4) {
  font-size: 13px;
}

.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 0 0 10px;
  padding-left: 22px;
}

.md-body :deep(li) {
  margin: 3px 0;
}

.md-body :deep(blockquote) {
  margin: 10px 0;
  padding: 4px 12px;
  color: var(--text-secondary);
  border-left: 3px solid var(--border-color);
}

.md-body :deep(code) {
  padding: 1px 5px;
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 4px;
}

.md-body :deep(pre) {
  margin: 10px 0;
  padding: 12px;
  overflow: auto;
  background: #1e2229;
  border-radius: 8px;
}

.md-body :deep(pre code) {
  padding: 0;
  color: #e6e6e6;
  font-size: 12px;
  line-height: 1.6;
  background: none;
}

.md-body :deep(table) {
  display: block;
  width: 100%;
  margin: 10px 0;
  overflow: auto;
  font-size: 12px;
  border-collapse: collapse;
}

.md-body :deep(th),
.md-body :deep(td) {
  padding: 6px 10px;
  text-align: left;
  border: 1px solid var(--border-color);
}

.md-body :deep(th) {
  font-weight: 600;
  background: var(--bg-secondary, #f7f7f7);
}

.md-body :deep(a) {
  color: var(--primary-color);
}

.md-body :deep(hr) {
  margin: 12px 0;
  border: 0;
  border-top: 1px solid var(--border-color);
}

.chat-footer {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 14px 16px;
  border-top: 1px solid var(--border-color);
}

.chat-footer .el-input {
  flex: 1;
}

.send-button {
  min-width: 88px;
}

@keyframes thinking-pulse {
  50% { opacity: 0.35; }
}

@keyframes waiting-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-3px); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .thinking-dot,
  .suggest-chip,
  .waiting-dots i {
    animation: none;
    transition: none;
  }
}
</style>
