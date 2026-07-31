<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  Clock,
  Collection,
  Medal,
  Plus,
  Refresh,
  VideoPlay,
  WarningFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { dashboardApi } from '@/api/dashboard'
import StatusTag from '@/components/StatusTag.vue'
import type { DashboardSummary } from '@/types/dashboard'
import type { ExpiryWarningItem } from '@/types/qualification'
import { formatDate } from '@/utils/format'

const router = useRouter()
const summary = ref<DashboardSummary | null>(null)
const loading = ref(false)

async function loadSummary(): Promise<void> {
  loading.value = true
  try {
    summary.value = await dashboardApi.summary()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function warningText(item: ExpiryWarningItem): string {
  if (item.status === 'expired') return `${item.title} 已过期`
  if (item.status === 'revoked') return `${item.title} 已撤销`
  if (item.status === 'off_job') return `${item.title} 人员已离职`
  return `${item.title} 还有 ${item.days_left} 天到期`
}

onMounted(() => {
  void loadSummary()
})
</script>

<template>
  <div v-loading="loading" class="page-container dashboard-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">工作台</h1>
        <p class="page-subtitle">待办任务、证书预警和最近进展一屏掌握。</p>
      </div>
      <div class="page-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadSummary">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="router.push('/tasks/new')">
          新建任务
        </el-button>
      </div>
    </header>

    <div v-if="summary" class="stats-row">
      <button type="button" class="stat-card warn" @click="router.push('/tasks')">
        <span class="stat-icon"><el-icon><Clock /></el-icon></span>
        <span class="stat-text">
          <strong>{{ summary.task_counts.waiting_confirm }}</strong>
          <small>待确认</small>
        </span>
      </button>
      <button type="button" class="stat-card" @click="router.push('/tasks')">
        <span class="stat-icon"><el-icon><VideoPlay /></el-icon></span>
        <span class="stat-text">
          <strong>{{ summary.task_counts.running }}</strong>
          <small>执行中</small>
        </span>
      </button>
      <button type="button" class="stat-card" @click="router.push('/tasks')">
        <span class="stat-icon"><el-icon><CircleCheckFilled /></el-icon></span>
        <span class="stat-text">
          <strong>{{ summary.task_counts.completed }}</strong>
          <small>已完成</small>
        </span>
      </button>
      <button type="button" class="stat-card" @click="router.push('/tasks')">
        <span class="stat-icon danger"><el-icon><CircleCloseFilled /></el-icon></span>
        <span class="stat-text">
          <strong>{{ summary.task_counts.failed }}</strong>
          <small>失败</small>
        </span>
      </button>
      <button
        type="button"
        class="stat-card"
        :class="{ alert: summary.warning_expired + summary.warning_expiring > 0 }"
        @click="router.push('/knowledge')"
      >
        <span class="stat-icon"><el-icon><WarningFilled /></el-icon></span>
        <span class="stat-text">
          <strong>{{ summary.warning_expired + summary.warning_expiring }}</strong>
          <small>证书预警</small>
        </span>
      </button>
    </div>

    <div v-if="summary" class="dashboard-grid">
      <section class="content-surface recent-surface">
        <header class="surface-head">
          <div>
            <h2 class="section-title">最近任务</h2>
            <p class="section-subtitle">按创建时间排列的最新 6 个任务</p>
          </div>
          <el-button text type="primary" @click="router.push('/tasks')">查看全部</el-button>
        </header>
        <el-table :data="summary.recent_tasks" stripe class="recent-table" @row-click="(row) => router.push(`/tasks/${row.id}`)">
          <el-table-column label="项目名称" min-width="240">
            <template #default="scope">
              <div class="project-cell">
                <strong>{{ scope.row.project_name }}</strong>
                <small>{{ formatDate(scope.row.created_at) }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="scope"><StatusTag :status="scope.row.status" /></template>
          </el-table-column>
          <el-table-column prop="file_count" label="附件" width="80" align="center">
            <template #default="scope">{{ scope.row.file_count }} 个</template>
          </el-table-column>
          <template #empty>
            <el-empty description="还没有任务，创建一个吧" :image-size="72" />
          </template>
        </el-table>
      </section>

      <div class="side-column">
        <section class="content-surface side-surface">
          <header class="surface-head">
            <div>
              <h2 class="section-title">待确认任务</h2>
              <p class="section-subtitle">解析完成，等待人工核对</p>
            </div>
            <span v-if="summary.pending_confirm_tasks.length" class="count-badge">
              {{ summary.pending_confirm_tasks.length }}
            </span>
          </header>
          <div v-if="summary.pending_confirm_tasks.length" class="pending-list">
            <button
              v-for="task in summary.pending_confirm_tasks"
              :key="task.id"
              type="button"
              class="pending-item"
              @click="router.push(`/tasks/${task.id}`)"
            >
              <span class="pending-dot" />
              <span class="pending-name">{{ task.project_name }}</span>
              <small>去处理</small>
            </button>
          </div>
          <el-empty v-else description="没有待确认任务" :image-size="56" />
        </section>

        <section class="content-surface side-surface">
          <header class="surface-head">
            <div>
              <h2 class="section-title">证书预警</h2>
              <p class="section-subtitle">临期与失效提醒</p>
            </div>
            <span v-if="summary.warnings.length" class="count-badge alert">
              {{ summary.warnings.length }}
            </span>
          </header>
          <div v-if="summary.warnings.length" class="warning-list">
            <div
              v-for="item in summary.warnings.slice(0, 6)"
              :key="`${item.kind}-${item.id}`"
              class="warning-item"
            >
              <span :class="{ urgent: item.status !== 'expiring' }" class="warning-dot" />
              <span>{{ warningText(item) }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无证书预警" :image-size="56" />
        </section>

        <section class="quick-actions">
          <button type="button" class="quick-action" @click="router.push('/templates')">
            <el-icon><Collection /></el-icon>
            <span>解析模板</span>
          </button>
          <button type="button" class="quick-action" @click="router.push('/knowledge')">
            <el-icon><Medal /></el-icon>
            <span>资质知识库</span>
          </button>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-page {
  max-width: 1480px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  gap: 12px;
  align-items: center;
  min-height: 76px;
  padding: 14px 18px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.stat-card:hover {
  border-color: var(--border-strong);
  background: var(--surface-muted);
}

.stat-card.alert {
  border-color: #ecd5a7;
  background: var(--warning-soft);
}

.stat-icon {
  display: grid;
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 9px;
  background: var(--surface-strong);
  color: var(--text-secondary);
  font-size: 19px;
}

.stat-card.warn .stat-icon {
  background: var(--warning-soft);
  color: var(--warning-color);
}

.stat-icon.danger {
  background: var(--danger-soft);
  color: var(--danger-color);
}

.stat-card.alert .stat-icon {
  background: var(--warning-color);
  color: #ffffff;
}

.stat-text {
  display: grid;
  min-width: 0;
}

.stat-text strong {
  color: var(--text-primary);
  font-size: 23px;
  line-height: 1.1;
}

.stat-text small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
}

.recent-surface {
  overflow: hidden;
}

.surface-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 22px;
  border-bottom: 1px solid var(--border-color);
}

.recent-table {
  width: 100%;
}

.recent-table :deep(.el-table__row) {
  cursor: pointer;
}

.project-cell strong,
.project-cell small {
  display: block;
}

.project-cell strong {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.project-cell small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.side-column {
  display: grid;
  gap: 16px;
}

.side-surface {
  overflow: hidden;
}

.count-badge {
  display: grid;
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  place-items: center;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.count-badge.alert {
  background: var(--warning-soft);
  color: var(--warning-color);
}

.pending-list {
  display: grid;
  padding: 8px 12px;
}

.pending-item {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 44px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
}

.pending-item:hover {
  background: var(--surface-muted);
}

.pending-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--warning-color);
}

.pending-name {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-item small {
  color: var(--primary-color);
  font-size: 11px;
}

.warning-list {
  display: grid;
  gap: 8px;
  padding: 12px 16px;
}

.warning-item {
  display: flex;
  gap: 9px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.warning-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--warning-color);
}

.warning-dot.urgent {
  background: var(--danger-color);
}

.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.quick-action {
  display: flex;
  gap: 9px;
  align-items: center;
  justify-content: center;
  min-height: 58px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  transition: border-color 0.15s ease, background-color 0.15s ease,
    color 0.15s ease;
}

.quick-action:hover {
  border-color: var(--primary-color);
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.quick-action .el-icon {
  font-size: 17px;
}

@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .stats-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
