<script setup lang="ts">
import { computed, ref } from "vue"

interface ReportHistory { name: string; metric: string; createdAt: string }

const projectName = ref("首页改版 A/B 实验")
const analyst = ref("数据分析员")
const metricName = ref("注册转化率")
const metricType = ref<"proportion" | "continuous">("proportion")
const method = ref("两比例 Z 检验 + 参数 Bootstrap")
const controlSize = ref(5000)
const treatmentSize = ref(5000)
const controlValue = ref(10)
const treatmentValue = ref(13)
const absoluteEffect = ref(3)
const relativeEffect = ref(30)
const pValue = ref(0.00001)
const ciLower = ref(1.7)
const ciUpper = ref(4.3)
const qualityScore = ref(88)
const decision = ref("拒绝原假设")
const conclusion = ref("实验组注册转化率显著高于对照组，可在业务价值与风险评估后考虑推广。")
const notesText = ref("统计显著不等同于业务收益，需要结合实施成本。\n建议持续监控上线后的长期指标与护栏指标。")
const loading = ref(false)
const errorMessage = ref("")
const history = ref<ReportHistory[]>(JSON.parse(localStorage.getItem("causalab-report-history") || "[]"))

const unit = computed(() => metricType.value === "proportion" ? "%" : "")

function switchMetric(type: "proportion" | "continuous") {
  metricType.value = type
  if (type === "proportion") {
    metricName.value = "注册转化率"; method.value = "两比例 Z 检验 + 参数 Bootstrap"
    controlValue.value = 10; treatmentValue.value = 13; absoluteEffect.value = 3
    relativeEffect.value = 30; ciLower.value = 1.7; ciUpper.value = 4.3
  } else {
    metricName.value = "平均订单金额"; method.value = "Welch t 检验 + 非参数 Bootstrap"
    controlValue.value = 126.5; treatmentValue.value = 134.8; absoluteEffect.value = 8.3
    relativeEffect.value = 6.56; ciLower.value = 3.1; ciUpper.value = 13.5
  }
}

