<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"
import { BarChart, ScatterChart } from "echarts/charts"
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components"
import { init, use, type ECharts, type EChartsCoreOption } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"

use([BarChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface VariableCandidate {
  name: string
  role: string
  data_type: string
  semantic_type: string
  non_null_count: number
  missing_percent: number
  unique_count: number
  reason: string
}

interface TaskRecommendation {
  key: string
  title: string
  method: string
  question: string
  suitability: "ready" | "needs_input" | "limited" | "not_available"
  confidence: number
  required_fields: string[]
  candidate_fields: Record<string, string[]>
  sample_assessment: string
  sample_gap: number | null
  explanation: string
}

interface WorkflowResult {
  file_name: string
  file_type: string
  row_count: number
  column_count: number
  quality_score: number
  quality_level: string
  dataset_summary: string
  variables: VariableCandidate[]
  recommended_tasks: TaskRecommendation[]
  next_steps: string[]
  preview: Record<string, unknown>[]
}

interface AnalysisMetric { label: string; value: string; note: string | null }
interface AnalysisResult {
  task_key: string
  title: string
  method: string
  sample_size: number
  summary: string
  metrics: AnalysisMetric[]
  table: Record<string, unknown>[]
  interpretation: string[]
  warnings: string[]
  chart_data: Record<string, unknown>[]
}

const selectedFile = ref<File | null>(null)
const result = ref<WorkflowResult | null>(null)
const loading = ref(false)
const analyzing = ref(false)
const dragging = ref(false)
const errorMessage = ref("")
const analysisError = ref("")
const fileInput = ref<HTMLInputElement | null>(null)
const selectedTask = ref<TaskRecommendation | null>(null)
const analysisResult = ref<AnalysisResult | null>(null)
const targetField = ref("")
const xField = ref("")
const yField = ref("")
const groupField = ref("")
const outcomeField = ref("")
const featureFields = ref<string[]>([])
const chartElement = ref<HTMLDivElement | null>(null)
const chartNotice = ref("")
let analysisChart: ECharts | null = null

const previewColumns = computed(() => result.value ? Object.keys(result.value.preview[0] || {}) : [])
const readyTasks = computed(() => result.value?.recommended_tasks.filter(task => task.suitability === "ready") || [])
const candidateTargets = computed(() => result.value?.variables.filter(item => item.role === "target").slice(0, 6) || [])
const candidateGroups = computed(() => result.value?.variables.filter(item => item.role === "group").slice(0, 6) || [])
const numericVariables = computed(() => result.value?.variables.filter(item => item.semantic_type === "numeric" && item.role !== "identifier") || [])
const groupVariables = computed(() => result.value?.variables.filter(item => ["group", "feature"].includes(item.role) && ["categorical", "binary"].includes(item.semantic_type)) || [])
const binaryVariables = computed(() => result.value?.variables.filter(item => item.semantic_type === "binary") || [])
const analysisColumns = computed(() => analysisResult.value ? Object.keys(analysisResult.value.table[0] || {}) : [])
const chartTitle = computed(() => {
  if (!analysisResult.value) return "分析图表"
  const titles: Record<string, string> = {
    linear_regression: "实际值与模型预测值",
    correlation: "两个变量的散点关系",
    descriptive: "数值字段均值对比",
    two_group_mean: "两组均值对比",
    multi_group_mean: "多组均值对比",
    proportion_test: "两组比例对比",
  }
  return titles[analysisResult.value.task_key] || "分析图表"
})

const roleText: Record<string, string> = {
  target: "目标候选",
  feature: "解释变量",
  group: "分组变量",
  identifier: "样本标识",
  time: "时间字段",
  text: "文本字段",
}

const semanticText: Record<string, string> = {
  numeric: "数值",
  categorical: "类别",
  binary: "二元",
  datetime: "时间",
  text: "文本",
  identifier: "标识",
}

const suitabilityText: Record<string, string> = {
  ready: "可直接开展",
  needs_input: "需确认字段",
  limited: "谨慎使用",
  not_available: "暂不适合",
}

function chooseFile() {
  fileInput.value?.click()
}

function handleInput(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) acceptFile(file)
}

function handleDrop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file) acceptFile(file)
}

function acceptFile(file: File) {
  errorMessage.value = ""
  const extension = file.name.split(".").pop()?.toLowerCase()
  if (!extension || !["csv", "xlsx"].includes(extension)) {
    errorMessage.value = "请选择 CSV 或 XLSX 表格文件"
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    errorMessage.value = "文件不能超过 10 MB"
    return
  }
  selectedFile.value = file
  selectedTask.value = null
  analysisResult.value = null
  inspectWorkflow()
}

