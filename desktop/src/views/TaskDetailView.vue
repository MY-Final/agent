<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Check,
  Download,
  Files,
  Refresh,
  RefreshLeft,
  Upload,
  VideoPlay,
} from '@element-plus/icons-vue'
import { isTauri } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import { ElMessage, type UploadFile, type UploadRawFile } from 'element-plus'
import { getErrorMessage, isNotFoundError } from '@/api/client'
import { taskApi } from '@/api/tasks'
import { templateApi } from '@/api/templates'
import AgentProgressPanel from '@/components/AgentProgressPanel.vue'
import MatchResultPanel from '@/components/MatchResultPanel.vue'
import ParseResultPanel from '@/components/ParseResultPanel.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { AgentStatus } from '@/types/agent'
import type { MatchResultRecord, ParseResultRecord } from '@/types/results'
import type { TaskDetail, TaskFile } from '@/types/task'
import type { ParseTemplateRecord } from '@/types/template'
import { formatDate, formatFileSize } from '@/utils/format'
import { getStoredBackendUrl, normalizeBackendUrl } from '@/utils/settings'

const route = useRoute()
const router = useRouter()
const taskId = computed(() => String(route.params.id))
const task = ref<TaskDetail | null>(null)
const files = ref<TaskFile[]>([])
const agentStatus = ref<AgentStatus | null>(null)
const parseRecord = ref<ParseResultRecord | null>(null)
const parseHistory = ref<ParseResultRecord[]>([])
const matchRecord = ref<MatchResultRecord | null>(null)
const activeTab = ref('files')
const pageLoading = ref(false)
const refreshing = ref(false)
const agentActionLoading = ref(false)
const uploadLoading = ref(false)
const confirmDialogVisible = ref(false)
const confirmationRemark = ref('')
const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const rejectTemplateId = ref('')
const templates = ref<ParseTemplateRecord[]>([])
const templatesLoading = ref(false)
let pollTimer: number | null = null

const exportUrl = computed(() => {
  if (!parseRecord.value) return null
  return `${normalizeBackendUrl(getStoredBackendUrl())}/api/v1/tasks/${taskId.value}/export`
})

const isWaitingConfirm = computed(() =>
  agentStatus.value?.is_waiting_confirmation || task.value?.status === 'waiting_confirm',
)
const isAgentRunning = computed(() =>
  agentStatus.value?.status === 'running' || ['parsing', 'analyzing', 'generating'].includes(task.value?.status || ''),
)
const canStart = computed(() =>
  Boolean(task.value && files.value.length > 0 && !isAgentRunning.value && !isWaitingConfirm.value),
)
const primaryHint = computed(() => {
  if (isWaitingConfirm.value) return '解析已完成，请核对解析结果并确认继续资质匹配。'
  if (isAgentRunning.value) return task.value?.status === 'analyzing' ? 'Agent 正在匹配公司资质，请稍候。' : 'Agent 正在解析标书，耗时取决于文件大小和 OCR 情况。'
  if (task.value?.status === 'completed') return '分析流程已完成，可以查看解析结果和匹配报告。'
  if (task.value?.status === 'failed') return '最近一次分析失败，请查看进度中的错误信息后重试。'
  if (!files.value.length) return '请先上传一份 PDF 或 DOCX 标书文件。'
  return '附件已就绪，可以启动 Agent 分析流程。'
})

async function loadTask(): Promise<void> {
  task.value = await taskApi.get(taskId.value)
}

async function loadFiles(): Promise<void> {
  files.value = await taskApi.listFiles(taskId.value)
}

async function loadAgentStatus(): Promise<void> {
  try {
    agentStatus.value = await taskApi.getAgentStatus(taskId.value)
  } catch (error) {
    if (isNotFoundError(error)) {
      agentStatus.value = null
      return
    }
    throw error
  }
}

async function loadParseResults(): Promise<void> {
  try {
    parseHistory.value = await taskApi.listParseResults(taskId.value)
    parseRecord.value = parseHistory.value[0] ?? null
  } catch (error) {
    if (isNotFoundError(error)) {
      parseHistory.value = []
      parseRecord.value = null
      return
    }
    throw error
  }
}

async function loadMatchResult(): Promise<void> {
  try {
    matchRecord.value = await taskApi.getMatchResult(taskId.value)
  } catch (error) {
    if (isNotFoundError(error)) {
      matchRecord.value = null
      return
    }
    throw error
  }
}

