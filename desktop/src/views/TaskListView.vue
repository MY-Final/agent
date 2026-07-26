<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Delete, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { taskApi } from '@/api/tasks'
import StatusTag from '@/components/StatusTag.vue'
import { useTasksStore } from '@/stores/tasks'
import type { TaskStatus } from '@/types/task'
import { formatDate } from '@/utils/format'

const router = useRouter()
const tasksStore = useTasksStore()
const statusFilter = ref<TaskStatus | ''>('')
const deletingId = ref<string | null>(null)

const statusOptions: Array<{ value: TaskStatus; label: string }> = [
  { value: 'created', label: '待分析' },
  { value: 'parsing', label: '解析中' },
  { value: 'waiting_confirm', label: '待确认' },
  { value: 'analyzing', label: '匹配中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
]

async function loadTasks(showMessage = false): Promise<void> {
  try {
    await tasksStore.fetchTasks(statusFilter.value || undefined)
    if (showMessage) ElMessage.success('任务列表已刷新')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function deleteTask(taskId: string, taskName: string): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `删除“${taskName}”后，关联的数据库记录和 MinIO 文件将一并清理。`,
      '确认删除任务',
      { type: 'warning', confirmButtonText: '删除任务', cancelButtonText: '取消' },
    )
    deletingId.value = taskId
    await taskApi.remove(taskId)
    ElMessage.success('任务已删除')
    await loadTasks()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getErrorMessage(error))
  } finally {
    deletingId.value = null
  }
}

onMounted(() => loadTasks())
</script>

<template>
  <div class="page-container task-list-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">分析任务</h1>
        <p class="page-subtitle">管理标书文件，启动分析流程并跟踪每个任务的处理状态。</p>
      </div>
      <div class="page-actions">
        <el-button :icon="Refresh" :loading="tasksStore.loading" @click="loadTasks(true)">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="router.push('/tasks/new')">新建任务</el-button>
      </div>
    </header>

    <section class="task-overview">
      <div>
        <span>全部任务</span>
        <strong>{{ tasksStore.total }}</strong>
      </div>
      <div class="overview-separator" />
      <p>最近创建和更新的任务会显示在列表前部。</p>
      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        clearable
        class="status-filter"
        :suffix-icon="Search"
        @change="loadTasks()"
        @clear="loadTasks()"
      >
        <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
    </section>

    <section class="content-surface table-surface">
      <el-table
        v-loading="tasksStore.loading"
        :data="tasksStore.items"
        row-key="id"
        @row-click="(row) => router.push(`/tasks/${row.id}`)"
      >
        <el-table-column label="项目名称" min-width="280">
          <template #default="scope">
            <div class="project-cell">
              <strong>{{ scope.row.project_name }}</strong>
              <small>{{ scope.row.remark || '暂无备注' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="scope"><StatusTag :status="scope.row.status" /></template>
        </el-table-column>
        <el-table-column prop="file_count" label="附件" width="90" align="center">
          <template #default="scope">{{ scope.row.file_count }} 个</template>
        </el-table-column>
        <el-table-column label="创建时间" width="175">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="175">
          <template #default="scope">{{ formatDate(scope.row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="scope">
            <el-tooltip content="删除任务" placement="top">
              <el-button
                text
                type="danger"
                :icon="Delete"
                :loading="deletingId === scope.row.id"
                aria-label="删除任务"
                @click.stop="deleteTask(scope.row.id, scope.row.project_name)"
              />
            </el-tooltip>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有分析任务">
            <el-button type="primary" :icon="Plus" @click="router.push('/tasks/new')">创建第一个任务</el-button>
          </el-empty>
        </template>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.task-overview {
  display: flex;
  min-height: 68px;
  align-items: center;
  gap: 18px;
  margin-bottom: 14px;
  padding: 0 18px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
}

.task-overview > div:first-child {
  display: flex;
  align-items: baseline;
  gap: 9px;
}

.task-overview span,
.task-overview p {
  color: var(--text-tertiary);
  font-size: 12px;
}

.task-overview strong {
  color: var(--text-primary);
  font-size: 23px;
}

.task-overview p {
  flex: 1;
  margin: 0;
}

.overview-separator {
  width: 1px;
  height: 26px;
  background: var(--border-color);
}

.status-filter {
  width: 150px;
}

.table-surface {
  overflow: hidden;
}

.table-surface :deep(.el-table__row) {
  cursor: pointer;
}

.project-cell strong,
.project-cell small {
  display: block;
}

.project-cell strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-cell small {
  overflow: hidden;
  margin-top: 4px;
  color: var(--text-tertiary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
