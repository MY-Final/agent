<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, DocumentAdd, QuestionFilled, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules, type UploadFile, type UploadRawFile } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { taskApi } from '@/api/tasks'
import { templateApi } from '@/api/templates'
import type { ParseTemplateRecord } from '@/types/template'

interface CreateForm {
  projectName: string
  remark: string
  templateId: string
}

const router = useRouter()
const formRef = ref<FormInstance>()
const form = ref<CreateForm>({ projectName: '', remark: '', templateId: '' })
const templates = ref<ParseTemplateRecord[]>([])
const templatesLoading = ref(false)
const selectedFile = ref<File | null>(null)
const submitting = ref(false)

const rules: FormRules<CreateForm> = {
  projectName: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 1, max: 255, message: '项目名称不能超过 255 个字符', trigger: 'blur' },
  ],
}

const fileList = computed<UploadFile[]>(() => selectedFile.value ? [{
  name: selectedFile.value.name,
  size: selectedFile.value.size,
  status: 'ready',
  uid: selectedFile.value.lastModified,
  raw: selectedFile.value as UploadRawFile,
}] : [])

function handleFileChange(uploadFile: UploadFile): void {
  const raw = uploadFile.raw
  if (!raw) return
  const extension = raw.name.split('.').pop()?.toLowerCase()
  if (!['pdf', 'docx'].includes(extension || '')) {
    selectedFile.value = null
    ElMessage.warning('第一版解析流程支持 PDF 和 DOCX 文件')
    return
  }
  selectedFile.value = raw
}

function clearFile(): void {
  selectedFile.value = null
}

async function loadTemplates(): Promise<void> {
  templatesLoading.value = true
  try {
    templates.value = await templateApi.list()
    const defaultTemplate = templates.value.find((item) => item.is_default)
    form.value.templateId = defaultTemplate?.id ?? ''
  } catch (error) {
    ElMessage.error(`模板加载失败：${getErrorMessage(error)}`)
  } finally {
    templatesLoading.value = false
  }
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!selectedFile.value) {
    ElMessage.warning('请选择需要分析的标书文件')
    return
  }

  submitting.value = true
  let taskId: string | null = null
  try {
    const task = await taskApi.create({
      project_name: form.value.projectName.trim(),
      remark: form.value.remark.trim() || null,
      source: 'desktop',
      parse_template_id: form.value.templateId || null,
    })
    taskId = task.id
    await taskApi.uploadFile(task.id, selectedFile.value)
    ElMessage.success('任务创建并上传成功')
    await router.push(`/tasks/${task.id}`)
  } catch (error) {
    const suffix = taskId ? '；任务已创建，可进入详情页重新上传附件' : ''
    ElMessage.error(`${getErrorMessage(error)}${suffix}`)
    if (taskId) await router.push(`/tasks/${taskId}`)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void loadTemplates()
})
</script>

<template>
  <div class="page-container create-page">
    <header class="page-header">
      <div>
        <el-button text :icon="ArrowLeft" class="back-button" @click="router.push('/tasks')">返回任务列表</el-button>
        <h1 class="page-title">新建分析任务</h1>
        <p class="page-subtitle">填写项目基础信息并上传一份标书，创建后即可启动 Agent 分析。</p>
      </div>
      <el-button text :icon="QuestionFilled" @click="router.push({ name: 'guide', hash: '#quickstart' })">
        使用示例
      </el-button>
    </header>

    <div class="create-layout">
      <section class="content-surface form-surface">
        <div class="form-section-heading">
          <span class="section-icon"><el-icon><DocumentAdd /></el-icon></span>
          <div>
            <h2 class="section-title">任务信息</h2>
            <p class="section-subtitle">项目名称用于任务识别，备注可记录招标单位或内部负责人。</p>
          </div>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
          <el-form-item label="项目名称" prop="projectName">
            <el-input v-model="form.projectName" maxlength="255" show-word-limit placeholder="例如：某市数据中心建设项目" />
          </el-form-item>
          <el-form-item label="解析模板">
            <el-select
              v-model="form.templateId"
              :loading="templatesLoading"
              class="template-select"
              placeholder="使用默认模板"
            >
              <el-option
                v-for="template in templates"
                :key="template.id"
                :label="`${template.name}（${template.version}）`"
                :value="template.id"
              />
            </el-select>
            <div class="template-help">决定解析时提取哪些字段，可在「解析模板」页管理。</div>
          </el-form-item>
          <el-form-item label="备注（可选）">
            <el-input
              v-model="form.remark"
              type="textarea"
              :rows="4"
              maxlength="2000"
              show-word-limit
              placeholder="记录任务背景、负责人或其他补充信息"
            />
          </el-form-item>
        </el-form>
      </section>

      <section class="content-surface upload-surface">
        <div class="form-section-heading">
          <span class="section-icon"><el-icon><UploadFilled /></el-icon></span>
          <div>
            <h2 class="section-title">标书附件</h2>
            <p class="section-subtitle">支持文字版或扫描版 PDF，以及 DOCX 文件。</p>
          </div>
        </div>

        <el-upload
          drag
          action="#"
          :auto-upload="false"
          :limit="1"
          :file-list="fileList"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          :on-change="handleFileChange"
          :on-remove="clearFile"
          :on-exceed="() => ElMessage.warning('第一版每个任务请选择一份主标书')"
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-copy">将文件拖到这里，或 <em>点击选择文件</em></div>
          <template #tip>
            <div class="upload-tip">文件将直接上传到后端配置的 MinIO，桌面端不会保存副本。</div>
          </template>
        </el-upload>
      </section>
    </div>

    <footer class="create-actions">
      <el-button @click="router.push('/tasks')">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        {{ submitting ? '正在创建并上传' : '创建任务' }}
      </el-button>
    </footer>
  </div>
</template>

<style scoped>
.create-page {
  max-width: 1120px;
}

.back-button {
  margin: 0 0 8px -12px;
  color: var(--text-secondary);
}

.create-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.75fr);
  gap: 16px;
}

.form-surface,
.upload-surface {
  min-height: 390px;
  padding: 24px;
}

.form-section-heading {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border-color);
}

.section-icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 6px;
  background: var(--primary-soft);
  color: var(--primary-color);
  font-size: 17px;
}

.upload-surface :deep(.el-upload) {
  display: block;
}

.upload-surface :deep(.el-upload-dragger) {
  display: flex;
  width: 100%;
  min-height: 230px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-color: var(--border-strong);
  border-radius: 7px;
  background: var(--surface-muted);
}

.upload-surface :deep(.el-upload-dragger:hover) {
  border-color: var(--primary-color);
  background: #f3f9f6;
}

.upload-icon {
  margin-bottom: 14px;
  color: var(--primary-color);
  font-size: 38px;
}

.upload-copy {
  color: var(--text-secondary);
  font-size: 13px;
}

.upload-copy em {
  color: var(--primary-color);
  font-style: normal;
  font-weight: 600;
}

.upload-tip {
  margin-top: 10px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.6;
}

.template-select {
  width: 100%;
}

.template-help {
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.6;
}

.create-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--border-color);
}

@media (max-width: 1050px) {
  .create-layout {
    grid-template-columns: 1fr;
  }
}
</style>
