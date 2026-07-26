<script setup lang="ts">
import { computed } from 'vue'
import type { AgentStatus } from '@/types/agent'
import { formatDate } from '@/utils/format'

const props = defineProps<{
  status: AgentStatus | null
  taskStatus: string
  loading?: boolean
}>()

const stepByTaskStatus: Record<string, number> = {
  created: 0,
  parsing: 0,
  waiting_confirm: 1,
  analyzing: 2,
  generating: 2,
  completed: 3,
  failed: 0,
}

const activeStep = computed(() => {
  if (!props.status) return stepByTaskStatus[props.taskStatus] ?? 0
  const mapping: Record<string, number> = {
    parse: 0,
    wait_confirm: 1,
    match: 2,
    completed: 3,
    failed: 0,
    cancelled: 0,
  }
  return mapping[props.status.current_step] ?? 0
})

const processStatus = computed<'wait' | 'process' | 'finish' | 'error'>(() => {
  if (props.status?.status === 'failed' || props.taskStatus === 'failed') return 'error'
  if (props.status?.status === 'completed' || props.taskStatus === 'completed') return 'finish'
  return 'process'
})

const inferredStep = computed(() => {
  const labels: Record<string, string> = {
    created: '等待启动',
    parsing: '解析标书',
    waiting_confirm: '等待人工确认',
    analyzing: '资质匹配',
    generating: '资质匹配',
    completed: '分析完成',
    failed: '执行失败',
  }
  return labels[props.taskStatus] ?? props.taskStatus
})

const stepLabel = computed(() => {
  const labels: Record<string, string> = {
    parse: '解析标书',
    wait_confirm: '等待人工确认',
    match: '资质匹配',
    completed: '分析完成',
    failed: '执行失败',
    cancelled: '已取消',
  }
  return props.status ? (labels[props.status.current_step] ?? props.status.current_step) : inferredStep.value
})

const runStatusLabel = computed(() => {
  if (!props.status) return '未找到运行记录'
  const labels: Record<string, string> = {
    running: '运行中',
    waiting_confirm: '等待确认',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[props.status.status] ?? props.status.status
})

const taskStatusLabel = computed(() => {
  const labels: Record<string, string> = {
    created: '已创建',
    parsing: '解析中',
    analyzing: '分析中',
    waiting_confirm: '待确认',
    generating: '生成中',
    completed: '已完成',
    failed: '失败',
  }
  return labels[props.taskStatus] ?? props.taskStatus
})
</script>

<template>
  <div v-loading="loading" class="progress-panel">
    <section class="progress-track">
      <div class="section-heading">
        <div>
          <h3 class="section-title">分析进度</h3>
          <p class="section-subtitle">Agent 按解析、人工确认、资质匹配的顺序执行</p>
        </div>
      </div>
      <el-steps :active="activeStep" :process-status="processStatus" finish-status="success" align-center>
        <el-step title="解析标书" description="提取文本并生成结构化结果" />
        <el-step title="人工确认" description="核对解析结果后继续" />
        <el-step title="资质匹配" description="与公司知识库执行规则匹配" />
        <el-step title="分析完成" description="查看结构化匹配报告" />
      </el-steps>
    </section>

    <section v-if="status" class="run-details">
      <div class="detail-row"><span>当前步骤</span><strong>{{ stepLabel }}</strong></div>
      <div class="detail-row"><span>运行状态</span><strong>{{ runStatusLabel }}</strong></div>
      <div class="detail-row"><span>任务状态</span><strong>{{ taskStatusLabel }}</strong></div>
      <div class="detail-row"><span>启动时间</span><strong>{{ formatDate(status.started_at) }}</strong></div>
      <div class="detail-row"><span>完成时间</span><strong>{{ formatDate(status.completed_at) }}</strong></div>
      <div class="detail-row"><span>确认备注</span><strong>{{ status.confirmation_note || '-' }}</strong></div>
      <div v-if="status.error_message" class="error-message">
        <strong>执行错误</strong>
        <p>{{ status.error_message }}</p>
      </div>
    </section>

    <section v-else-if="taskStatus !== 'created'" class="run-details inferred-details">
      <div class="detail-row"><span>当前步骤</span><strong>{{ stepLabel }}</strong></div>
      <div class="detail-row"><span>运行状态</span><strong>{{ runStatusLabel }}</strong></div>
      <div class="detail-row"><span>任务状态</span><strong>{{ taskStatusLabel }}</strong></div>
      <div class="inferred-message">
        当前进度根据任务状态推断。历史任务可能没有独立的 Agent 运行记录，但仍可继续当前流程。
      </div>
    </section>

    <div v-else class="empty-block">
      <el-empty description="尚未启动 Agent 分析流程" :image-size="80" />
    </div>
  </div>
</template>

<style scoped>
.progress-track {
  padding: 26px 24px 34px;
  border-bottom: 1px solid var(--border-color);
}

.section-heading {
  margin-bottom: 30px;
}

.progress-track :deep(.el-step__title) {
  font-size: 13px;
}

.progress-track :deep(.el-step__description) {
  padding-right: 8px;
  padding-left: 8px;
  font-size: 11px;
  line-height: 1.5;
}

.run-details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 8px 24px 24px;
}

.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 14px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-tertiary);
  font-size: 13px;
}

.detail-row:nth-child(odd) {
  border-right: 1px solid var(--border-color);
}

.detail-row strong {
  max-width: 68%;
  color: var(--text-primary);
  font-weight: 500;
  overflow-wrap: anywhere;
  text-align: right;
}

.error-message {
  grid-column: 1 / -1;
  margin-top: 18px;
  padding: 14px 16px;
  border: 1px solid #f0cbc7;
  border-radius: 6px;
  background: var(--danger-soft);
  color: var(--danger-color);
}

.error-message strong {
  font-size: 13px;
}

.error-message p {
  margin: 5px 0 0;
  color: #81504b;
  font-size: 13px;
  line-height: 1.6;
}

.inferred-details {
  padding-top: 8px;
}

.inferred-message {
  grid-column: 1 / -1;
  margin-top: 18px;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-muted);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
</style>
