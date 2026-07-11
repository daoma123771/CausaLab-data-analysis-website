<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue"
import * as echarts from "echarts/core"
import { BarChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

type MetricType = "proportion" | "continuous"
type Alternative = "two-sided" | "greater" | "less"
interface HistogramBin { lower: number; upper: number; count: number }
interface AnalysisResult {
  metric_type: MetricType; method: string; control_size: number; treatment_size: number
  control_value: number; treatment_value: number; absolute_effect: number
  relative_effect_percent: number | null; statistic: number; p_value: number; alpha: number
  confidence_level: number; ci_lower: number; ci_upper: number; significant: boolean
  direction_matches: boolean; decision: string; conclusion: string
  bootstrap_iterations: number; bootstrap_histogram: HistogramBin[]; warnings: string[]
}

const metricType = ref<MetricType>("proportion")
const alternative = ref<Alternative>("greater")
const alpha = ref(0.05)
const bootstrapIterations = ref(3000)
const controlTotal = ref(5000)
const controlSuccess = ref(500)
const treatmentTotal = ref(5000)
const treatmentSuccess = ref(650)
const controlText = ref("9, 10, 11, 10, 9, 11, 10, 10")
const treatmentText = ref("13, 14, 15, 14, 13, 15, 14, 14")
const result = ref<AnalysisResult | null>(null)
const loading = ref(false)
const errorMessage = ref("")
const chartElement = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const parseValues = (text: string) => text.split(/[\s,，;；]+/).filter(Boolean).map(Number)
const formatValue = (value: number, percent = false) => percent
  ? `${(value * 100).toFixed(2)}%`
  : Math.abs(value) >= 100 ? value.toFixed(1) : value.toFixed(3)
const metricUnitPercent = computed(() => result.value?.metric_type === "proportion")
const effectLabel = computed(() => metricUnitPercent.value ? "绝对转化率差" : "均值差")

function selectMetric(type: MetricType) {
  metricType.value = type
  result.value = null
  errorMessage.value = ""
}

async function runAnalysis() {
  errorMessage.value = ""
  loading.value = true
  try {
    let body: Record<string, unknown>
    if (metricType.value === "proportion") {
      body = {
        control_total: controlTotal.value, control_success: controlSuccess.value,
        treatment_total: treatmentTotal.value, treatment_success: treatmentSuccess.value,
        alpha: alpha.value, alternative: alternative.value,
        bootstrap_iterations: bootstrapIterations.value,
      }
    } else {
      const controlValues = parseValues(controlText.value)
      const treatmentValues = parseValues(treatmentText.value)
      if (controlValues.some(value => !Number.isFinite(value)) || treatmentValues.some(value => !Number.isFinite(value))) {
        throw new Error("连续指标中包含无法识别的数值")
      }
      body = {
        control_values: controlValues, treatment_values: treatmentValues,
        alpha: alpha.value, alternative: alternative.value,
        bootstrap_iterations: bootstrapIterations.value,
      }
    }
    const response = await fetch(`/api/analysis/${metricType.value}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail?.[0]?.msg || data.detail || "分析请求失败")
    result.value = data
    await nextTick()
    renderChart()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "分析失败"
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartElement.value || !result.value) return
  chart?.dispose()
  chart = echarts.init(chartElement.value)
  const bins = result.value.bootstrap_histogram
  chart.setOption({
    tooltip: { trigger: "axis", formatter: (items: any) => {
      const item = items[0]
      const bin = bins[item.dataIndex]
      return `效应区间：${bin.lower.toFixed(4)} ～ ${bin.upper.toFixed(4)}<br/>重抽样次数：${bin.count}`
    } },
    grid: { left: 54, right: 18, top: 24, bottom: 48 },
    xAxis: { type: "category", data: bins.map(bin => ((bin.lower + bin.upper) / 2).toFixed(3)), name: "效应差", nameLocation: "middle", nameGap: 31, axisLabel: { interval: 3, color: "#718078" } },
    yAxis: { type: "value", name: "频数", splitLine: { lineStyle: { color: "#edf1ed" } } },
    series: [{ type: "bar", data: bins.map(bin => bin.count), itemStyle: { color: "#5d9275", borderRadius: [3, 3, 0, 0] }, barMaxWidth: 26 }],
  })
}

onBeforeUnmount(() => chart?.dispose())
</script>

<template>
  <section class="analysis-view">
    <div class="planning-heading">
      <div><p class="eyebrow">EFFECT ESTIMATION</p><h1>A/B 效应评估与稳健性验证</h1><p class="lead">同时报告显著性检验、效应大小与 Bootstrap 置信区间，避免只看 p 值做决策。</p></div>
      <span class="method-badge">检验 + 估计 + 决策解释</span>
    </div>
    <div class="analysis-layout">
      <form class="parameter-panel analysis-form" @submit.prevent="runAnalysis">
        <div class="panel-title"><div><small>STEP 01</small><h2>录入实验结果</h2></div><span>内置演示数据</span></div>
        <div class="metric-tabs">
          <button type="button" :class="{ active: metricType === 'proportion' }" @click="selectMetric('proportion')">比例指标</button>
          <button type="button" :class="{ active: metricType === 'continuous' }" @click="selectMetric('continuous')">连续指标</button>
        </div>
        <div v-if="metricType === 'proportion'" class="group-inputs">
          <div class="group-box"><strong>对照组 A</strong><label><span>总样本量</span><input v-model.number="controlTotal" type="number" min="2" required /></label><label><span>成功事件数</span><input v-model.number="controlSuccess" type="number" min="0" required /></label></div>
          <div class="group-box treatment"><strong>实验组 B</strong><label><span>总样本量</span><input v-model.number="treatmentTotal" type="number" min="2" required /></label><label><span>成功事件数</span><input v-model.number="treatmentSuccess" type="number" min="0" required /></label></div>
        </div>
        <div v-else class="raw-inputs">
          <label><span>对照组 A 原始观测值</span><textarea v-model="controlText" rows="4" required></textarea><small>使用逗号、空格或换行分隔</small></label>
          <label><span>实验组 B 原始观测值</span><textarea v-model="treatmentText" rows="4" required></textarea></label>
        </div>
        <div class="field-grid common-fields">
          <label><span>备择假设</span><select v-model="alternative"><option value="greater">实验组更高</option><option value="less">实验组更低</option><option value="two-sided">两组不相等</option></select></label>
          <label><span>显著性水平 α</span><select v-model.number="alpha"><option :value="0.1">0.10</option><option :value="0.05">0.05</option><option :value="0.01">0.01</option></select></label>
          <label class="span-two"><span>Bootstrap 重抽样次数</span><select v-model.number="bootstrapIterations"><option :value="1000">1,000（快速）</option><option :value="3000">3,000（推荐）</option><option :value="10000">10,000（精细）</option></select></label>
        </div>
        <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
        <button class="primary-action" :disabled="loading">{{ loading ? "正在进行重抽样…" : "运行效应评估" }}</button>
      </form>
      <div class="result-panel analysis-result">
        <div v-if="!result" class="result-empty"><div><strong>等待分析</strong><p>使用左侧示例数据即可生成完整统计结论</p></div></div>
        <div v-else class="result-content">
          <div class="decision-banner" :class="{ significant: result.significant && result.direction_matches }"><div><small>统计决策</small><strong>{{ result.decision }}</strong><p>{{ result.conclusion }}</p></div><span>{{ result.significant ? "显著" : "未显著" }}</span></div>
          <div class="analysis-metrics">
            <article><small>对照组</small><strong>{{ formatValue(result.control_value, metricUnitPercent) }}</strong><span>n = {{ result.control_size }}</span></article>
            <article><small>实验组</small><strong>{{ formatValue(result.treatment_value, metricUnitPercent) }}</strong><span>n = {{ result.treatment_size }}</span></article>
            <article class="effect"><small>{{ effectLabel }}</small><strong>{{ result.absolute_effect > 0 ? '+' : '' }}{{ formatValue(result.absolute_effect, metricUnitPercent) }}</strong><span v-if="result.relative_effect_percent !== null">相对变化 {{ result.relative_effect_percent.toFixed(2) }}%</span></article>
            <article><small>p 值</small><strong>{{ result.p_value < 0.0001 ? '< 0.0001' : result.p_value.toFixed(4) }}</strong><span>α = {{ result.alpha }}</span></article>
          </div>
          <div class="interval-card"><div><small>{{ (result.confidence_level * 100).toFixed(0) }}% Bootstrap 置信区间</small><strong>[{{ formatValue(result.ci_lower, metricUnitPercent) }}, {{ formatValue(result.ci_upper, metricUnitPercent) }}]</strong></div><span>{{ result.method }}</span></div>
          <div class="chart-card"><div class="chart-title"><h3>Bootstrap 效应差抽样分布</h3><span>{{ result.bootstrap_iterations.toLocaleString() }} 次重抽样</span></div><div ref="chartElement" class="bootstrap-chart"></div></div>
          <div v-if="result.warnings.length" class="warning-card"><strong>解释提示</strong><p v-for="warning in result.warnings" :key="warning">{{ warning }}</p></div>
        </div>
      </div>
    </div>
  </section>
</template>
