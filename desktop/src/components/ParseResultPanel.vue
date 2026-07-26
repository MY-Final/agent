<script setup lang="ts">
import { computed } from 'vue'
import { Document, WarningFilled } from '@element-plus/icons-vue'
import type { ParseResultRecord } from '@/types/results'
import { formatDate, formatValue } from '@/utils/format'

const props = defineProps<{
  record: ParseResultRecord | null
  loading?: boolean
}>()

const result = computed(() => props.record?.result ?? null)
const scoreEntries = computed(() => Object.entries(result.value?.scoring_method ?? {}))
const dateEntries = computed(() => Object.entries(result.value?.key_dates ?? {}))
</script>

<template>
  <div v-loading="loading" class="result-panel">
    <template v-if="record?.status === 'failed'">
      <el-alert
        title="解析失败"
        :description="record.error_message || '未记录具体错误，请查看后端日志。'"
        type="error"
        :closable="false"
        show-icon
      />
    </template>

    <template v-else-if="result">
      <section class="result-section overview-section">
        <div class="section-heading">
          <div>
            <h3 class="section-title">项目概览</h3>
            <p class="section-subtitle">结构化结果生成于 {{ formatDate(record?.created_at) }}</p>
          </div>
          <el-tag v-if="result.confidence !== null" type="success" effect="plain">
            置信度 {{ Math.round(result.confidence * 100) }}%
          </el-tag>
        </div>
        <el-descriptions :column="3" border class="overview-descriptions">
          <el-descriptions-item label="项目名称">{{ result.project_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目编号">{{ result.project_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购人">{{ result.purchaser || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预算金额">{{ result.budget || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目地点">{{ result.location || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目工期">{{ result.duration || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="result.raw_summary" class="summary-copy">
          <el-icon><Document /></el-icon>
          <p>{{ result.raw_summary }}</p>
        </div>
      </section>

      <section class="result-section">
        <div class="section-heading">
          <div>
            <h3 class="section-title">资格要求</h3>
            <p class="section-subtitle">共提取 {{ result.qualifications.length }} 条要求</p>
          </div>
        </div>
        <el-table v-if="result.qualifications.length" :data="result.qualifications" stripe>
          <el-table-column prop="category" label="类别" width="110" />
          <el-table-column label="要求" min-width="320">
            <template #default="scope">
              <div class="requirement-cell">
                <span>{{ scope.row.description }}</span>
                <small v-if="scope.row.original_text">原文：{{ scope.row.original_text }}</small>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="性质" width="100" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.is_mandatory ? 'danger' : 'info'" effect="plain" size="small">
                {{ scope.row.is_mandatory ? '强制' : '一般' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="未提取到资格要求" :image-size="72" />
      </section>

      <section class="result-section split-section">
        <div class="split-column">
          <div class="section-heading">
            <div>
              <h3 class="section-title">评分办法</h3>
              <p class="section-subtitle">商务、技术和价格等评分信息</p>
            </div>
          </div>
          <div v-if="scoreEntries.length" class="key-value-list">
            <div v-for="([key, value]) in scoreEntries" :key="key" class="key-value-row">
              <span>{{ key }}</span>
              <strong>{{ formatValue(value) }}</strong>
            </div>
          </div>
          <el-empty v-else description="暂无评分办法" :image-size="60" />
        </div>

        <div class="split-column">
          <div class="section-heading">
            <div>
              <h3 class="section-title">关键时间</h3>
              <p class="section-subtitle">报名、投标截止和开标等节点</p>
            </div>
          </div>
          <div v-if="dateEntries.length" class="key-value-list">
            <div v-for="([key, value]) in dateEntries" :key="key" class="key-value-row">
              <span>{{ key }}</span>
              <strong>{{ formatValue(value) }}</strong>
            </div>
          </div>
          <el-empty v-else description="暂无关键时间" :image-size="60" />
        </div>
      </section>

      <section class="result-section split-section">
        <div class="split-column">
          <div class="section-heading">
            <div>
              <h3 class="section-title">废标条款</h3>
              <p class="section-subtitle">需要优先核验的否决条件</p>
            </div>
          </div>
          <ul v-if="result.disqualification_items.length" class="point-list danger-list">
            <li v-for="item in result.disqualification_items" :key="item">
              <el-icon><WarningFilled /></el-icon>
              <span>{{ item }}</span>
            </li>
          </ul>
          <el-empty v-else description="未提取到废标条款" :image-size="60" />
        </div>

        <div class="split-column">
          <div class="section-heading">
            <div>
              <h3 class="section-title">其他要点</h3>
              <p class="section-subtitle">值得关注的补充信息</p>
            </div>
          </div>
          <ul v-if="result.other_key_points.length" class="point-list">
            <li v-for="item in result.other_key_points" :key="item"><span>{{ item }}</span></li>
          </ul>
          <el-empty v-else description="暂无其他要点" :image-size="60" />
        </div>
      </section>
    </template>

    <div v-else class="empty-block">
      <el-empty description="启动分析后，这里将展示结构化解析结果" :image-size="88" />
    </div>
  </div>
</template>

<style scoped>
.result-panel {
  min-height: 360px;
}

.result-section {
  padding: 24px;
  border-bottom: 1px solid var(--border-color);
}

.result-section:last-child {
  border-bottom: 0;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}

.overview-descriptions :deep(.el-descriptions__label) {
  width: 100px;
  color: var(--text-secondary);
  font-size: 12px;
}

.overview-descriptions :deep(.el-descriptions__content) {
  color: var(--text-primary);
  font-weight: 500;
}

.summary-copy {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 16px;
  padding: 14px 16px;
  border-left: 3px solid var(--primary-color);
  background: var(--primary-soft);
  color: var(--text-secondary);
}

.summary-copy .el-icon {
  flex: 0 0 auto;
  margin-top: 3px;
  color: var(--primary-color);
}

.summary-copy p {
  margin: 0;
  line-height: 1.75;
}

.requirement-cell span,
.requirement-cell small {
  display: block;
}

.requirement-cell span {
  color: var(--text-primary);
  line-height: 1.6;
}

.requirement-cell small {
  margin-top: 5px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

.split-section {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  padding: 0;
}

.split-column {
  min-width: 0;
  padding: 24px;
}

.split-column + .split-column {
  border-left: 1px solid var(--border-color);
}

.key-value-list {
  border-top: 1px solid var(--border-color);
}

.key-value-row {
  display: grid;
  grid-template-columns: minmax(100px, 0.42fr) minmax(0, 1fr);
  gap: 16px;
  padding: 11px 0;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  line-height: 1.6;
}

.key-value-row span {
  color: var(--text-tertiary);
}

.key-value-row strong {
  color: var(--text-primary);
  font-weight: 500;
  text-align: right;
  overflow-wrap: anywhere;
}

.point-list {
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.point-list li {
  position: relative;
  display: flex;
  gap: 9px;
  align-items: flex-start;
  padding: 11px 12px 11px 28px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
}

.point-list li::before {
  position: absolute;
  top: 18px;
  left: 14px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--primary-color);
  content: '';
}

.danger-list li {
  padding-left: 12px;
  border-color: #f2d0cc;
  background: #fffafa;
}

.danger-list li::before {
  display: none;
}

.danger-list .el-icon {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--danger-color);
}

@media (max-width: 1120px) {
  .split-section {
    grid-template-columns: 1fr;
  }

  .split-column + .split-column {
    border-top: 1px solid var(--border-color);
    border-left: 0;
  }
}
</style>
