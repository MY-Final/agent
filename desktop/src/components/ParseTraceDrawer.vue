<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Document, MagicStick, Memo } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { taskApi } from '@/api/tasks'
import type { ParseResultRecord, ParseSourceTextItem } from '@/types/results'

const props = defineProps<{
  modelValue: boolean
  taskId: string
  record: ParseResultRecord | null
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>()

type TraceTab = 'source' | 'prompt' | 'raw'

const activeTab = ref<TraceTab>('source')
const sourceItems = ref<ParseSourceTextItem[]>([])
const sourceLoading = ref(false)
const sourceKeyword = ref('')

const trace = computed(() => props.record?.llm_prompt ?? null)

const messages = computed(() => {
  const list = trace.value?.messages
  return Array.isArray(list) ? list : []
})

const systemPrompt = computed(() => {
  const message = messages.value.find((item) => item.role === 'system')
  return message?.content ?? ''
})

const userPrompt = computed(() => {
  const message = messages.value.find((item) => item.role === 'user')
  return message?.content ?? ''
})

const schemaText = computed(() => {
  const schema = trace.value?.schema
  if (!schema) return ''
  try {
    return JSON.stringify(schema, null, 2)
  } catch {
    return String(schema)
  }
})

const rawResponse = computed(() => {
  const raw = props.record?.raw_llm_response ?? ''
  if (!raw) return ''
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
})

watch(
  () => [props.modelValue, props.record?.id] as const,
  async ([visible, recordId]) => {
    if (!visible || !recordId || !props.taskId) return
    activeTab.value = 'source'
    sourceKeyword.value = ''
    sourceItems.value = []
    sourceLoading.value = true
    try {
      sourceItems.value = await taskApi.getSourceText(props.taskId, recordId)
    } catch (error) {
      ElMessage.error(getErrorMessage(error))
    } finally {
      sourceLoading.value = false
    }
  },
  { immediate: true },
)

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function highlighted(text: string): string {
  const keyword = sourceKeyword.value.trim()
  const escaped = escapeHtml(text)
  if (!keyword) return escaped
  const pattern = escapeHtml(keyword).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped.replace(new RegExp(pattern, 'gi'), (match) => `<mark>${match}</mark>`)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="过程详情"
    size="min(680px, 52vw)"
    class="trace-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="trace-heading">
        <h2>AI 解析过程详情</h2>
        <p>完整还原：提取的原文 → 发送给大模型的提示词 → 大模型原始返回。</p>
      </div>
    </template>

    <div class="trace-tabs" role="tablist">
      <button
        type="button"
        class="trace-tab"
        :class="{ active: activeTab === 'source' }"
        @click="activeTab = 'source'"
      >
        <el-icon><Document /></el-icon>
        提取的原文
      </button>
      <button
        type="button"
        class="trace-tab"
        :class="{ active: activeTab === 'prompt' }"
        @click="activeTab = 'prompt'"
      >
        <el-icon><Memo /></el-icon>
        发送的提示词
      </button>
      <button
        type="button"
        class="trace-tab"
        :class="{ active: activeTab === 'raw' }"
        @click="activeTab = 'raw'"
      >
        <el-icon><MagicStick /></el-icon>
        LLM 原始返回
      </button>
    </div>

    <template v-if="activeTab === 'source'">
      <el-input
        v-model="sourceKeyword"
        class="trace-search"
        placeholder="输入原文片段，高亮定位"
        clearable
      />
      <div v-loading="sourceLoading" class="trace-body">
        <section v-for="item in sourceItems" :key="item.filename" class="trace-file">
          <header class="trace-file-head">
            <el-icon><Document /></el-icon>
            <strong>{{ item.filename }}</strong>
            <small v-if="item.extraction_method">提取方式：{{ item.extraction_method }}</small>
          </header>
          <pre class="trace-pre" v-html="highlighted(item.text)" />
        </section>
        <el-empty
          v-if="!sourceLoading && !sourceItems.length"
          description="该版本没有保存原文文本"
          :image-size="80"
        />
      </div>
    </template>

    <template v-else-if="activeTab === 'prompt'">
      <div v-if="messages.length" class="trace-body trace-prompt">
        <section class="trace-block">
          <header class="trace-block-head">
            <strong>系统提示词</strong>
            <small>System</small>
          </header>
          <pre class="trace-pre">{{ systemPrompt }}</pre>
        </section>
        <section class="trace-block">
          <header class="trace-block-head">
            <strong>用户消息</strong>
            <small>User</small>
          </header>
          <pre class="trace-pre">{{ userPrompt }}</pre>
        </section>
        <section class="trace-block">
          <header class="trace-block-head">
            <strong>响应 JSON Schema</strong>
            <small>response_format</small>
          </header>
          <pre class="trace-pre">{{ schemaText }}</pre>
        </section>
      </div>
      <el-empty v-else description="该版本没有保存调用提示词" :image-size="80" />
    </template>

    <template v-else>
      <div v-if="rawResponse" class="trace-body">
        <pre class="trace-pre">{{ rawResponse }}</pre>
      </div>
      <el-empty v-else description="该版本没有保存大模型原始返回" :image-size="80" />
    </template>
  </el-drawer>
</template>

<style scoped>
.trace-heading h2 {
  margin: 0;
  font-size: 17px;
}

.trace-heading p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

.trace-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border-color);
}

.trace-tab {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 9px 14px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
}

.trace-tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
  font-weight: 600;
}

.trace-search {
  margin-bottom: 12px;
}

.trace-body {
  max-height: calc(100vh - 260px);
  overflow: auto;
}

.trace-file,
.trace-block {
  margin-bottom: 14px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 10px;
}

.trace-file-head,
.trace-block-head {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 9px 12px;
  background: var(--bg-secondary, #fafafa);
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
}

.trace-block-head small {
  margin-left: auto;
  color: var(--text-tertiary);
  font-size: 10px;
}

.trace-file-head small {
  margin-left: auto;
  color: var(--text-tertiary);
  font-size: 10px;
}

.trace-pre {
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 11px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}

.trace-pre :deep(mark) {
  padding: 0 1px;
  color: inherit;
  background: #ffe58f;
  border-radius: 2px;
}
</style>