async function inspectWorkflow() {
  if (!selectedFile.value) return
  loading.value = true
  errorMessage.value = ""
  result.value = null
  try {
    const form = new FormData()
    form.append("file", selectedFile.value)
    const response = await fetch("/api/workflow/inspect", { method: "POST", body: form })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || "分析向导生成失败")
    result.value = data
    const firstReady = data.recommended_tasks.find((task: TaskRecommendation) => task.suitability === "ready") || data.recommended_tasks[0]
    if (firstReady) selectTask(firstReady)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "分析向导生成失败"
  } finally {
    loading.value = false
  }
}

function firstCandidate(task: TaskRecommendation, key: string, fallback: VariableCandidate[]) {
  return task.candidate_fields[key]?.[0] || fallback[0]?.name || ""
}

function selectTask(task: TaskRecommendation) {
  selectedTask.value = task
  analysisResult.value = null
  analysisError.value = ""
  disposeAnalysisChart()
  targetField.value = firstCandidate(task, "target", candidateTargets.value.length ? candidateTargets.value : numericVariables.value)
  groupField.value = firstCandidate(task, "group", groupVariables.value)
  outcomeField.value = firstCandidate(task, "outcome", binaryVariables.value)
  const numeric = numericVariables.value.map(item => item.name)
  xField.value = task.candidate_fields.numeric?.[0] || numeric[0] || ""
  yField.value = task.candidate_fields.numeric?.find(item => item !== xField.value) || numeric.find(item => item !== xField.value) || ""
  if (task.key === "two_group_mean" || task.key === "multi_group_mean") {
    targetField.value = firstCandidate(task, "metric", numericVariables.value)
  }
  const suggestedFeatures = task.candidate_fields.features || numeric.filter(item => item !== targetField.value).slice(0, 4)
  featureFields.value = suggestedFeatures.filter(item => item !== targetField.value).slice(0, 6)
}

function toggleFeature(field: string) {
  if (field === targetField.value) return
  featureFields.value = featureFields.value.includes(field)
    ? featureFields.value.filter(item => item !== field)
    : [...featureFields.value, field]
}

async function runAnalysis() {
  if (!selectedFile.value || !selectedTask.value) return
  analyzing.value = true
  analysisError.value = ""
  chartNotice.value = ""
  disposeAnalysisChart()
  analysisResult.value = null
  try {
    const form = new FormData()
    form.append("file", selectedFile.value)
    form.append("task_key", selectedTask.value.key)
    if (targetField.value) form.append("target", targetField.value)
    if (xField.value) form.append("x_field", xField.value)
    if (yField.value) form.append("y_field", yField.value)
    if (groupField.value) form.append("group_field", groupField.value)
    if (outcomeField.value) form.append("outcome_field", outcomeField.value)
    form.append("feature_fields", JSON.stringify(featureFields.value))
    const response = await fetch("/api/workflow/analyze", { method: "POST", body: form })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || "统计分析失败")
    analysisResult.value = data
    localStorage.setItem("causalab-latest-workflow-analysis", JSON.stringify({
      fileName: selectedFile.value.name,
      createdAt: new Date().toLocaleString("zh-CN"),
      result: data,
    }))
    await nextTick()
    renderAnalysisChart()
  } catch (error) {
    analysisError.value = error instanceof Error ? error.message : "统计分析失败"
  } finally {
    analyzing.value = false
  }
}

