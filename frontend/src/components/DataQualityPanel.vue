<script setup lang="ts">
import { computed, ref } from "vue"

interface NumericSummary { minimum: number; maximum: number; mean: number; median: number; standard_deviation: number }
interface ColumnProfile {
  name: string; data_type: string; inferred_role: string; non_null_count: number
  missing_count: number; missing_percent: number; unique_count: number
  outlier_count: number | null; numeric_summary: NumericSummary | null
}
interface GroupCount { value: string; count: number; percent: number }
interface QualityResult {
  file_name: string; file_type: string; row_count: number; column_count: number
  quality_score: number; quality_level: string; duplicate_rows: number; duplicate_percent: number
  total_missing_cells: number; total_missing_percent: number; detected_group_column: string | null
  group_distribution: GroupCount[]; columns: ColumnProfile[]; preview: Record<string, unknown>[]
  warnings: string[]; recommendations: string[]
}

const selectedFile = ref<File | null>(null)
const result = ref<QualityResult | null>(null)
const loading = ref(false)
const errorMessage = ref("")
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const levelText = computed(() => ({ excellent: "优秀", good: "良好", warning: "需关注", poor: "较差" }[result.value?.quality_level || ""] || ""))
const scoreStyle = computed(() => ({ "--score": `${result.value?.quality_score || 0}%` }))
const previewColumns = computed(() => result.value ? Object.keys(result.value.preview[0] || {}) : [])
const roleText: Record<string, string> = { identifier: "标识符", group: "实验分组", metric: "数值指标", time: "时间", category: "分类", text: "文本" }

function chooseFile() { fileInput.value?.click() }
function handleInput(event: Event) {
  const files = (event.target as HTMLInputElement).files
  if (files?.[0]) acceptFile(files[0])
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
    errorMessage.value = "请选择 CSV 或 XLSX 文件"
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    errorMessage.value = "文件不能超过 10 MB"
    return
  }
  selectedFile.value = file
  inspectFile()
}

async function inspectFile() {
  if (!selectedFile.value) return
  loading.value = true
  errorMessage.value = ""
  result.value = null
  try {
    const form = new FormData()
    form.append("file", selectedFile.value)
    const response = await fetch("/api/data/inspect", { method: "POST", body: form })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || "文件诊断失败")
    result.value = data
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "文件诊断失败"
  } finally {
    loading.value = false
  }
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "—"
  return String(value)
}
</script>

