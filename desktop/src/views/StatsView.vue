<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { statsApi } from '@/api/stats'
import type { StatsSummary } from '@/types/stats'

const router = useRouter()
const summary = ref<StatsSummary | null>(null)
const loading = ref(false)

const PURPOSE_LABELS: Record<string, string> = {
  parse: '标书解析',
  template_suggest: 'AI 生成模板',
}

function purposeLabel(purpose: string): string {
  return PURPOSE_LABELS[purpose] ?? purpose
}

function formatTokens(value: number): string {
  return value.toLocaleString('zh-CN')
}

function formatCost(value: string): string {
  const number = Number(value)
  if (!number) return '$0'
  return `$${number.toFixed(number >= 1 ? 2 : 4)}`
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-'
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} 分钟`
  return `${(seconds / 3600).toFixed(2)} 小时`
}

function formatLatency(ms: number | null): string {
  if (ms === null) return '-'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} 秒` : `${ms} ms`
}

const maxDailyCost = computed(() => {
  const values = (summary.value?.daily ?? []).map((item) => Number(item.total_cost))
  return Math.max(0, ...values)
})

function barHeight(cost: string): number {
  if (!maxDailyCost.value) return 0
  const value = Number(cost)
  if (!value) return 0
  return Math.max(4, Math.round((value / maxDailyCost.value) * 100))
}

function dayLabel(date: string): string {
  return date.slice(5)
}

async function loadSummary(): Promise<void> {
  loading.value = true
  try {
    summary.value = await statsApi.summary()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadSummary()
})
</script>

