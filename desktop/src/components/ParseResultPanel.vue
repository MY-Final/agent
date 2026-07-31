<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Document, Files } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import ParseResultCompare from '@/components/ParseResultCompare.vue'
import ResultViewer from '@/components/ResultViewer.vue'
import type { ParseResultRecord } from '@/types/results'
import { formatDate } from '@/utils/format'

type ViewMode = 'single' | 'compare'

const MAX_COMPARE_COUNT = 4

const props = defineProps<{
  record: ParseResultRecord | null
  loading?: boolean
  history?: ParseResultRecord[]
}>()

const mode = ref<ViewMode>('single')
const selectedId = ref<string | null>(props.record?.id ?? null)
const compareSelectedIds = ref<string[]>([])

watch(
  () => props.record?.id,
  (id) => {
    selectedId.value = id ?? null
  },
)

watch(
  () => props.history,
  (history) => {
    if (!history?.length) {
      compareSelectedIds.value = []
      return
    }
    const valid = history
      .filter((item) => compareSelectedIds.value.includes(item.id))
      .map((item) => item.id)
    compareSelectedIds.value = valid.length >= 2 ? valid : history.slice(0, 2).map((item) => item.id)
  },
)

const displayedRecord = computed<ParseResultRecord | null>(() => {
  if (!props.history?.length) return props.record
  return props.history.find((item) => item.id === selectedId.value) ?? props.record
})

const compareRecords = computed<ParseResultRecord[]>(() => {
  if (!props.history) return []
  return props.history.filter((item) => compareSelectedIds.value.includes(item.id))
})

const result = computed(() => displayedRecord.value?.result ?? null)
const generatedAt = computed(() => formatDate(displayedRecord.value?.created_at))

function isLatest(item: ParseResultRecord): boolean {
  return props.history?.[0]?.id === item.id
}

function versionLabel(item: ParseResultRecord): string {
  return `${item.template_version ?? '内置模板'} · ${formatDate(item.created_at)}`
}

function pillState(item: ParseResultRecord): 'latest' | 'rejected' | 'failed' | 'normal' {
  if (item.status === 'failed') return 'failed'
  if (item.is_rejected) return 'rejected'
  if (isLatest(item)) return 'latest'
  return 'normal'
}

function pillLabel(item: ParseResultRecord): string {
  const time = item.created_at.slice(11, 16)
  return `v${item.template_version ?? '?'} · ${time}`
}

function pillClass(item: ParseResultRecord): string {
  const state = pillState(item)
  const active = mode.value === 'single'
    ? selectedId.value === item.id
    : compareSelectedIds.value.includes(item.id)
  return active ? `${state} active` : state
}

function pillTitle(item: ParseResultRecord): string {
  const status = pillState(item)
  const statusLabel = {
    latest: '最新',
    rejected: '已驳回',
    failed: '解析失败',
    normal: '历史版本',
  }[status]
  const parts = [versionLabel(item), statusLabel]
  if (item.is_rejected && item.reject_reason) {
    parts.push(`原因：${item.reject_reason}`)
  }
  return parts.join(' · ')
}

function toggleVersion(item: ParseResultRecord): void {
  if (mode.value === 'single') {
    selectedId.value = item.id
    return
  }
  const index = compareSelectedIds.value.indexOf(item.id)
  if (index >= 0) {
    compareSelectedIds.value = compareSelectedIds.value.filter((id) => id !== item.id)
    return
  }
  if (compareSelectedIds.value.length >= MAX_COMPARE_COUNT) {
    ElMessage.warning(`最多同时对比 ${MAX_COMPARE_COUNT} 个版本`)
    return
  }
  compareSelectedIds.value = [...compareSelectedIds.value, item.id]
}

function switchMode(next: ViewMode): void {
  mode.value = next
}
</script>

