<script setup lang="ts">
import { LineChart } from "echarts/charts"
import { GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components"
import { init, use, type ECharts } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"

use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

type MetricType = "proportion" | "continuous"

interface CurvePoint {
  total_sample_size: number
  power: number
}

interface PlanResult {
  metric_type: MetricType
  control_sample_size: number
  treatment_sample_size: number
  total_sample_size: number
  effect_size: number
  minimum_detectable_effect: number
  alpha: number
  target_power: number
  estimated_days: number | null
  curve: CurvePoint[]
  explanation: string
  warnings: string[]
}

const metricType = ref<MetricType>("proportion")
const baselineRate = ref(10)
const targetRate = ref(12)
const meanDifference = ref(5)
const standardDeviation = ref(10)
const alpha = ref(0.05)
const targetPower = ref(0.8)
const allocationRatio = ref(1)
const dailyTraffic = ref(500)
const loading = ref(false)
const errorMessage = ref("")
const result = ref<PlanResult | null>(null)
const chartElement = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null

const metricLabel = computed(() => metricType.value === "proportion" ? "比例指标" : "连续指标")

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value)
}

function buildPayload() {
  const common = {
    alpha: alpha.value,
    power: targetPower.value,
    allocation_ratio: allocationRatio.value,
    daily_traffic: dailyTraffic.value || null,
  }
  return metricType.value === "proportion"
    ? {
        ...common,
        baseline_rate: baselineRate.value / 100,
        target_rate: targetRate.value / 100,
      }
    : {
        ...common,
        mean_difference: meanDifference.value,
        standard_deviation: standardDeviation.value,
      }
}

