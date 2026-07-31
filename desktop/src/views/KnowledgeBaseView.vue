<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Delete,
  EditPen,
  Medal,
  OfficeBuilding,
  Plus,
  Refresh,
  Search,
  TrendCharts,
  Upload,
  User,
  Warning,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { qualificationApi } from '@/api/qualifications'
import type {
  ExpiryWarningItem,
  PaginatedData,
} from '@/types/qualification'

type EntityKey = 'certificates' | 'performances' | 'personnel' | 'companies'

interface FormField {
  key: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'date' | 'select' | 'switch'
  required?: boolean
  options?: { value: string; label: string }[]
  placeholder?: string
}

interface ColumnDef {
  key: string
  label: string
  width?: number
  minWidth?: number
  kind?: 'text' | 'tag' | 'bool' | 'date'
}

interface FilterField {
  key: string
  label: string
  param: string
  type: 'text' | 'select'
  placeholder?: string
  options?: { value: string; label: string }[]
}

interface EntityConfig {
  key: EntityKey
  label: string
  icon: typeof Medal
  emptyText: string
  columns: ColumnDef[]
  formFields: FormField[]
  filters: FilterField[]
  list: (params: Record<string, unknown>) => Promise<PaginatedData<unknown>>
  create: (payload: Record<string, unknown>) => Promise<unknown>
  update: (id: string, payload: Record<string, unknown>) => Promise<unknown>
  remove: (id: string) => Promise<{ id: string; deleted: boolean }>
}

const CERT_STATUS_OPTIONS = [
  { value: 'valid', label: '有效' },
  { value: 'expired', label: '已过期' },
  { value: 'revoked', label: '已撤销' },
]

const BOOL_OPTIONS = [
  { value: 'true', label: '是' },
  { value: 'false', label: '否' },
]