async function loadTemplates(): Promise<void> {
  templatesLoading.value = true
  try {
    templates.value = await templateApi.list()
  } catch (error) {
    ElMessage.error(`模板加载失败：${getErrorMessage(error)}`)
  } finally {
    templatesLoading.value = false
  }
}

async function refreshAll(showMessage = false): Promise<void> {
  refreshing.value = true
  try {
    await Promise.all([loadTask(), loadFiles(), loadAgentStatus(), loadParseResults(), loadMatchResult()])
    if (showMessage) ElMessage.success('任务信息已刷新')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    refreshing.value = false
  }
}

async function initialize(): Promise<void> {
  pageLoading.value = true
  try {
    await refreshAll()
  } finally {
    pageLoading.value = false
  }
}

async function startAgent(): Promise<void> {
  if (!canStart.value) return
  agentActionLoading.value = true
  try {
    agentStatus.value = await taskApi.startAgent(taskId.value)
    await Promise.all([loadTask(), loadParseResults()])
    activeTab.value = agentStatus.value.is_waiting_confirmation ? 'parse' : 'progress'
    ElMessage.success(agentStatus.value.is_waiting_confirmation ? '解析完成，请确认解析结果' : 'Agent 已启动')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    await refreshAll()
  } finally {
    agentActionLoading.value = false
  }
}

async function confirmAgent(): Promise<void> {
  agentActionLoading.value = true
  try {
    agentStatus.value = await taskApi.confirmAgent(taskId.value, confirmationRemark.value)
    confirmDialogVisible.value = false
    confirmationRemark.value = ''
    await Promise.all([loadTask(), loadMatchResult()])
    activeTab.value = agentStatus.value.status === 'completed' ? 'match' : 'progress'
    ElMessage.success(agentStatus.value.status === 'completed' ? '资质匹配完成' : 'Agent 已继续执行')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    await refreshAll()
  } finally {
    agentActionLoading.value = false
  }
}

function openRejectDialog(): void {
  rejectReason.value = ''
  const defaultTemplate = templates.value.find((item) => item.is_default)
  rejectTemplateId.value =
    task.value?.parse_template_id || defaultTemplate?.id || ''
  rejectDialogVisible.value = true
}

async function rejectAndReparse(): Promise<void> {
  if (!parseRecord.value) return
  agentActionLoading.value = true
  try {
    agentStatus.value = await taskApi.rejectAndReparse(
      taskId.value,
      parseRecord.value.id,
      rejectReason.value,
      rejectTemplateId.value,
    )
    rejectDialogVisible.value = false
    rejectReason.value = ''
    await refreshAll()
    activeTab.value = 'progress'
    ElMessage.success('已驳回原解析结果并开始重新解析')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    agentActionLoading.value = false
  }
}

async function handleSupplementFile(uploadFile: UploadFile): Promise<void> {
  const raw = uploadFile.raw
  if (!raw) return
  const extension = raw.name.split('.').pop()?.toLowerCase()
  if (!['pdf', 'docx'].includes(extension || '')) {
    ElMessage.warning('仅支持 PDF 和 DOCX 文件')
    return
  }
  uploadLoading.value = true
  try {
    await taskApi.uploadFile(taskId.value, raw as UploadRawFile)
    await Promise.all([loadTask(), loadFiles()])
    ElMessage.success('附件上传成功')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    uploadLoading.value = false
  }
}