<template>
  <div v-loading="loading" class="result-panel">
    <div v-if="history && history.length" class="version-toolbar">
      <div class="version-pills" role="tablist" aria-label="解析版本">
        <button
          v-for="item in history"
          :key="item.id"
          type="button"
          class="version-pill"
          :class="pillClass(item)"
          :title="pillTitle(item)"
          @click="toggleVersion(item)"
        >
          <span class="pill-dot" aria-hidden="true" />
          <span class="pill-text">{{ pillLabel(item) }}</span>
        </button>
      </div>
      <div class="mode-segment" role="tablist" aria-label="查看模式">
        <button
          type="button"
          :class="{ active: mode === 'single' }"
          @click="switchMode('single')"
        >
          <el-icon><Document /></el-icon>
          <span>单版本</span>
        </button>
        <button
          type="button"
          :class="{ active: mode === 'compare' }"
          :disabled="history.length < 2"
          @click="switchMode('compare')"
        >
          <el-icon><Files /></el-icon>
          <span>对比</span>
        </button>
      </div>
    </div>

    <template v-if="mode === 'single'">
      <el-alert
        v-if="displayedRecord?.is_rejected && displayedRecord.status === 'success'"
        class="rejected-banner"
        title="该解析结果已被驳回"
        :description="displayedRecord.reject_reason || '未填写驳回原因'"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-alert
        v-else-if="displayedRecord?.is_rejected && displayedRecord.status === 'failed'"
        class="rejected-banner"
        title="该解析结果已被驳回（解析本身失败）"
        :description="displayedRecord.reject_reason || displayedRecord.error_message || '未填写驳回原因'"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-alert
        v-if="displayedRecord?.status === 'failed' && !displayedRecord.is_rejected"
        title="解析失败"
        :description="displayedRecord.error_message || '未记录具体错误，请查看后端日志。'"
        type="error"
        :closable="false"
        show-icon
      />

      <ResultViewer
        v-if="displayedRecord?.status === 'success' && result"
        :template="result.template"
        :data="result.data"
        :summary="result.raw_summary"
        :confidence="result.confidence"
        :generated-at="generatedAt"
      />

      <div v-if="!displayedRecord" class="empty-block">
        <el-empty description="启动分析后，这里将展示结构化解析结果" :image-size="88" />
      </div>
    </template>

    <template v-else>
      <ParseResultCompare v-if="compareRecords.length >= 2" :records="compareRecords" />
      <div v-else class="empty-block">
        <el-empty
          description="请至少选择两个版本进行对比"
          :image-size="88"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.result-panel {
  min-height: 360px;
}

.version-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 46px;
  padding: 8px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--surface-color);
}

.version-pills {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
  gap: 6px;
}

.version-pill {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease,
    color 0.15s ease;
}

.version-pill:hover {
  border-color: var(--border-strong);
  background: var(--surface-strong);
  color: var(--text-primary);
}

.version-pill.active {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: #ffffff;
  font-weight: 600;
}

.pill-dot {
  width: 5px;
  height: 5px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.version-pill.latest .pill-dot {
  background: var(--success-color);
}

.version-pill.rejected .pill-dot {
  background: var(--warning-color);
}

.version-pill.failed .pill-dot {
  background: var(--danger-color);
}

.version-pill.active .pill-dot {
  background: rgba(255, 255, 255, 0.92);
}

.pill-text {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-segment {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--surface-strong);
}

.mode-segment button {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  height: 22px;
  padding: 0 9px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.mode-segment button .el-icon {
  font-size: 12px;
}

.mode-segment button span {
  font-size: 11px;
  line-height: 1;
}

.mode-segment button:hover:not(:disabled):not(.active) {
  color: var(--text-secondary);
}

.mode-segment button.active {
  background: var(--surface-color);
  color: var(--primary-dark);
  box-shadow: 0 1px 2px rgba(31, 41, 36, 0.08);
  font-weight: 600;
}

.mode-segment button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.rejected-banner {
  margin: 0;
  border: 0;
  border-bottom: 1px solid var(--border-color);
  border-radius: 0;
}

.empty-block {
  display: grid;
  min-height: 260px;
  place-items: center;
}

@media (max-width: 1100px) {
  .version-toolbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