function numericValue(value: unknown) {
  const parsed = typeof value === "number" ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function firstExistingKey(row: Record<string, unknown>, candidates: string[]) {
  const keys = Object.keys(row)
  return candidates.find(key => key in row) || keys.find(key => candidates.some(candidate => key.toLowerCase().includes(candidate.toLowerCase())))
}

function buildChartOption(): EChartsCoreOption | null {
  const data = analysisResult.value
  if (!data) return null
  const green = "#1d6a47"
  const gold = "#d49b58"
  if (data.task_key === "linear_regression") {
    return {
      tooltip: { trigger: "item" },
      grid: { left: 52, right: 20, top: 32, bottom: 45 },
      xAxis: { type: "value", name: "实际值", nameGap: 25 },
      yAxis: { type: "value", name: "预测值" },
      series: [{
        type: "scatter",
        symbolSize: 7,
        itemStyle: { color: green, opacity: 0.72 },
        data: data.chart_data.map(item => [numericValue(item.actual), numericValue(item.predicted)]),
      }],
    }
  }
  if (data.task_key === "correlation") {
    const first = data.chart_data[0] || {}
    const keys = Object.keys(first)
    return {
      tooltip: { trigger: "item" },
      grid: { left: 52, right: 20, top: 32, bottom: 45 },
      xAxis: { type: "value", name: keys[0] || "X", nameGap: 25 },
      yAxis: { type: "value", name: keys[1] || "Y" },
      series: [{
        type: "scatter",
        symbolSize: 8,
        itemStyle: { color: green, opacity: 0.75 },
        data: data.chart_data.map(item => [numericValue(item[keys[0]]), numericValue(item[keys[1]])]),
      }],
    }
  }
  const firstRow = data.table[0]
  if (!firstRow) return null
  const labelKey = firstExistingKey(firstRow, ["字段", "分组", "组别", "变量", "field", "group", "category"])
  const valueKey = firstExistingKey(firstRow, ["均值", "平均值", "比例", "value", "mean", "rate"])
  if (!labelKey || !valueKey) return null
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 52, right: 20, top: 32, bottom: 52 },
    xAxis: { type: "category", axisLabel: { rotate: data.table.length > 5 ? 28 : 0 }, data: data.table.map(row => String(row[labelKey] ?? "")) },
    yAxis: { type: "value" },
    series: [{
      type: "bar",
      itemStyle: { color: data.task_key === "proportion_test" ? gold : green, borderRadius: [6, 6, 0, 0] },
      data: data.table.map(row => numericValue(row[valueKey])),
    }],
  }
}

function renderAnalysisChart() {
  if (!chartElement.value || !analysisResult.value) return
  const option = buildChartOption()
  if (!option) {
    chartNotice.value = "当前统计结果以表格和文字解释为主，暂未生成可视化图表。"
    return
  }
  chartNotice.value = ""
  analysisChart = init(chartElement.value)
  analysisChart.setOption(option, true)
  requestAnimationFrame(() => analysisChart?.resize())
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "—"
  return String(value)
}

function disposeAnalysisChart() {
  analysisChart?.dispose()
  analysisChart = null
}

function resizeChart() {
  analysisChart?.resize()
}

onMounted(() => window.addEventListener("resize", resizeChart))
onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart)
  disposeAnalysisChart()
})
</script>