async function downloadFile(file: TaskFile): Promise<void> {
  try {
    const result = await taskApi.getDownloadUrl(taskId.value, file.id)
    if (isTauri()) {
      await openUrl(result.url)
    } else {
      window.open(result.url, '_blank', 'noopener,noreferrer')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function exportReport(): Promise<void> {
  if (!exportUrl.value) return
  try {
    if (isTauri()) {
      await openUrl(exportUrl.value)
    } else {
      window.open(exportUrl.value, '_blank', 'noopener,noreferrer')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function updatePolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
  if (isAgentRunning.value) {
    pollTimer = window.setInterval(() => {
      void refreshAll()
    }, 5000)
  }
}

watch(isAgentRunning, updatePolling)
onMounted(() => {
  void initialize()
  void loadTemplates()
})
onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
})
</script>

<template>
  <div v-loading="pageLoading" class="page-container detail-page">
    <template v-if="task">
      <header class="detail-header">
        <div class="detail-title-block">
          <el-button text :icon="ArrowLeft" class="back-button" @click="router.push('/tasks')">返回任务列表</el-button>
          <div class="title-line">
            <h1 class="page-title">{{ task.project_name }}</h1>
            <StatusTag :status="task.status" />
          </div>
          <p class="task-meta">
            <span>创建于 {{ formatDate(task.created_at) }}</span>
            <span v-if="task.source">来源：{{ task.source }}</span>
          </p>
        </div>
        <div class="page-actions detail-actions">
          <el-button :icon="Refresh" :loading="refreshing" @click="refreshAll(true)">刷新</el-button>
          <el-button
            v-if="parseRecord"
            :icon="Download"
            :disabled="!exportUrl"
            @click="exportReport"
          >
            导出报告
          </el-button>
          <el-button
            v-if="isWaitingConfirm"
            type="warning"
            :icon="Check"
            :loading="agentActionLoading"
            @click="confirmDialogVisible = true"
          >
            确认并继续
          </el-button>
          <el-button
            v-if="isWaitingConfirm && parseRecord"
            type="danger"
            plain
            :icon="RefreshLeft"
            :loading="agentActionLoading"
            @click="openRejectDialog"
          >
            驳回并重新解析
          </el-button>
          <el-button
            v-else
            type="primary"
            :icon="VideoPlay"
            :disabled="!canStart"
            :loading="agentActionLoading"
            @click="startAgent"
          >
            {{ task.status === 'completed' || task.status === 'failed' ? '重新分析' : '启动分析' }}
          </el-button>
        </div>
      </header>

      <section class="status-banner" :class="{ waiting: isWaitingConfirm, running: isAgentRunning, failed: task.status === 'failed' }">
        <span class="banner-mark" />
        <div>
          <strong>{{ isWaitingConfirm ? '等待人工确认' : isAgentRunning ? 'Agent 正在运行' : task.status === 'completed' ? '分析已完成' : task.status === 'failed' ? '分析执行失败' : '任务已就绪' }}</strong>
          <p>{{ primaryHint }}</p>
        </div>
        <el-button v-if="isWaitingConfirm" type="warning" plain size="small" @click="activeTab = 'parse'">查看解析结果</el-button>
      </section>

      <section v-if="task.remark" class="remark-line">
        <span>任务备注</span>
        <p>{{ task.remark }}</p>
      </section>

      <section class="content-surface detail-tabs">
        <el-tabs v-model="activeTab">
          <el-tab-pane name="files">
            <template #label><span class="tab-label"><el-icon><Files /></el-icon>文件信息</span></template>
            <div class="tab-toolbar">
              <div>
                <h2 class="section-title">已上传文件</h2>
                <p class="section-subtitle">文件存储在 MinIO，点击下载可获取临时访问链接。</p>
              </div>
              <el-upload
                action="#"
                :auto-upload="false"
                :show-file-list="false"
                accept=".pdf,.docx"
                :on-change="handleSupplementFile"
              >
                <el-button :icon="Upload" :loading="uploadLoading">补充上传</el-button>
              </el-upload>
            </div>
            <el-table :data="files" class="file-table">
              <el-table-column label="文件名" min-width="300">
                <template #default="scope">
                  <div class="file-name-cell">
                    <span class="file-extension">{{ scope.row.original_filename.split('.').pop()?.toUpperCase() || 'FILE' }}</span>
                    <div><strong>{{ scope.row.original_filename }}</strong><small>{{ scope.row.content_type }}</small></div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="110">
                <template #default="scope">{{ formatFileSize(scope.row.file_size) }}</template>
              </el-table-column>
              <el-table-column label="上传时间" width="180">
                <template #default="scope">{{ formatDate(scope.row.uploaded_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="90" align="center">
                <template #default="scope">
                  <el-tooltip content="下载文件">
                    <el-button text type="primary" :icon="Download" aria-label="下载文件" @click="downloadFile(scope.row)" />
                  </el-tooltip>
                </template>
              </el-table-column>
              <template #empty><el-empty description="暂无附件，请先上传标书" :image-size="76" /></template>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="解析结果" name="parse">
            <ParseResultPanel
              :task-id="taskId"
              :record="parseRecord"
              :history="parseHistory"
              :files="files"
              :loading="refreshing"
              @saved="refreshAll"
              @export="exportReport"
            />
          </el-tab-pane>

          <el-tab-pane label="匹配结果" name="match">
            <MatchResultPanel :record="matchRecord" :loading="refreshing" />
          </el-tab-pane>

          <el-tab-pane label="状态与进度" name="progress">
            <AgentProgressPanel :status="agentStatus" :task-status="task.status" :loading="refreshing" />
          </el-tab-pane>
        </el-tabs>
      </section>
    </template>

    <el-dialog v-model="confirmDialogVisible" title="确认解析结果并继续" width="520px">
      <el-alert
        title="确认后将立即执行公司资质匹配"
        description="请先在“解析结果”中核对资格要求、评分办法、废标条款和关键时间。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-position="top" class="confirm-form">
        <el-form-item label="确认备注（可选）">
          <el-input
            v-model="confirmationRemark"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="记录本次人工核对结论或补充说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="agentActionLoading" @click="confirmAgent">确认并开始匹配</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectDialogVisible" title="驳回解析结果并重新解析" width="520px">
      <el-alert
        title="原解析结果将标记为已驳回，并保留在历史版本中"
        description="确认后将立即重新解析，新结果会作为新版本追加，可随时切回对比。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-position="top" class="confirm-form">
        <el-form-item label="重新解析使用的模板">
          <el-select
            v-model="rejectTemplateId"
            :loading="templatesLoading"
            class="reject-template-select"
          >
            <el-option label="跟随默认模板" value="" />
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="`${template.name}（${template.version}）`"
              :value="template.id"
            />
          </el-select>
          <div class="template-help">选择后会同时作为该任务的模板保存，后续解析沿用。</div>
        </el-form-item>
        <el-form-item label="驳回原因（可选）">
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="记录驳回原因，便于后续版本对比"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="agentActionLoading" @click="rejectAndReparse">
          驳回并重新解析
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-page {
  max-width: 1520px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}

.back-button {
  margin: 0 0 8px -12px;
  color: var(--text-secondary);
}

.title-line {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-meta {
  display: flex;
  gap: 16px;
  margin: 7px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

.detail-actions {
  padding-top: 30px;
}

.status-banner {
  display: flex;
  min-height: 74px;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding: 13px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
}

.status-banner > div {
  min-width: 0;
  flex: 1;
}

.status-banner strong {
  color: var(--text-primary);
  font-size: 13px;
}

.status-banner p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.banner-mark {
  width: 7px;
  height: 36px;
  flex: 0 0 auto;
  border-radius: 3px;
  background: var(--primary-color);
}

.status-banner.waiting {
  border-color: #ecd5a7;
  background: var(--warning-soft);
}

.status-banner.waiting .banner-mark {
  background: var(--warning-color);
}

.status-banner.running .banner-mark {
  animation: banner-pulse 1.5s ease-in-out infinite;
}

.status-banner.failed {
  border-color: #f0cbc7;
  background: var(--danger-soft);
}

.status-banner.failed .banner-mark {
  background: var(--danger-color);
}

.remark-line {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 14px;
  padding: 12px 16px;
  border-left: 3px solid var(--border-strong);
  color: var(--text-secondary);
}

.remark-line span {
  flex: 0 0 auto;
  color: var(--text-tertiary);
  font-size: 12px;
}

.remark-line p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}

.detail-tabs {
  overflow: hidden;
}

.detail-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 22px;
  border-bottom: 1px solid var(--border-color);
}

.detail-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.detail-tabs :deep(.el-tabs__item) {
  height: 52px;
  padding: 0 20px;
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary-color);
  font-weight: 600;
}

.tab-label {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.tab-toolbar {
  display: flex;
  min-height: 78px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border-color);
}

.file-table {
  width: 100%;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 11px;
}

.file-extension {
  display: grid;
  width: 42px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  background: var(--surface-muted);
  color: var(--primary-dark);
  font-size: 9px;
  font-weight: 700;
}

.file-name-cell strong,
.file-name-cell small {
  display: block;
}

.file-name-cell strong {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.file-name-cell small {
  margin-top: 3px;
  color: var(--text-tertiary);
  font-size: 10px;
}

.confirm-form {
  margin-top: 20px;
}

.reject-template-select {
  width: 100%;
}

.template-help {
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.6;
}

@keyframes banner-pulse {
  50% { opacity: 0.35; }
}

@media (prefers-reduced-motion: reduce) {
  .status-banner.running .banner-mark { animation: none; }
}
</style>