const entities: Record<EntityKey, EntityConfig> = {
  certificates: {
    key: 'certificates',
    label: '资质证书',
    icon: Medal,
    emptyText: '暂无资质证书，可点击新增或批量导入',
    columns: [
      { key: 'name', label: '证书名称', minWidth: 220 },
      { key: 'specialty', label: '专业', minWidth: 140 },
      { key: 'cert_number', label: '证书编号', minWidth: 140 },
      { key: 'valid_period', label: '有效期', minWidth: 170 },
      { key: 'status', label: '状态', width: 90, kind: 'tag' },
    ],
    formFields: [
      { key: 'name', label: '证书名称', type: 'text', required: true },
      { key: 'level', label: '等级', type: 'text' },
      { key: 'specialty', label: '专业', type: 'text' },
      { key: 'cert_number', label: '证书编号', type: 'text' },
      { key: 'issuing_authority', label: '发证机关', type: 'text' },
      { key: 'valid_from', label: '生效日期', type: 'date' },
      { key: 'valid_to', label: '失效日期', type: 'date' },
      {
        key: 'status',
        label: '状态',
        type: 'select',
        options: CERT_STATUS_OPTIONS,
      },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    filters: [
      { key: 'name', label: '证书名称', param: 'name', type: 'text', placeholder: '搜索证书名称' },
      { key: 'status', label: '状态', param: 'status', type: 'select', options: CERT_STATUS_OPTIONS },
      { key: 'is_valid', label: '有效性', param: 'is_valid', type: 'select', options: BOOL_OPTIONS },
    ],
    list: (params) => qualificationApi.listCertificates(params),
    create: (payload) => qualificationApi.createCertificate(payload),
    update: (id, payload) => qualificationApi.updateCertificate(id, payload),
    remove: (id) => qualificationApi.removeCertificate(id),
  },
  performances: {
    key: 'performances',
    label: '业绩',
    icon: TrendCharts,
    emptyText: '暂无业绩记录，可点击新增或批量导入',
    columns: [
      { key: 'project_name', label: '项目名称', minWidth: 220 },
      { key: 'amount', label: '合同金额', minWidth: 130 },
      { key: 'period', label: '项目日期', minWidth: 170 },
      { key: 'is_completed', label: '完成状态', width: 90, kind: 'bool' },
      { key: 'owner_name', label: '业主', minWidth: 120 },
      { key: 'related_qualification', label: '关联资质', minWidth: 140 },
    ],
    formFields: [
      { key: 'project_name', label: '项目名称', type: 'text', required: true },
      { key: 'project_amount', label: '合同金额（元）', type: 'number' },
      { key: 'currency', label: '币种', type: 'text', placeholder: 'CNY' },
      { key: 'start_date', label: '开始日期', type: 'date' },
      { key: 'end_date', label: '结束日期', type: 'date' },
      { key: 'is_completed', label: '是否完成', type: 'switch' },
      { key: 'owner_name', label: '业主名称', type: 'text' },
      { key: 'location', label: '项目地点', type: 'text' },
      { key: 'related_qualification', label: '关联资质', type: 'text' },
      { key: 'description', label: '项目描述', type: 'textarea' },
    ],
    filters: [
      { key: 'keyword', label: '关键词', param: 'keyword', type: 'text', placeholder: '搜索项目、业主或描述' },
      { key: 'is_completed', label: '完成状态', param: 'is_completed', type: 'select', options: BOOL_OPTIONS },
    ],
    list: (params) => qualificationApi.listPerformances(params),
    create: (payload) => qualificationApi.createPerformance(payload),
    update: (id, payload) => qualificationApi.updatePerformance(id, payload),
    remove: (id) => qualificationApi.removePerformance(id),
  },
  personnel: {
    key: 'personnel',
    label: '人员证书',
    icon: User,
    emptyText: '暂无人员证书，可点击新增或批量导入',
    columns: [
      { key: 'person_name', label: '姓名', width: 110 },
      { key: 'cert_type', label: '证书类型', minWidth: 160 },
      { key: 'specialty', label: '专业', minWidth: 140 },
      { key: 'valid_period', label: '有效期', minWidth: 170 },
      { key: 'is_on_job', label: '在职', width: 80, kind: 'bool' },
    ],
    formFields: [
      { key: 'person_name', label: '姓名', type: 'text', required: true },
      { key: 'cert_type', label: '证书类型', type: 'text', required: true },
      { key: 'specialty', label: '专业', type: 'text' },
      { key: 'cert_number', label: '证书编号', type: 'text' },
      { key: 'valid_from', label: '生效日期', type: 'date' },
      { key: 'valid_to', label: '失效日期', type: 'date' },
      { key: 'is_on_job', label: '是否在职', type: 'switch' },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    filters: [
      { key: 'person_name', label: '姓名', param: 'person_name', type: 'text', placeholder: '搜索姓名' },
      { key: 'is_on_job', label: '在职', param: 'is_on_job', type: 'select', options: BOOL_OPTIONS },
      { key: 'is_valid', label: '有效性', param: 'is_valid', type: 'select', options: BOOL_OPTIONS },
    ],
    list: (params) => qualificationApi.listPersonnel(params),
    create: (payload) => qualificationApi.createPersonnel(payload),
    update: (id, payload) => qualificationApi.updatePersonnel(id, payload),
    remove: (id) => qualificationApi.removePersonnel(id),
  },
  companies: {
    key: 'companies',
    label: '公司信息',
    icon: OfficeBuilding,
    emptyText: '暂无公司信息，可点击新增或批量导入',
    columns: [
      { key: 'company_name', label: '公司名称', minWidth: 220 },
      { key: 'legal_person', label: '法定代表人', width: 110 },
      { key: 'registered_capital', label: '注册资本（元）', minWidth: 130 },
      { key: 'establish_date', label: '成立日期', width: 110, kind: 'date' },
      { key: 'contact_info', label: '联系方式', minWidth: 160 },
    ],
    formFields: [
      { key: 'company_name', label: '公司名称', type: 'text', required: true },
      { key: 'legal_person', label: '法定代表人', type: 'text' },
      { key: 'registered_capital', label: '注册资本（元）', type: 'number' },
      { key: 'establish_date', label: '成立日期', type: 'date' },
      { key: 'address', label: '地址', type: 'text' },
      { key: 'contact_info', label: '联系方式', type: 'text' },
    ],
    filters: [
      { key: 'company_name', label: '公司名称', param: 'company_name', type: 'text', placeholder: '搜索公司名称' },
    ],
    list: (params) => qualificationApi.listCompanies(params),
    create: (payload) => qualificationApi.createCompany(payload),
    update: (id, payload) => qualificationApi.updateCompany(id, payload),
    remove: (id) => qualificationApi.removeCompany(id),
  },
}

const entityKeys: EntityKey[] = ['certificates', 'performances', 'personnel', 'companies']
const activeTab = ref<EntityKey>('certificates')
const items = reactive<Record<EntityKey, unknown[]>>({
  certificates: [],
  performances: [],
  personnel: [],
  companies: [],
})
const filters = reactive<Record<EntityKey, Record<string, string>>>({
  certificates: { name: '', status: '', is_valid: '' },
  performances: { keyword: '', is_completed: '' },
  personnel: { person_name: '', is_on_job: '', is_valid: '' },
  companies: { company_name: '' },
})
const loading = ref(false)
const warnings = ref<ExpiryWarningItem[]>([])

const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)
const formValues = reactive<Record<string, unknown>>({})

function currentConfig(): EntityConfig {
  return entities[activeTab.value]
}

function buildParams(key: EntityKey): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  for (const field of entities[key].filters) {
    const raw = filters[key][field.key].trim()
    if (!raw) continue
    params[field.param] = raw === 'true' ? true : raw === 'false' ? false : raw
  }
  return params
}