<template>
  <section class="workflow-view">
    <div class="planning-heading">
      <div>
        <p class="eyebrow">ANALYSIS WIZARD</p>
        <h1>上传一份表格，生成连续统计分析路线</h1>
        <p class="lead">
          系统会先读取 CSV/Excel 数据，识别字段类型和数据质量，再推荐可开展的统计检验、样本量判断和建模方向。
        </p>
      </div>
      <span class="method-badge">CSV / XLSX · 向导式分析</span>
    </div>

    <div class="wizard-steps">
      <article class="active"><strong>01</strong><span>导入数据</span></article>
      <article :class="{ active: result }"><strong>02</strong><span>数据画像</span></article>
      <article :class="{ active: readyTasks.length }"><strong>03</strong><span>方法推荐</span></article>
      <article :class="{ active: result }"><strong>04</strong><span>样本量判断</span></article>
      <article :class="{ active: selectedTask }"><strong>05</strong><span>检验与建模</span></article>
      <article :class="{ active: analysisResult }"><strong>06</strong><span>报告归档</span></article>
    </div>

    <div v-if="!result" class="upload-stage workflow-upload">
      <div class="upload-card" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="handleDrop">
        <div class="upload-icon">↑</div>
        <h2>{{ loading ? "正在读取数据并生成分析路线…" : "上传 CSV / Excel 表格" }}</h2>
        <p>适合上传房价、工资、汽车油耗、问卷、实验记录等二维表格数据</p>
        <input ref="fileInput" type="file" accept=".csv,.xlsx" hidden @change="handleInput" />
        <button type="button" :disabled="loading" @click="chooseFile">{{ loading ? "分析中" : "选择数据文件" }}</button>
        <small>最大 10 MB · 一行代表一个样本，一列代表一个变量</small>
      </div>
      <p v-if="errorMessage" class="form-error upload-error">{{ errorMessage }}</p>

      <div class="quality-capabilities">
        <article><strong>01</strong><span>自动画像</span><p>识别字段类型、目标变量候选、分组变量和数据质量问题</p></article>
        <article><strong>02</strong><span>方法推荐</span><p>根据数据结构推荐描述统计、相关分析、t 检验、ANOVA 或回归</p></article>
        <article><strong>03</strong><span>样本量判断</span><p>判断当前数据是否适合继续分析，并提示可能的数据缺口</p></article>
      </div>
    </div>

    <div v-else class="workflow-results">
      <div class="quality-toolbar">
        <div>
          <small>当前数据集</small>
          <strong>{{ result.file_name }}</strong>
          <span>{{ result.row_count.toLocaleString() }} 行 × {{ result.column_count }} 列 · 质量评分 {{ result.quality_score }}/100</span>
        </div>
        <button type="button" @click="chooseFile">更换数据</button>
        <input ref="fileInput" type="file" accept=".csv,.xlsx" hidden @change="handleInput" />
      </div>

      <section class="workflow-summary">
        <article class="dataset-brief">
          <span>DATASET PROFILE</span>
          <h2>{{ result.dataset_summary }}</h2>
          <p>系统已完成字段识别、质量评分和第一轮统计分析路线推荐。下一步需要你确认目标字段和分析问题是否符合业务含义。</p>
        </article>
        <article>
          <small>优先可开展</small>
          <strong>{{ readyTasks.length }}</strong>
          <span>项分析任务</span>
        </article>
        <article>
          <small>目标候选</small>
          <strong>{{ candidateTargets.length }}</strong>
          <span>个连续目标</span>
        </article>
        <article>
          <small>分组候选</small>
          <strong>{{ candidateGroups.length }}</strong>
          <span>个类别字段</span>
        </article>
      </section>

      <div class="workflow-grid-main">
        <section class="quality-section">
          <div class="quality-title">
            <div><small>RECOMMENDED ANALYSIS</small><h2>推荐统计分析路线</h2></div>
            <span>{{ result.recommended_tasks.length }} 项</span>
          </div>
          <div class="task-list">
            <article v-for="task in result.recommended_tasks" :key="task.key" :class="task.suitability">
              <div class="task-head">
                <div>
                  <small>{{ task.method }}</small>
                  <h3>{{ task.title }}</h3>
                </div>
                <span>{{ suitabilityText[task.suitability] }} · {{ task.confidence }}%</span>
              </div>
              <p>{{ task.question }}</p>
              <div class="task-meta">
                <b>样本判断</b>
                <span>{{ task.sample_assessment }}</span>
              </div>
              <div class="task-fields">
                <span v-for="field in task.required_fields" :key="field">{{ field }}</span>
              </div>
              <p class="task-explain">{{ task.explanation }}</p>
              <button type="button" class="task-run" :class="{ active: selectedTask?.key === task.key }" @click="selectTask(task)">
                {{ selectedTask?.key === task.key ? "当前选择" : "选择此路线" }}
              </button>
            </article>
          </div>
        </section>

        <aside class="workflow-side">
          <section class="quality-section">
            <div class="quality-title"><div><small>NEXT STEPS</small><h2>下一步建议</h2></div></div>
            <p v-for="step in result.next_steps" :key="step" class="diagnosis recommendation">{{ step }}</p>
          </section>

          <section class="quality-section">
            <div class="quality-title"><div><small>VARIABLES</small><h2>关键变量候选</h2></div></div>
            <div class="variable-list">
              <article v-for="variable in result.variables.slice(0, 10)" :key="variable.name">
                <div>
                  <strong>{{ variable.name }}</strong>
                  <span>{{ roleText[variable.role] || variable.role }} · {{ semanticText[variable.semantic_type] || variable.semantic_type }}</span>
                </div>
                <small>缺失 {{ variable.missing_percent }}% · {{ variable.unique_count }} 个唯一值</small>
              </article>
            </div>
          </section>
        </aside>
      </div>

      <section v-if="selectedTask" class="analysis-workbench">
        <div class="quality-title">
          <div>
            <small>RUN ANALYSIS</small>
            <h2>检验与建模工作台</h2>
          </div>
          <span>{{ selectedTask.method }}</span>
        </div>

        <div class="analysis-config">
          <article class="config-card">
            <small>当前分析任务</small>
            <h3>{{ selectedTask.title }}</h3>
            <p>{{ selectedTask.question }}</p>
          </article>

          <article v-if="['two_group_mean', 'multi_group_mean', 'proportion_test'].includes(selectedTask.key)" class="config-card">
            <label>
              <span>分组字段</span>
              <select v-model="groupField">
                <option v-for="variable in groupVariables" :key="variable.name" :value="variable.name">{{ variable.name }}</option>
              </select>
            </label>
          </article>

          <article v-if="['two_group_mean', 'multi_group_mean', 'linear_regression'].includes(selectedTask.key)" class="config-card">
            <label>
              <span>{{ selectedTask.key === 'linear_regression' ? '目标变量' : '数值指标' }}</span>
              <select v-model="targetField">
                <option v-for="variable in numericVariables" :key="variable.name" :value="variable.name">{{ variable.name }}</option>
              </select>
            </label>
          </article>

          <article v-if="selectedTask.key === 'correlation'" class="config-card two-selects">
            <label>
              <span>变量 X</span>
              <select v-model="xField">
                <option v-for="variable in numericVariables" :key="variable.name" :value="variable.name">{{ variable.name }}</option>
              </select>
            </label>
            <label>
              <span>变量 Y</span>
              <select v-model="yField">
                <option v-for="variable in numericVariables" :key="variable.name" :value="variable.name">{{ variable.name }}</option>
              </select>
            </label>
          </article>

          <article v-if="selectedTask.key === 'proportion_test'" class="config-card">
            <label>
              <span>二元结果字段</span>
              <select v-model="outcomeField">
                <option v-for="variable in binaryVariables" :key="variable.name" :value="variable.name">{{ variable.name }}</option>
              </select>
            </label>
          </article>

          <article v-if="['linear_regression', 'descriptive'].includes(selectedTask.key)" class="config-card feature-config">
            <span>{{ selectedTask.key === 'linear_regression' ? '解释变量' : '分析字段' }}</span>
            <div class="feature-pills">
              <button
                v-for="variable in numericVariables"
                :key="variable.name"
                type="button"
                :disabled="selectedTask.key === 'linear_regression' && variable.name === targetField"
                :class="{ active: featureFields.includes(variable.name) }"
                @click="toggleFeature(variable.name)"
              >
                {{ variable.name }}
              </button>
            </div>
          </article>
        </div>

        <div class="analysis-action-row">
          <button type="button" class="primary-action inline" :disabled="analyzing" @click="runAnalysis">
            {{ analyzing ? "正在计算…" : "运行统计分析 / 建模" }}
          </button>
          <p v-if="analysisError" class="form-error">{{ analysisError }}</p>
        </div>

        <div v-if="analysisResult" class="analysis-output">
          <article class="analysis-summary-card">
            <span>{{ analysisResult.method }}</span>
            <h3>{{ analysisResult.title }}</h3>
            <p>{{ analysisResult.summary }}</p>
          </article>

          <div class="analysis-result-metrics">
            <article v-for="metric in analysisResult.metrics" :key="metric.label">
              <small>{{ metric.label }}</small>
              <strong>{{ metric.value }}</strong>
              <span v-if="metric.note">{{ metric.note }}</span>
            </article>
          </div>

          <section class="quality-section analysis-chart-section">
            <div class="quality-title">
              <div><small>VISUAL RESULT</small><h2>{{ chartTitle }}</h2></div>
              <span>{{ analysisResult.method }}</span>
            </div>
            <div ref="chartElement" class="workflow-analysis-chart"></div>
            <p v-if="chartNotice" class="chart-empty-note">{{ chartNotice }}</p>
          </section>

          <section v-if="analysisResult.table.length" class="quality-section">
            <div class="quality-title">
              <div><small>RESULT TABLE</small><h2>统计结果表</h2></div>
              <span>{{ analysisResult.sample_size }} 个有效样本</span>
            </div>
            <div class="preview-table-wrap">
              <table class="preview-table">
                <thead><tr><th v-for="column in analysisColumns" :key="column">{{ column }}</th></tr></thead>
                <tbody>
                  <tr v-for="(row, index) in analysisResult.table" :key="index">
                    <td v-for="column in analysisColumns" :key="column">{{ formatCell(row[column]) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="quality-section">
            <div class="quality-title"><div><small>INTERPRETATION</small><h2>结果解释</h2></div></div>
            <p v-for="item in analysisResult.interpretation" :key="item" class="diagnosis recommendation">{{ item }}</p>
            <p v-for="item in analysisResult.warnings" :key="item" class="diagnosis warning">{{ item }}</p>
          </section>
        </div>
      </section>

      <section class="quality-section preview-section">
        <div class="quality-title">
          <div><small>DATA PREVIEW</small><h2>数据预览</h2></div>
          <span>前 {{ result.preview.length }} 行</span>
        </div>
        <div class="preview-table-wrap">
          <table class="preview-table">
            <thead><tr><th v-for="column in previewColumns" :key="column">{{ column }}</th></tr></thead>
            <tbody>
              <tr v-for="(row, index) in result.preview" :key="index">
                <td v-for="column in previewColumns" :key="column">{{ formatCell(row[column]) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </section>
</template>