async function calculatePlan() {
  loading.value = true
  errorMessage.value = ""
  try {
    const response = await fetch(`/api/planning/${metricType.value}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    })
    const data = await response.json()
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((item: { msg?: string }) => item.msg).join("；")
        : data.detail
      throw new Error(detail || "计算失败，请检查输入参数。")
    }
    result.value = data as PlanResult
    await nextTick()
    renderChart()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "计算失败，请稍后重试。"
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartElement.value || !result.value) return
  chart ??= init(chartElement.value)
  chart.setOption({
    animationDuration: 500,
    grid: { left: 54, right: 24, top: 34, bottom: 42 },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const item = (params as Array<{ data: [number, number] }>)[0]
        return `总样本量：${formatNumber(item.data[0])}<br/>统计功效：${(item.data[1] * 100).toFixed(1)}%`
      },
    },
    xAxis: {
      type: "value",
      name: "总样本量",
      nameLocation: "middle",
      nameGap: 28,
      axisLine: { lineStyle: { color: "#98a79f" } },
      splitLine: { lineStyle: { color: "#e7ece8" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 1,
      axisLabel: { formatter: (value: number) => `${Math.round(value * 100)}%` },
      splitLine: { lineStyle: { color: "#e7ece8" } },
    },
    series: [
      {
        type: "line",
        smooth: true,
        symbolSize: 7,
        data: result.value.curve.map((point) => [point.total_sample_size, point.power]),
        lineStyle: { width: 3, color: "#277653" },
        itemStyle: { color: "#277653" },
        areaStyle: { color: "rgba(104, 170, 130, 0.16)" },
        markLine: {
          symbol: "none",
          label: { formatter: `目标功效 ${(result.value.target_power * 100).toFixed(0)}%` },
          lineStyle: { color: "#c48a4a", type: "dashed" },
          data: [{ yAxis: result.value.target_power }],
        },
      },
    ],
  })
}

function switchMetric(type: MetricType) {
  metricType.value = type
  result.value = null
  errorMessage.value = ""
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  window.addEventListener("resize", handleResize)
  calculatePlan()
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
  chart?.dispose()
})
</script>

<template>
  <section class="planning-view">
    <div class="planning-heading">
      <div>
        <p class="eyebrow">EXPERIMENT PLANNING</p>
        <h1>实验样本量与功效规划</h1>
        <p class="lead">在实验开始前明确需要多少样本，避免“做完才发现检验能力不足”。</p>
      </div>
      <span class="method-badge">独立两样本 · 双侧检验</span>
    </div>

    <div class="planning-layout">
      <form class="parameter-panel" @submit.prevent="calculatePlan">
        <div class="panel-title">
          <div>
            <small>输入参数</small>
            <h2>{{ metricLabel }}</h2>
          </div>
          <span>所有参数均可调整</span>
        </div>

        <div class="metric-tabs" role="tablist" aria-label="指标类型">
          <button type="button" :class="{ active: metricType === 'proportion' }" @click="switchMetric('proportion')">比例指标</button>
          <button type="button" :class="{ active: metricType === 'continuous' }" @click="switchMetric('continuous')">连续指标</button>
        </div>

        <div v-if="metricType === 'proportion'" class="field-grid">
          <label>
            <span>基准转化率</span>
            <div class="input-with-unit"><input v-model.number="baselineRate" type="number" min="0.1" max="99.9" step="0.1" required /><b>%</b></div>
            <small>对照组当前水平</small>
          </label>
          <label>
            <span>目标转化率</span>
            <div class="input-with-unit"><input v-model.number="targetRate" type="number" min="0.1" max="99.9" step="0.1" required /><b>%</b></div>
            <small>希望能够检出的水平</small>
          </label>
        </div>

        <div v-else class="field-grid">
          <label>
            <span>最小均值差</span>
            <input v-model.number="meanDifference" type="number" min="0.1" step="0.1" required />
            <small>具有实际意义的最小差异</small>
          </label>
          <label>
            <span>指标标准差</span>
            <input v-model.number="standardDeviation" type="number" min="0.1" step="0.1" required />
            <small>可根据历史数据估计</small>
          </label>
        </div>

        <div class="field-grid common-fields">
          <label>
            <span>显著性水平 α</span>
            <select v-model.number="alpha">
              <option :value="0.1">0.10</option>
              <option :value="0.05">0.05</option>
              <option :value="0.01">0.01</option>
            </select>
          </label>
          <label>
            <span>目标统计功效</span>
            <select v-model.number="targetPower">
              <option :value="0.8">80%</option>
              <option :value="0.85">85%</option>
              <option :value="0.9">90%</option>
              <option :value="0.95">95%</option>
            </select>
          </label>
          <label>
            <span>实验组/对照组比例</span>
            <input v-model.number="allocationRatio" type="number" min="0.1" max="10" step="0.1" required />
          </label>
          <label>
            <span>每日预计流量</span>
            <input v-model.number="dailyTraffic" type="number" min="2" step="1" required />
          </label>
        </div>

        <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
        <button class="primary-action" type="submit" :disabled="loading">
          {{ loading ? "正在计算…" : "计算实验方案" }}
        </button>
      </form>

      <div class="result-panel">
        <div v-if="result" class="result-content">
          <div class="result-summary">
            <div class="result-main">
              <small>建议总样本量</small>
              <strong>{{ formatNumber(result.total_sample_size) }}</strong>
              <span v-if="result.estimated_days">按当前流量预计约 {{ result.estimated_days }} 天</span>
            </div>
            <div class="result-split">
              <div><small>对照组</small><strong>{{ formatNumber(result.control_sample_size) }}</strong></div>
              <div><small>实验组</small><strong>{{ formatNumber(result.treatment_sample_size) }}</strong></div>
              <div><small>标准化效应</small><strong>{{ result.effect_size.toFixed(3) }}</strong></div>
            </div>
          </div>

          <div class="chart-card">
            <div class="chart-title"><h3>样本量—统计功效曲线</h3><span>功效越高，发现真实效应的概率越高</span></div>
            <div ref="chartElement" class="power-chart" aria-label="样本量与统计功效曲线"></div>
          </div>

          <div class="explanation-card">
            <span>结果解释</span>
            <p>{{ result.explanation }}</p>
          </div>

          <div v-if="result.warnings.length" class="warning-card">
            <strong>规划提示</strong>
            <p v-for="warning in result.warnings" :key="warning">{{ warning }}</p>
          </div>
        </div>
        <div v-else class="result-empty">设置参数后计算实验方案</div>
      </div>
    </div>
  </section>
</template>