async function loadTab(key?: string | number): Promise<void> {
  const target = (
    typeof key === 'string' && key in entities ? key : activeTab.value
  ) as EntityKey
  loading.value = true
  try {
    const result = await entities[target].list(buildParams(target))
    items[target] = result.items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadWarnings(): Promise<void> {
  try {
    const result = await qualificationApi.expiryWarnings()
    warnings.value = result.items
  } catch {
    warnings.value = []
  }
}

const statCards = computed(() => {
  const warningCount = warnings.value.filter(
    (item) =>
      item.status === 'expired' ||
      item.status === 'revoked' ||
      item.status === 'off_job',
  ).length
  const expiringCount = warnings.value.filter(
    (item) => item.status === 'expiring',
  ).length
  return [
    ...entityKeys.map((key) => ({
      key,
      label: entities[key].label,
      count: (items[key] as unknown[]).length,
      icon: entities[key].icon,
    })),
    {
      key: 'warnings' as const,
      label: '证书预警',
      count: warningCount + expiringCount,
      icon: Warning,
      alert: warningCount + expiringCount > 0,
    },
  ]
})

function openCreate(): void {
  editingId.value = null
  const config = currentConfig()
  for (const key of Object.keys(formValues)) delete formValues[key]
  for (const field of config.formFields) {
    if (field.type === 'switch') formValues[field.key] = true
    else if (field.type === 'select' && field.options?.length) {
      formValues[field.key] = field.options[0].value
    } else {
      formValues[field.key] = ''
    }
  }
  dialogVisible.value = true
}

function openEdit(row: Record<string, unknown>): void {
  editingId.value = String(row.id)
  const config = currentConfig()
  for (const key of Object.keys(formValues)) delete formValues[key]
  for (const field of config.formFields) {
    const value = row[field.key]
    formValues[field.key] =
      value === null || value === undefined ? '' : (value as unknown)
  }
  dialogVisible.value = true
}

function buildPayload(): Record<string, unknown> {
  const config = currentConfig()
  const payload: Record<string, unknown> = {}
  for (const field of config.formFields) {
    let value = formValues[field.key]
    if (field.type === 'number') {
      value = typeof value === 'number' && Number.isFinite(value) ? value : null
    } else if (typeof value === 'string') {
      const trimmed = value.trim()
      value = trimmed || (field.required ? trimmed : null)
    }
    payload[field.key] = value
  }
  return payload
}

async function save(): Promise<void> {
  const config = currentConfig()
  const payload = buildPayload()
  const requiredMissing = config.formFields
    .filter((field) => field.required && !payload[field.key])
    .map((field) => field.label)
  if (requiredMissing.length) {
    ElMessage.warning(`请填写：${requiredMissing.join('、')}`)
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await config.update(editingId.value, payload)
      ElMessage.success(`${config.label}更新成功`)
    } else {
      await config.create(payload)
      ElMessage.success(`${config.label}创建成功`)
    }
    dialogVisible.value = false
    await Promise.all([loadTab(), loadWarnings()])
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function removeRow(row: Record<string, unknown>): Promise<void> {
  const config = currentConfig()
  const label = String(
    row.project_name || row.name || row.person_name || row.company_name || '该记录',
  )
  try {
    await ElMessageBox.confirm(
      `确定删除「${label}」吗？删除后不可恢复。`,
      `删除${config.label}`,
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await config.remove(String(row.id))
    ElMessage.success('删除成功')
    await Promise.all([loadTab(), loadWarnings()])
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function cellValue(row: Record<string, unknown>, column: ColumnDef): unknown {
  if (column.key === 'valid_period') {
    const from = row.valid_from ? String(row.valid_from).slice(0, 10) : ''
    const to = row.valid_to ? String(row.valid_to).slice(0, 10) : ''
    return from || to ? `${from || '?'} ~ ${to || '长期'}` : '-'
  }
  if (column.key === 'amount') {
    const amount = row.project_amount
    return amount === null || amount === undefined
      ? '-'
      : `${amount} ${row.currency || ''}`.trim()
  }
  if (column.key === 'period') {
    const from = row.start_date ? String(row.start_date).slice(0, 10) : ''
    const to = row.end_date ? String(row.end_date).slice(0, 10) : ''
    return from || to ? `${from || '?'} ~ ${to || '?'}` : '-'
  }
  const value = row[column.key]
  if (column.kind === 'date') {
    return value ? String(value).slice(0, 10) : '-'
  }
  return value === null || value === undefined || value === '' ? '-' : value
}

function statusTag(status: string): { label: string; type: 'success' | 'danger' | 'info' } {
  return (
    {
      valid: { label: '有效', type: 'success' },
      expired: { label: '已过期', type: 'danger' },
      revoked: { label: '已撤销', type: 'info' },
    }[status] ?? { label: status, type: 'info' }
  )
}

function warningText(item: ExpiryWarningItem): string {
  if (item.status === 'expired') return `${item.title} 已过期（${item.detail}）`
  if (item.status === 'revoked') return `${item.title} 已撤销（${item.detail}）`
  if (item.status === 'off_job') return `${item.title} 人员已离职（${item.detail}）`
  return `${item.title} 将于 ${item.days_left} 天后到期（${item.detail}）`
}

async function handleImport(file: File): Promise<void> {
  try {
    const result = await qualificationApi.importExcel(file)
    if (result.failed === 0) {
      ElMessage.success(`导入完成：新增 ${result.created} 条`)
    } else {
      await ElMessageBox.alert(
        `新增 ${result.created} 条，失败 ${result.failed} 条。\n\n${result.errors
          .slice(0, 20)
          .join('\n')}`,
        '导入结果',
        { type: 'warning', confirmButtonText: '知道了' },
      )
    }
    await Promise.all([loadTab(), loadWarnings()])
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function onImportFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void handleImport(file)
  input.value = ''
}

function refreshAll(): void {
  void Promise.all([loadTab(), loadWarnings()])
}

function selectTab(key: string): void {
  if (key !== 'warnings') {
    activeTab.value = key as EntityKey
  }
}

onMounted(() => {
  void loadTab()
  void loadWarnings()
})
</script>

<template>
  <div class="page-container knowledge-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">资质知识库</h1>
        <p class="page-subtitle">
          维护公司信息、资质证书、业绩和人员证书，资质匹配将基于这份数据自动核验。
        </p>
      </div>
      <div class="page-actions">
        <el-button :icon="Refresh" :loading="loading" @click="refreshAll">刷新</el-button>
        <el-button :icon="Upload" @click="$refs.importInput?.click()">导入 Excel</el-button>
        <input
          ref="importInput"
          type="file"
          accept=".xlsx,.xls"
          class="hidden-file-input"
          @change="onImportFile"
        />
      </div>
    </header>

    <div class="stats-row">
      <button
        v-for="card in statCards"
        :key="card.key"
        type="button"
        class="stat-card"
        :class="{ active: activeTab === card.key, alert: card.alert }"
        @click="selectTab(card.key)"
      >
        <span class="stat-icon">
          <el-icon><component :is="card.icon" /></el-icon>
        </span>
        <span class="stat-text">
          <strong>{{ card.count }}</strong>
          <small>{{ card.label }}</small>
        </span>
      </button>
    </div>

    <el-alert
      v-if="warnings.length"
      class="warnings-alert"
      :title="`${warnings.filter((item) => item.status !== 'expiring').length} 项需处理，${warnings.filter((item) => item.status === 'expiring').length} 项即将到期`"
      type="warning"
      :closable="false"
      show-icon
    >
      <ul class="warnings-list">
        <li v-for="item in warnings" :key="`${item.kind}-${item.id}`">
          <span :class="{ urgent: item.status !== 'expiring' }" class="warning-dot" />
          {{ warningText(item) }}
        </li>
      </ul>
    </el-alert>

    <section class="content-surface">
      <div class="tab-toolbar">
        <el-tabs v-model="activeTab" class="knowledge-tabs" @tab-change="loadTab">
          <el-tab-pane v-for="key in entityKeys" :key="key" :name="key">
            <template #label>
              <span class="tab-label">{{ entities[key].label }}</span>
            </template>
          </el-tab-pane>
        </el-tabs>
        <el-button
          type="primary"
          :icon="Plus"
          class="add-button"
          @click="openCreate"
        >
          新增{{ currentConfig().label }}
        </el-button>
      </div>

      <div class="filter-bar">
        <label
          v-for="field in currentConfig().filters"
          :key="field.key"
          class="filter-item"
        >
          <span>{{ field.label }}</span>
          <el-input
            v-if="field.type === 'text'"
            v-model="filters[activeTab][field.key]"
            :prefix-icon="Search"
            :placeholder="field.placeholder"
            clearable
            class="filter-input"
            @keyup.enter="loadTab()"
            @change="loadTab()"
            @clear="loadTab()"
          />
          <el-select
            v-else
            v-model="filters[activeTab][field.key]"
            :placeholder="`全部${field.label}`"
            clearable
            class="filter-select"
            @change="loadTab()"
            @clear="loadTab()"
          >
            <el-option
              v-for="option in field.options"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </label>
      </div>

      <el-table
        v-loading="loading"
        :data="items[activeTab] as Record<string, unknown>[]"
        stripe
        class="knowledge-table"
      >
        <el-table-column
          v-for="column in currentConfig().columns"
          :key="column.key"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
        >
          <template #default="scope">
            <el-tag
              v-if="column.kind === 'tag'"
              :type="statusTag(String(scope.row.status)).type"
              size="small"
              effect="plain"
            >
              {{ statusTag(String(scope.row.status)).label }}
            </el-tag>
            <el-tag
              v-else-if="column.kind === 'bool'"
              :type="scope.row[column.key] ? 'success' : 'info'"
              size="small"
              effect="plain"
            >
              {{ scope.row[column.key] ? '是' : '否' }}
            </el-tag>
            <span v-else>{{ cellValue(scope.row, column) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="scope">
            <div class="row-actions">
              <el-tooltip content="编辑">
                <el-button
                  text
                  class="action-btn"
                  :icon="EditPen"
                  aria-label="编辑"
                  @click="openEdit(scope.row)"
                />
              </el-tooltip>
              <el-tooltip content="删除">
                <el-button
                  text
                  class="action-btn danger-btn"
                  :icon="Delete"
                  aria-label="删除"
                  @click="removeRow(scope.row)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="currentConfig().emptyText" :image-size="76" />
        </template>
      </el-table>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="`${editingId ? '编辑' : '新增'}${currentConfig().label}`"
      width="680px"
      align-center
    >
      <el-form label-position="top" class="entity-form">
        <div class="form-grid">
          <el-form-item
            v-for="field in currentConfig().formFields"
            :key="field.key"
            :label="field.label + (field.required ? ' *' : '')"
            class="form-item"
            :class="{ 'form-item-wide': field.type === 'textarea' }"
          >
            <el-input
              v-if="field.type === 'text'"
              v-model="formValues[field.key]"
              :placeholder="field.placeholder"
            />
            <el-input
              v-else-if="field.type === 'textarea'"
              v-model="formValues[field.key]"
              type="textarea"
              :rows="3"
            />
            <el-input-number
              v-else-if="field.type === 'number'"
              v-model="formValues[field.key]"
              :min="0"
              :controls="false"
              class="number-input"
              placeholder="留空表示未填写"
            />
            <el-date-picker
              v-else-if="field.type === 'date'"
              v-model="formValues[field.key]"
              type="date"
              value-format="YYYY-MM-DD"
              class="date-input"
              placeholder="选择日期"
            />
            <el-select
              v-else-if="field.type === 'select'"
              v-model="formValues[field.key]"
              class="select-input"
            >
              <el-option
                v-for="option in field.options"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-switch v-else v-model="formValues[field.key]" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ editingId ? '保存修改' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.knowledge-page {
  max-width: 1360px;
}

.hidden-file-input {
  display: none;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.stat-card {
  display: flex;
  gap: 12px;
  align-items: center;
  min-height: 72px;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.stat-card:hover {
  border-color: var(--border-strong);
}

.stat-card.active {
  border-color: var(--primary-color);
  background: var(--primary-soft);
}

.stat-card.alert {
  border-color: #ecd5a7;
  background: var(--warning-soft);
}

.stat-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
  background: var(--surface-strong);
  color: var(--text-secondary);
  font-size: 18px;
}

.stat-card.active .stat-icon {
  background: var(--primary-color);
  color: #ffffff;
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
  font-size: 22px;
  line-height: 1.1;
}

.stat-text small {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.warnings-alert {
  margin-bottom: 14px;
}

.warnings-list {
  display: grid;
  max-height: 150px;
  gap: 5px;
  margin: 8px 0 0;
  padding: 0;
  overflow: auto;
  list-style: none;
}

.warnings-list li {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 12px;
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

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 22px;
  border-bottom: 1px solid var(--border-color);
}

.knowledge-tabs {
  min-width: 0;
  flex: 1;
}

.knowledge-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.knowledge-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.knowledge-tabs :deep(.el-tabs__item) {
  height: 50px;
  color: var(--text-secondary);
  font-size: 13px;
}

.knowledge-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary-color);
  font-weight: 600;
}

.add-button {
  flex: 0 0 auto;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  padding: 12px 22px;
  border-bottom: 1px solid var(--border-color);
  background: var(--surface-muted);
}

.filter-item {
  display: grid;
  gap: 5px;
}

.filter-item > span {
  color: var(--text-tertiary);
  font-size: 11px;
}

.filter-input {
  width: 220px;
}

.filter-select {
  width: 140px;
}

.knowledge-table {
  width: 100%;
}

.row-actions {
  display: inline-flex;
  gap: 2px;
  align-items: center;
}

.action-btn {
  width: 30px;
  height: 30px;
  padding: 0;
  color: var(--text-tertiary);
  font-size: 15px;
}

.action-btn:hover {
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.action-btn.danger-btn:hover {
  background: var(--danger-soft);
  color: var(--danger-color);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.form-item-wide {
  grid-column: 1 / -1;
}

.number-input,
.date-input,
.select-input {
  width: 100%;
}

@media (max-width: 1180px) {
  .stats-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