async function exportReport() {
  loading.value = true
  errorMessage.value = ""
  try {
    const scale = metricType.value === "proportion" ? 0.01 : 1
    const response = await fetch("/api/reports/analysis.docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: projectName.value, analyst: analyst.value, metric_name: metricName.value,
        metric_type: metricType.value, method: method.value,
        control_size: controlSize.value, treatment_size: treatmentSize.value,
        control_value: controlValue.value * scale, treatment_value: treatmentValue.value * scale,
        absolute_effect: absoluteEffect.value * scale, relative_effect_percent: relativeEffect.value,
        p_value: pValue.value, alpha: 0.05, confidence_level: 0.95,
        ci_lower: ciLower.value * scale, ci_upper: ciUpper.value * scale,
        decision: decision.value, conclusion: conclusion.value, quality_score: qualityScore.value,
        notes: notesText.value.split("\n").map(item => item.trim()).filter(Boolean),
      }),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail?.[0]?.msg || data.detail || "报告生成失败")
    }
    const blob = await response.blob()
    const disposition = response.headers.get("Content-Disposition") || ""
    const match = disposition.match(/filename\*=UTF-8''([^;]+)/)
    const fileName = match ? decodeURIComponent(match[1]) : `${projectName.value}_分析报告.docx`
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url; link.download = fileName; link.click()
    URL.revokeObjectURL(url)
    history.value.unshift({ name: projectName.value, metric: metricName.value, createdAt: new Date().toLocaleString("zh-CN") })
    history.value = history.value.slice(0, 5)
    localStorage.setItem("causalab-report-history", JSON.stringify(history.value))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "报告生成失败"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="report-view">
    <div class="planning-heading">
      <div><p class="eyebrow">REPORT CENTER</p><h1>可复现分析报告</h1><p class="lead">将实验参数、统计结果和解释建议整理为结构化 Word 文档。</p></div>
      <span class="method-badge">DOCX · 自动排版</span>
    </div>
    <div class="report-layout">
      <form class="report-form" @submit.prevent="exportReport">
        <section class="report-card">
          <div class="panel-title"><div><small>STEP 01</small><h2>项目与指标</h2></div></div>
          <div class="metric-tabs"><button type="button" :class="{ active: metricType === 'proportion' }" @click="switchMetric('proportion')">比例指标</button><button type="button" :class="{ active: metricType === 'continuous' }" @click="switchMetric('continuous')">连续指标</button></div>
          <div class="report-fields"><label class="wide"><span>项目名称</span><input v-model="projectName" required maxlength="100" /></label><label><span>分析人员</span><input v-model="analyst" required /></label><label><span>核心指标</span><input v-model="metricName" required /></label><label class="wide"><span>统计方法</span><input v-model="method" required /></label></div>
        </section>
        <section class="report-card">
          <div class="panel-title"><div><small>STEP 02</small><h2>核心统计结果</h2></div></div>
          <div class="report-fields numeric-fields">
            <label><span>对照组样本量</span><input v-model.number="controlSize" type="number" min="2" required /></label><label><span>实验组样本量</span><input v-model.number="treatmentSize" type="number" min="2" required /></label>
            <label><span>对照组指标 {{ unit }}</span><input v-model.number="controlValue" type="number" step="0.001" required /></label><label><span>实验组指标 {{ unit }}</span><input v-model.number="treatmentValue" type="number" step="0.001" required /></label>
            <label><span>绝对效应 {{ unit }}</span><input v-model.number="absoluteEffect" type="number" step="0.001" required /></label><label><span>相对变化 %</span><input v-model.number="relativeEffect" type="number" step="0.01" required /></label>
            <label><span>p 值</span><input v-model.number="pValue" type="number" min="0" max="1" step="0.00001" required /></label><label><span>数据质量分</span><input v-model.number="qualityScore" type="number" min="0" max="100" required /></label>
            <label><span>区间下限 {{ unit }}</span><input v-model.number="ciLower" type="number" step="0.001" required /></label><label><span>区间上限 {{ unit }}</span><input v-model.number="ciUpper" type="number" step="0.001" required /></label>
          </div>
        </section>
        <section class="report-card">
          <div class="panel-title"><div><small>STEP 03</small><h2>结论与备注</h2></div></div>
          <div class="report-fields"><label class="wide"><span>统计决策</span><select v-model="decision"><option>拒绝原假设</option><option>暂不拒绝原假设</option><option>不支持预设方向</option></select></label><label class="wide"><span>结论</span><textarea v-model="conclusion" rows="3" required maxlength="500"></textarea></label><label class="wide"><span>风险备注（每行一条）</span><textarea v-model="notesText" rows="3"></textarea></label></div>
        </section>
        <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
        <button class="report-export" :disabled="loading">{{ loading ? "正在生成 Word…" : "生成并下载 Word 报告" }}</button>
      </form>
      <aside class="report-preview">
        <div class="document-sheet">
          <small>EXPERIMENT ANALYSIS REPORT</small><h2>{{ projectName || "未命名项目" }}</h2><p>A/B 实验效应评估报告</p>
          <div class="sheet-meta"><span>{{ analyst }}</span><span>{{ metricName }}</span></div>
          <h3>执行摘要</h3><div class="sheet-callout"><strong>{{ decision }}</strong><p>{{ conclusion }}</p></div>
          <h3>核心结果</h3><div class="sheet-metrics"><span><b>{{ controlValue }}{{ unit }}</b>对照组</span><span><b>{{ treatmentValue }}{{ unit }}</b>实验组</span><span><b>{{ absoluteEffect > 0 ? '+' : '' }}{{ absoluteEffect }}{{ unit }}</b>绝对效应</span></div>
          <div class="sheet-interval">95% CI [{{ ciLower }}{{ unit }}, {{ ciUpper }}{{ unit }}]</div>
          <h3>方法与判断规则</h3><i></i><i></i><i class="short"></i>
          <footer>CausaLab V1.0 自动生成</footer>
        </div>
        <div v-if="history.length" class="report-history"><div class="quality-title"><div><small>RECENT EXPORTS</small><h2>最近导出</h2></div></div><article v-for="item in history" :key="item.createdAt"><div><strong>{{ item.name }}</strong><span>{{ item.metric }}</span></div><small>{{ item.createdAt }}</small></article></div>
      </aside>
    </div>
  </section>
</template>
