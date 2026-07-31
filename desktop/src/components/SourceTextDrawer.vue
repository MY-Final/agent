<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Document, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { taskApi } from '@/api/tasks'
import type { ParseSourceTextItem } from '@/types/results'
import type { PdfInfo, TaskFile } from '@/types/task'
import { getStoredBackendUrl, normalizeBackendUrl } from '@/utils/settings'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  taskId: string
  parseResultId: string | null
  highlight: string
  files?: TaskFile[]
}>()

const texts = ref<ParseSourceTextItem[]>([])
const loading = ref(false)
const query = ref('')
const contentRef = ref<HTMLElement>()
const mode = ref<'text' | 'pdf'>('text')
const selectedFileId = ref('')
const pdfInfo = ref<PdfInfo | null>(null)
const currentPage = ref(1)

const pdfFiles = computed(() =>
  (props.files ?? []).filter((file) =>
    file.original_filename.toLowerCase().endsWith('.pdf'),
  ),
)

const currentPageUrl = computed(() => {
  if (mode.value !== 'pdf' || !selectedFileId.value) return null
  return `${normalizeBackendUrl(getStoredBackendUrl())}/api/v1/tasks/${
    props.taskId
  }/files/${selectedFileId.value}/pages/${currentPage.value}`
})

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function highlighted(text: string): string {
  const keyword = query.value.trim()
  const escaped = escapeHtml(text)
  if (!keyword) return escaped
  const escapedKeyword = escapeHtml(keyword)
  const parts = escaped.split(escapedKeyword)
  if (parts.length === 1) return escaped
  return parts.join(`<mark class="src-mark">${escapedKeyword}</mark>`)
}

async function scrollToFirstMark(): Promise<void> {
  await nextTick()
  contentRef.value?.querySelector('.src-mark')?.scrollIntoView({
    block: 'center',
  })
}

async function loadTexts(): Promise<void> {
  if (!props.parseResultId) return
  loading.value = true
  try {
    texts.value = await taskApi.getSourceText(props.taskId, props.parseResultId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

watch(visible, (open) => {
  if (open) {
    mode.value = 'text'
    query.value = props.highlight
    void loadTexts().then(() => scrollToFirstMark())
  }
})

watch(mode, (value) => {
  if (value === 'pdf') {
    selectedFileId.value = pdfFiles.value[0]?.id ?? ''
  }
})

watch(selectedFileId, async (fileId) => {
  pdfInfo.value = null
  currentPage.value = 1
  if (!fileId) return
  try {
    pdfInfo.value = await taskApi.getPdfInfo(props.taskId, fileId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
})

watch(query, () => {
  void scrollToFirstMark()
})

watch(
  () => props.highlight,
  (value) => {
    query.value = value
  },
)
</script>

<template>
  <el-drawer v-model="visible" size="min(620px, 46vw)" class="source-drawer">
    <template #header>
      <div class="source-heading">
        <h2>标书原文对照</h2>
        <p>人工核对时对照原始文本，支持按原文片段定位高亮。</p>
      </div>
    </template>

    <div class="source-body">
      <div class="mode-tabs" role="tablist">
        <button
          type="button"
          class="mode-tab"
          :class="{ active: mode === 'text' }"
          @click="mode = 'text'"
        >
          文本对照
        </button>
        <button
          v-if="pdfFiles.length"
          type="button"
          class="mode-tab"
          :class="{ active: mode === 'pdf' }"
          @click="mode = 'pdf'"
        >
          PDF 页面
        </button>
      </div>

      <template v-if="mode === 'text'">
        <el-input
          v-model="query"
          class="source-search"
          :prefix-icon="Search"
          placeholder="输入原文片段，回车定位"
          clearable
          @keyup.enter="scrollToFirstMark"
        />

        <div v-loading="loading" ref="contentRef" class="source-content">
          <section v-for="item in texts" :key="item.filename" class="source-file">
            <header class="source-file-head">
              <el-icon><Document /></el-icon>
              <strong>{{ item.filename }}</strong>
              <small v-if="item.extraction_method">提取方式：{{ item.extraction_method }}</small>
            </header>
            <pre class="source-text" v-html="highlighted(item.text)" />
          </section>
          <el-empty
            v-if="!loading && !texts.length"
            description="该版本没有保存原文文本"
            :image-size="80"
          />
        </div>
      </template>

      <template v-else>
        <div class="pdf-toolbar">
          <el-select
            v-model="selectedFileId"
            size="small"
            class="pdf-file-select"
            placeholder="选择 PDF 文件"
          >
            <el-option
              v-for="file in pdfFiles"
              :key="file.id"
              :label="file.original_filename"
              :value="file.id"
            />
          </el-select>
          <span v-if="pdfInfo" class="pdf-pages">共 {{ pdfInfo.total_pages }} 页</span>
        </div>

        <div class="pdf-viewer">
          <img
            v-if="currentPageUrl"
            :src="currentPageUrl"
            :alt="`PDF 第 ${currentPage} 页`"
            class="pdf-image"
          />
          <el-empty
            v-else
            description="该文件没有可预览的 PDF 页面"
            :image-size="80"
          />
        </div>

        <div class="pdf-nav">
          <el-button
            size="small"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          >
            上一页
          </el-button>
          <el-input-number
            v-model="currentPage"
            :min="1"
            :max="pdfInfo?.total_pages ?? 1"
            size="small"
            :controls="false"
            class="page-input"
          />
          <span class="page-total">/ {{ pdfInfo?.total_pages ?? '-' }}</span>
          <el-button
            size="small"
            :disabled="currentPage >= (pdfInfo?.total_pages ?? 1)"
            @click="currentPage += 1"
          >
            下一页
          </el-button>
        </div>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.source-heading h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
}

.source-heading p {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

.source-body {
  display: grid;
  gap: 12px;
}

.source-search {
  flex: 0 0 auto;
}

.mode-tabs {
  display: inline-flex;
  gap: 2px;
  align-self: flex-start;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--surface-strong);
}

.mode-tab {
  height: 24px;
  padding: 0 12px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 11px;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.mode-tab.active {
  background: var(--surface-color);
  color: var(--primary-dark);
  box-shadow: 0 1px 2px rgba(31, 41, 36, 0.08);
  font-weight: 600;
}

.source-content {
  display: grid;
  gap: 18px;
  min-height: 200px;
  overflow: auto;
}

.source-file-head {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.source-file-head .el-icon {
  color: var(--primary-color);
}

.source-file-head strong {
  color: var(--text-primary);
  font-size: 12px;
}

.source-file-head small {
  color: var(--text-tertiary);
  font-size: 11px;
}

.source-text {
  margin: 0;
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-muted);
  color: var(--text-secondary);
  font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
  font-size: 12px;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-all;
}

.source-text :deep(.src-mark) {
  padding: 1px 3px;
  border-radius: 3px;
  background: #ffe08a;
  color: var(--text-primary);
  font-weight: 600;
}

.pdf-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.pdf-file-select {
  width: 100%;
}

.pdf-pages {
  flex: 0 0 auto;
  color: var(--text-tertiary);
  font-size: 11px;
}

.pdf-viewer {
  display: grid;
  min-height: 300px;
  place-items: center;
  overflow: auto;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--surface-muted);
}

.pdf-image {
  display: block;
  width: 100%;
  max-width: 760px;
  background: #ffffff;
  box-shadow: 0 2px 10px rgba(31, 41, 36, 0.08);
}

.pdf-nav {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
}

.page-input {
  width: 72px;
}

.page-total {
  color: var(--text-tertiary);
  font-size: 12px;
}
</style>