<template>
  <div v-loading="loading" class="page-container stats-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">统计与成本</h1>
        <p class="page-subtitle">
          所有用到 AI 的调用都会自动记录：解析、AI 生成模板，以及以后新增的任何 AI 功能。
        </p>
      </div>
      <div class="page-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadSummary">刷新</el-button>
      </div>
    </header>

    <div v-if="summary" class="llm-cards">
      <div class="stat-card">
        <span class="stat-label">AI 调用次数</span>
        <strong>{{ summary.llm.total_calls }}</strong>
        <small>成功 {{ summary.llm.success_calls }} · 失败 {{ summary.llm.failed_calls }}</small>
      </div>
      <div class="stat-card">
        <span class="stat-label">总 Token 消耗</span>
        <strong>{{ formatTokens(summary.llm.total_tokens) }}</strong>
        <small>输入 + 输出合计</small>
      </div>
      <div class="stat-card accent">
        <span class="stat-label">预估成本（USD）</span>
        <strong>{{ formatCost(summary.llm.total_cost) }}</strong>
        <small>按模型单价估算</small>
      </div>
      <div class="stat-card">
        <span class="stat-label">平均响应耗时</span>
        <strong>{{ formatLatency(summary.llm.avg_latency_ms) }}</strong>
        <small>单次 AI 调用</small>
      </div>
      <div class="stat-card">
        <span class="stat-label">任务成功率</span>
        <strong>{{ summary.tasks.success_rate === null ? '-' : `${summary.tasks.success_rate}%` }}</strong>
        <small>完成 {{ summary.tasks.completed_runs }} · 失败 {{ summary.tasks.failed_runs }}</small>
      </div>
      <div class="stat-card">
        <span class="stat-label">任务平均耗时</span>
        <strong>{{ formatDuration(summary.tasks.avg_duration_seconds) }}</strong>
        <small>共 {{ summary.tasks.total_runs }} 次运行</small>
      </div>
    </div>

    <div v-if="summary" class="stats-grid">
      <section class="content-surface">
        <header class="surface-head">
          <div>
            <h2 class="section-title">近 14 天成本趋势</h2>
            <p class="section-subtitle">按天汇总的预估成本，柱子高度按最高一天归一化</p>
          </div>
        </header>
        <div class="chart-wrap">
          <div v-if="summary.daily.some((item) => item.calls > 0)" class="bar-chart">
            <div
              v-for="item in summary.daily"
              :key="item.date"
              class="bar-col"
              :title="`${item.date} · ${item.calls} 次调用 · ${formatTokens(item.total_tokens)} tokens · ${formatCost(item.total_cost)}`"
            >
              <div class="bar" :style="{ height: `${barHeight(item.total_cost)}px` }" />
              <span class="bar-label">{{ dayLabel(item.date) }}</span>
            </div>
          </div>
          <el-empty
            v-else
            description="近 14 天还没有 AI 调用记录"
            :image-size="72"
          />
        </div>
      </section>

      <section class="content-surface">
        <header class="surface-head">
          <div>
            <h2 class="section-title">按用途</h2>
            <p class="section-subtitle">每个 AI 场景的调用与成本</p>
          </div>
        </header>
        <el-table :data="summary.by_purpose" stripe>
          <el-table-column label="用途" min-width="140">
            <template #default="scope">{{ purposeLabel(scope.row.purpose) }}</template>
          </el-table-column>
          <el-table-column prop="calls" label="调用" width="80" align="center" />
          <el-table-column prop="success_calls" label="成功" width="80" align="center" />
          <el-table-column label="Token" width="120" align="right">
            <template #default="scope">{{ formatTokens(scope.row.total_tokens) }}</template>
          </el-table-column>
          <el-table-column label="成本" width="110" align="right">
            <template #default="scope">{{ formatCost(scope.row.total_cost) }}</template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无 AI 调用记录" :image-size="56" />
          </template>
        </el-table>
      </section>

      <section class="content-surface">
        <header class="surface-head">
          <div>
            <h2 class="section-title">按模型</h2>
            <p class="section-subtitle">各模型的 Token 与成本占比</p>
          </div>
        </header>
        <el-table :data="summary.by_model" stripe>
          <el-table-column prop="model" label="模型" min-width="180" />
          <el-table-column prop="calls" label="调用" width="90" align="center" />
          <el-table-column label="Token" width="130" align="right">
            <template #default="scope">{{ formatTokens(scope.row.total_tokens) }}</template>
          </el-table-column>
          <el-table-column label="成本" width="120" align="right">
            <template #default="scope">{{ formatCost(scope.row.total_cost) }}</template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无 AI 调用记录" :image-size="56" />
          </template>
        </el-table>
      </section>

      <section class="content-surface">
        <header class="surface-head">
          <div>
            <h2 class="section-title">按任务</h2>
            <p class="section-subtitle">AI 成本最高的 8 个任务</p>
          </div>
        </header>
        <el-table :data="summary.by_task" stripe @row-click="(row) => router.push(`/tasks/${row.task_id}`)">
          <el-table-column prop="task_name" label="项目名称" min-width="200">
            <template #default="scope">
              <span class="task-link">{{ scope.row.task_name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="calls" label="调用" width="80" align="center" />
          <el-table-column label="Token" width="120" align="right">
            <template #default="scope">{{ formatTokens(scope.row.total_tokens) }}</template>
          </el-table-column>
          <el-table-column label="成本" width="110" align="right">
            <template #default="scope">{{ formatCost(scope.row.total_cost) }}</template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无带 AI 成本的任务" :image-size="56" />
          </template>
        </el-table>
      </section>
    </div>
  </div>
</template>

<style scoped>
.stats-page {
  max-width: 1480px;
}

.llm-cards {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  display: grid;
  gap: 4px;
  min-height: 96px;
  padding: 16px 18px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
}

.stat-card.accent {
  border-color: #b9d8c7;
  background: var(--primary-soft);
}

.stat-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.stat-card strong {
  color: var(--text-primary);
  font-size: 22px;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-card small {
  color: var(--text-tertiary);
  font-size: 11px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.content-surface {
  overflow: hidden;
}

.surface-head {
  padding: 16px 22px;
  border-bottom: 1px solid var(--border-color);
}

.chart-wrap {
  min-height: 220px;
  padding: 20px 22px;
}

.bar-chart {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  height: 180px;
}

.bar-col {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 6px;
  justify-items: center;
}

.bar {
  width: 100%;
  max-width: 34px;
  border-radius: 4px 4px 0 0;
  background: linear-gradient(180deg, #2b9b68 0%, #18794e 100%);
  transition: height 0.3s ease;
}

.bar-label {
  color: var(--text-tertiary);
  font-size: 10px;
  transform: rotate(-45deg);
  transform-origin: top center;
  white-space: nowrap;
}

.task-link {
  color: var(--primary-dark);
  cursor: pointer;
  font-weight: 500;
}

.content-surface :deep(.el-table__row) {
  cursor: pointer;
}

@media (max-width: 1180px) {
  .llm-cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
