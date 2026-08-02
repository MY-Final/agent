<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Collection,
  DataAnalysis,
  Files,
  MagicStick,
  Medal,
  Plus,
  QuestionFilled,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const TOC_ITEMS = [
  { anchor: 'quickstart', label: '快速上手', icon: Files },
  { anchor: 'templates', label: '解析模板', icon: Collection },
  { anchor: 'knowledge', label: '资质知识库', icon: Medal },
  { anchor: 'stats', label: '统计与成本', icon: DataAnalysis },
  { anchor: 'faq', label: '常见问题', icon: QuestionFilled },
]

const TEMPLATE_EXAMPLES = [
  {
    title: '投标关键商务条款',
    description: '重点关注投标保证金、付款方式和工期违约条款',
    result:
      '生成「投标保证金（金额/形式/到账时间）」「付款方式（预付款/进度款/尾款）」「工期与违约（工期要求/违约金比例）」等区块，并自动补充「资格要求」表格区块。',
  },
  {
    title: '评分与废标要点',
    description: '提取评分办法、废标条款和联合体投标要求',
    result:
      '生成「评分标准」表格区块（评分项/分值/得分标准）、「废标条款」要点列表（红色警示）和「联合体要求」字段描述区块。',
  },
  {
    title: '工期质量要求',
    description: '关注项目工期、质量标准和验收要求',
    result:
      '生成「工期要求」「质量标准」「验收要求」三个字段描述区块，工期用日期类型、质量标准用要点列表，便于后续核验。',
  },
]

const SECTION_KIND_ROWS = [
  { kind: 'grid', name: '字段描述', usage: '一组「名称 + 值」的字段', example: '投标保证金：金额、形式、到账时间' },
  { kind: 'table', name: '表格', usage: '有行有列的结构化数据', example: '评分标准、人员证书清单' },
  { kind: 'key_value', name: '键值对', usage: '一对一的说明条目', example: '付款方式、工期要求' },
  { kind: 'list', name: '要点列表', usage: '多条并列的要点', example: '废标条款、注意事项' },
]

const FIELD_TYPE_ROWS = [
  { type: '文本', usage: '普通文字，如招标单位、项目地点' },
  { type: '数字', usage: '数值，如投标人数、工期天数' },
  { type: '金额', usage: '带金额格式，如投标保证金 50 万元' },
  { type: '日期', usage: '日期时间，如投标截止时间' },
  { type: '布尔', usage: '是否类，如是否允许联合体投标' },
]

const TONE_ROWS = [
  { tone: '中性', usage: '默认展示' },
  { tone: '品牌绿', usage: '重点强调' },
  { tone: '琥珀', usage: '关注 / 预警类' },
  { tone: '红色', usage: '风险 / 废标类，最醒目' },
  { tone: '绿色', usage: '符合 / 通过类' },
  { tone: '蓝灰', usage: '中性说明' },
]

const FAQ_ITEMS = [
  {
    q: '连接不上后端 / 一直提示「连接设置」？',
    a: '在侧边栏底部打开连接设置，确认后端地址为 http://<服务器IP>:8000，且服务已启动（浏览器可访问 /health）。',
  },
  {
    q: '解析后字段大量为空？',
    a: '扫描版 PDF 没有文本层，需要开启 OCR 重新构建镜像（WITH_OCR=true docker compose up -d --build backend），或改用带文本层的 PDF / DOCX。',
  },
  {
    q: '改了模板但结果没变化？',
    a: '模板在解析启动时读取。已启动或已完成的任务不会重新应用，请新建任务，或在「新建任务」里指定目标模板后重新解析。',
  },
  {
    q: '如何对比两次解析结果？',
    a: '任务详情保留多版本溯源，可并排对比不同解析版本，差异字段会高亮显示。',
  },
  {
    q: '资质匹配结果不准确？',
    a: '匹配基于确定性规则逐项核验（证书等级、有效期、业绩金额、人员数量等）。请先确认资质知识库中的数据完整、准确。',
  },
  {
    q: '删除模板会有什么影响？',
    a: '已引用该模板的任务会自动回退到默认模板或内置种子模板，历史解析结果不受影响。',
  },
]

