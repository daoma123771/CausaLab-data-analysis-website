<script setup lang="ts">
type TargetView = "workflow" | "planning" | "quality" | "analysis" | "report"

defineEmits<{
  navigate: [view: TargetView]
}>()

const workflow = [
  {
    number: "01",
    title: "表格数据导入",
    text: "上传 CSV/Excel，系统自动识别字段类型、数据质量、目标变量候选和分组变量。",
    target: "workflow",
  },
  {
    number: "02",
    title: "分析路线推荐",
    text: "根据数据结构推荐描述统计、相关分析、t 检验、ANOVA、比例检验或线性回归。",
    target: "workflow",
  },
  {
    number: "03",
    title: "样本量与条件评估",
    text: "判断当前数据是否适合目标分析，提示样本量是否充足以及可能的数据缺口。",
    target: "workflow",
  },
  {
    number: "04",
    title: "统计结果与报告",
    text: "输出统计检验、建模解释、置信区间、风险提示，并生成可复核 Word 报告。",
    target: "report",
  },
] as const

const capabilityMap = [
  ["数据画像", "识别行列规模、字段类型、缺失、重复、异常值和目标变量候选"],
  ["方法推荐", "根据分析问题和字段结构推荐 t 检验、ANOVA、相关分析、回归等方法"],
  ["样本量判断", "结合目标功效、显著性水平和当前有效样本，判断数据是否满足分析要求"],
  ["统计建模", "支持从描述统计到线性回归的逐步扩展，适合房价、工资、油耗等表格数据"],
  ["结果归档", "生成包含数据概况、方法选择、样本量判断和统计结论的可复核报告"],
]

const principleMap = [
  ["统计功效", "在实验前评估样本量是否足以发现预设效应"],
  ["假设检验", "使用 p 值判断观察到的差异是否可能来自随机波动"],
  ["置信区间", "用区间表达效应估计的不确定性，而不是只给单点结果"],
  ["线性回归", "用多个解释变量刻画连续目标变量的变化规律"],
]
</script>

<template>
  <section class="dashboard-view">
    <header>
      <div>
        <p class="eyebrow">STATISTICAL ANALYSIS WIZARD</p>
        <h1>上传一份表格，获得一条清晰的统计分析路线</h1>
        <p class="lead">
          CausaLab 面向房价、工资、油耗、问卷和实验记录等表格数据，自动完成数据画像、方法推荐、样本量判断、统计检验与报告归档。
        </p>
      </div>
      <button @click="$emit('navigate', 'workflow')">上传数据开始分析</button>
    </header>

    <section class="summary-grid dashboard-summary">
      <article class="hero-card dashboard-hero" @click="$emit('navigate', 'workflow')">
        <div>
          <span class="label">推荐操作路径</span>
          <h2>导入 → 画像 → 推荐 → 检验 → 报告</h2>
          <p>
            用户不需要先知道该选哪种统计方法。系统会先理解表格结构，再把数据能回答的问题、适合的方法和样本量条件讲清楚。
          </p>
        </div>
        <div class="metric">
          <span>当前版本</span>
          <strong>分析向导 · 本地可复现统计</strong>
        </div>
      </article>

      <article class="status-card">
        <span class="status-dot"></span>
        <div>
          <small>系统状态</small>
          <strong>核心流程已打通</strong>
        </div>
      </article>
    </section>

    <section class="modules">
      <div class="section-title">
        <div>
          <p class="eyebrow">PRODUCT WORKFLOW</p>
          <h2>围绕一份数据完成连续统计分析</h2>
        </div>
        <span>点击卡片进入模块</span>
      </div>

      <div class="module-grid workflow-grid">
        <article v-for="item in workflow" :key="item.number" class="module-card workflow-card" @click="$emit('navigate', item.target)">
          <div class="module-top">
            <span>{{ item.number }}</span>
            <small class="building">可用</small>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.text }}</p>
        </article>
      </div>
    </section>

    <section class="dashboard-lower">
      <article class="requirement-card">
        <div class="section-title compact">
          <div>
            <p class="eyebrow">CAPABILITY MAP</p>
            <h2>平台能力与输出</h2>
          </div>
        </div>
        <div class="mapping-table">
          <div v-for="row in capabilityMap" :key="row[0]">
            <strong>{{ row[0] }}</strong>
            <span>{{ row[1] }}</span>
          </div>
        </div>
      </article>

      <article class="principle-card">
        <span>STATISTICAL BASIS</span>
        <h2>数据分析向导</h2>
        <p>
          平台把数据画像、方法推荐、样本量评估、假设检验和数学建模组织到同一条流程中，
          让用户既能看到分析结果，也能理解结果背后的统计含义。
        </p>
        <ul>
          <li v-for="item in principleMap" :key="item[0]">
            <strong>{{ item[0] }}</strong>
            <span>{{ item[1] }}</span>
          </li>
        </ul>
        <button @click="$emit('navigate', 'workflow')">进入分析向导</button>
      </article>
    </section>
  </section>
</template>