<template>
  <section class="quality-view">
    <div class="planning-heading">
      <div><p class="eyebrow">DATA QUALITY</p><h1>实验数据质量诊断</h1><p class="lead">在计算效应之前先检查数据结构、缺失、重复、异常值与随机分组质量。</p></div>
      <span class="method-badge">CSV / XLSX · 本地分析</span>
    </div>

    <div v-if="!result" class="upload-stage">
      <div class="upload-card" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="handleDrop">
        <div class="upload-icon">↑</div>
        <h2>{{ loading ? "正在解析并诊断数据…" : "上传实验数据文件" }}</h2>
        <p>拖放文件到这里，或点击选择文件</p>
        <input ref="fileInput" type="file" accept=".csv,.xlsx" hidden @change="handleInput" />
        <button type="button" :disabled="loading" @click="chooseFile">{{ loading ? "诊断中" : "选择 CSV / XLSX" }}</button>
        <small>最大 10 MB · 示例文件位于 examples/ab_test_sample.csv</small>
      </div>
      <p v-if="errorMessage" class="form-error upload-error">{{ errorMessage }}</p>
      <div class="quality-capabilities">
        <article><strong>01</strong><span>结构识别</span><p>自动推断标识符、分组、指标和时间字段</p></article>
        <article><strong>02</strong><span>问题扫描</span><p>检测缺失、重复与 IQR 异常值</p></article>
        <article><strong>03</strong><span>实验检查</span><p>评估分组比例与潜在 SRM 风险</p></article>
      </div>
    </div>

    <div v-else class="quality-results">
      <div class="quality-toolbar">
        <div><small>当前文件</small><strong>{{ result.file_name }}</strong><span>{{ result.row_count.toLocaleString() }} 行 × {{ result.column_count }} 列</span></div>
        <button type="button" @click="chooseFile">更换文件</button>
        <input ref="fileInput" type="file" accept=".csv,.xlsx" hidden @change="handleInput" />
      </div>

      <div class="quality-summary">
        <article class="score-card">
          <div class="score-ring" :style="scoreStyle"><div><strong>{{ result.quality_score }}</strong><small>/ 100</small></div></div>
          <div><small>综合数据质量</small><h2>{{ levelText }}</h2><p>根据完整性、唯一性、异常值和分组平衡综合计算</p></div>
        </article>
        <article><small>缺失单元格</small><strong>{{ result.total_missing_cells }}</strong><span>{{ result.total_missing_percent.toFixed(2) }}%</span></article>
        <article><small>重复数据行</small><strong>{{ result.duplicate_rows }}</strong><span>{{ result.duplicate_percent.toFixed(2) }}%</span></article>
        <article><small>识别分组字段</small><strong class="column-name">{{ result.detected_group_column || "未识别" }}</strong><span>{{ result.group_distribution.length }} 个取值</span></article>
      </div>

      <div class="quality-grid">
        <section class="quality-section column-section">
          <div class="quality-title"><div><small>FIELD PROFILE</small><h2>字段画像</h2></div><span>{{ result.columns.length }} 个字段</span></div>
          <div class="column-table-wrap"><table class="column-table"><thead><tr><th>字段</th><th>角色</th><th>类型</th><th>唯一值</th><th>缺失</th><th>异常值</th></tr></thead><tbody><tr v-for="column in result.columns" :key="column.name"><td><strong>{{ column.name }}</strong></td><td><span class="role-tag" :class="column.inferred_role">{{ roleText[column.inferred_role] }}</span></td><td>{{ column.data_type }}</td><td>{{ column.unique_count }}</td><td :class="{ issue: column.missing_count > 0 }">{{ column.missing_count }} <small>({{ column.missing_percent }}%)</small></td><td>{{ column.outlier_count === null ? "—" : column.outlier_count }}</td></tr></tbody></table></div>
        </section>

        <aside class="quality-side">
          <section v-if="result.group_distribution.length" class="quality-section">
            <div class="quality-title"><div><small>ALLOCATION</small><h2>分组分布</h2></div></div>
            <div class="group-bars"><div v-for="group in result.group_distribution" :key="group.value"><div><strong>{{ group.value }}</strong><span>{{ group.count }} · {{ group.percent }}%</span></div><div class="bar-track"><i :style="{ width: `${group.percent}%` }"></i></div></div></div>
          </section>
          <section class="quality-section advice-section">
            <div class="quality-title"><div><small>DIAGNOSIS</small><h2>诊断建议</h2></div></div>
            <p v-for="warning in result.warnings" :key="warning" class="diagnosis warning">{{ warning }}</p>
            <p v-for="recommendation in result.recommendations" :key="recommendation" class="diagnosis recommendation">{{ recommendation }}</p>
          </section>
        </aside>
      </div>

      <section class="quality-section preview-section">
        <div class="quality-title"><div><small>DATA PREVIEW</small><h2>数据预览</h2></div><span>前 {{ result.preview.length }} 行</span></div>
        <div class="preview-table-wrap"><table class="preview-table"><thead><tr><th v-for="column in previewColumns" :key="column">{{ column }}</th></tr></thead><tbody><tr v-for="(row, index) in result.preview" :key="index"><td v-for="column in previewColumns" :key="column">{{ formatCell(row[column]) }}</td></tr></tbody></table></div>
      </section>
    </div>
  </section>
</template>