function scrollToAnchor(anchor: string): void {
  document.getElementById(anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function tryExample(index: number): void {
  void router.push({ path: '/templates', query: { suggest: String(index) } })
}

watch(
  () => route.hash,
  (hash) => {
    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="page-container guide-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">使用指南</h1>
        <p class="page-subtitle">从创建任务到资质匹配的完整流程，以及解析模板、资质知识库的用法与示例。</p>
      </div>
    </header>

    <nav class="guide-toc content-surface" aria-label="指南目录">
      <button
        v-for="item in TOC_ITEMS"
        :key="item.anchor"
        type="button"
        @click="scrollToAnchor(item.anchor)"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <section id="quickstart" class="guide-section content-surface guide-anchor">
      <h2 class="guide-section-title">快速上手：完成一次投标分析</h2>
      <p class="guide-text">整个主流程共五步，前四步在任务详情里连续完成，最后一步可在统计页复盘。</p>
      <el-steps :active="5" align-center class="guide-steps">
        <el-step title="新建任务" description="填写项目名称，上传 PDF / DOCX 标书" />
        <el-step title="启动解析" description="Agent 按模板自动结构化提取" />
        <el-step title="人工确认" description="对照原文核查 / 修正字段，可驳回重解析" />
        <el-step title="资质匹配" description="确认后自动按规则匹配公司资质" />
        <el-step title="查看报告" description="导出 Excel 报告，查看统计与成本" />
      </el-steps>
      <div class="guide-step-actions">
        <el-button type="primary" :icon="Plus" @click="router.push('/tasks/new')">去新建任务</el-button>
        <el-button :icon="Files" @click="router.push('/tasks')">查看任务列表</el-button>
        <el-button :icon="DataAnalysis" @click="router.push('/stats')">查看统计</el-button>
      </div>
    </section>

    <section id="templates" class="guide-section content-surface guide-anchor">
      <h2 class="guide-section-title">解析模板：AI 生成与人工编辑</h2>
      <p class="guide-text">
        模板决定标书解析提取哪些字段、前端如何展示。你不需要懂代码，以下两种方式任选：
      </p>

      <div class="guide-cards">
        <div class="guide-card">
          <h3><el-icon><MagicStick /></el-icon> AI 生成模板</h3>
          <p>用一句话描述提取重点，AI 生成完整模板建议，你在编辑器里确认后保存。</p>
          <ul>
            <li>适合：第一次配置、不熟悉字段设计</li>
            <li>特点：快，几分钟拿到可用模板</li>
          </ul>
        </div>
        <div class="guide-card">
          <h3><el-icon><Collection /></el-icon> 手工新建 / 编辑</h3>
          <p>像搭积木一样添加区块、字段、表格列，展示方式完全自定义。</p>
          <ul>
            <li>适合：已有模板微调、公司固定格式</li>
            <li>特点：可控，字段结构和展示完全自己定</li>
          </ul>
        </div>
      </div>

      <h3 class="guide-sub-title">示例：三步用 AI 生成一套模板</h3>
      <p class="guide-text">点「一键试用」会直接打开模板页并填好描述，输入内容也可以自由修改。</p>
      <div class="example-grid">
        <article v-for="(example, index) in TEMPLATE_EXAMPLES" :key="example.title" class="example-card">
          <div class="example-card-head">
            <strong>{{ example.title }}</strong>
            <el-button type="primary" size="small" :icon="MagicStick" @click="tryExample(index)">
              一键试用
            </el-button>
          </div>
          <p class="example-desc">{{ example.description }}</p>
          <p class="example-result">{{ example.result }}</p>
        </article>
      </div>
      <el-alert
        class="guide-note"
        title="完整操作路径"
        description="模板页 →「AI 生成模板」→ 输入描述（可选粘贴参考原文）→ 生成建议 → 在编辑器中检查区块和字段 → 保存 → 设为默认。"
        type="info"
        :closable="false"
        show-icon
      />

      <h3 class="guide-sub-title">手工编辑速查</h3>
      <h4 class="guide-sub-title-small">区块类型</h4>
      <el-table class="guide-table" :data="SECTION_KIND_ROWS" size="small" stripe>
        <el-table-column label="类型" width="120">
          <template #default="scope"><code class="guide-code">{{ scope.row.kind }}</code></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="110" />
        <el-table-column prop="usage" label="用途" min-width="190" />
        <el-table-column prop="example" label="例子" min-width="230" />
      </el-table>

      <h4 class="guide-sub-title-small">字段类型</h4>
      <el-table class="guide-table" :data="FIELD_TYPE_ROWS" size="small" stripe>
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="usage" label="用途" />
      </el-table>

      <h4 class="guide-sub-title-small">展示色调</h4>
      <el-table class="guide-table" :data="TONE_ROWS" size="small" stripe>
        <el-table-column prop="tone" label="色调" width="100" />
        <el-table-column prop="usage" label="适用场景" />
      </el-table>

      <h3 class="guide-sub-title">模板选择与版本</h3>
      <ul class="guide-list">
        <li>选择规则：任务指定模板 → 默认模板 → 内置种子模板，新建任务时可以指定模板。</li>
        <li>多版本溯源：每次解析独立成版本，任务详情支持并排对比与差异高亮。</li>
      </ul>
    </section>

    <section id="knowledge" class="guide-section content-surface guide-anchor">
      <h2 class="guide-section-title">资质知识库</h2>
      <ul class="guide-list">
        <li>四类数据：公司信息、资质证书、业绩、人员证书，支持搜索筛选。</li>
        <li>证书预警：90 天内到期、过期、撤销、离职都会在工作台首页提醒。</li>
        <li>批量导入：Excel 表格可一次导入，按数据模板整理后上传即可。</li>
      </ul>
      <el-button :icon="Medal" @click="router.push('/knowledge')">前往资质知识库</el-button>
    </section>

    <section id="stats" class="guide-section content-surface guide-anchor">
      <h2 class="guide-section-title">统计与成本</h2>
      <p class="guide-text">
        所有 AI 调用都会自动记录 token、耗时、预估成本和成功 / 失败。统计页可查看调用趋势、
        按用途 / 模型 / 任务分布、任务成功率与平均耗时。
      </p>
      <el-button :icon="DataAnalysis" @click="router.push('/stats')">前往统计页</el-button>
    </section>

    <section id="faq" class="guide-section content-surface guide-anchor">
      <h2 class="guide-section-title">常见问题</h2>
      <el-collapse>
        <el-collapse-item v-for="item in FAQ_ITEMS" :key="item.q" :title="item.q">
          <p class="faq-answer">{{ item.a }}</p>
        </el-collapse-item>
      </el-collapse>
    </section>
  </div>
</template>

<style scoped>
.guide-page {
  max-width: 1120px;
}

.guide-toc {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
  padding: 12px 16px;
}

.guide-toc button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.guide-toc button:hover {
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.guide-section {
  margin-bottom: 20px;
  padding: 24px 28px 28px;
}

.guide-anchor {
  scroll-margin-top: 20px;
}

.guide-section-title {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 700;
}

.guide-text {
  margin: 0 0 16px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.guide-sub-title {
  margin: 26px 0 12px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.guide-sub-title-small {
  margin: 18px 0 10px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.guide-steps {
  margin: 18px 0 20px;
}

.guide-steps :deep(.el-step__description) {
  font-size: 12px;
}

.guide-step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.guide-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  margin-bottom: 8px;
}

.guide-card {
  padding: 16px 18px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-muted);
}

.guide-card h3 {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 8px;
  color: var(--text-primary);
  font-size: 14px;
}

.guide-card h3 .el-icon {
  color: var(--primary-color);
}

.guide-card p,
.guide-card ul {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.guide-card ul {
  margin-top: 8px;
  padding-left: 18px;
}

.example-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 14px;
  margin: 14px 0 16px;
}

.example-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--surface-color);
}

.example-card-head {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.example-card-head strong {
  color: var(--text-primary);
  font-size: 13px;
}

.example-desc {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--primary-soft);
  color: var(--primary-dark);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.6;
}

.example-result {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.7;
}

.guide-note {
  margin: 0;
}

.guide-table {
  margin: 10px 0 18px;
}

.guide-list {
  margin: 10px 0 16px;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.9;
}

.guide-code {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface-strong);
  color: var(--text-primary);
  font-family: Consolas, "Courier New", monospace;
  font-size: 11px;
}

.faq-answer {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.8;
}
</style>
