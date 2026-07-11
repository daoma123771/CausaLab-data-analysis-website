<script setup lang="ts">
import { ref } from "vue"
import AnalysisPanel from "./components/AnalysisPanel.vue"
import DashboardPanel from "./components/DashboardPanel.vue"
import DataQualityPanel from "./components/DataQualityPanel.vue"
import PlanningPanel from "./components/PlanningPanel.vue"
import ReportPanel from "./components/ReportPanel.vue"
import WorkflowPanel from "./components/WorkflowPanel.vue"

type ViewName = "dashboard" | "workflow" | "planning" | "quality" | "analysis" | "report"
const activeView = ref<ViewName>("dashboard")
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">C</span>
        <div>
          <strong>CausaLab</strong>
          <small>智能统计分析平台</small>
        </div>
      </div>

      <nav>
        <button :class="{ active: activeView === 'dashboard' }" @click="activeView = 'dashboard'">工作台</button>
        <button :class="{ active: activeView === 'workflow' }" @click="activeView = 'workflow'">分析向导</button>
        <button :class="{ active: activeView === 'report' }" @click="activeView = 'report'">分析报告</button>
        <span class="nav-label">专项工具</span>
        <button class="secondary-nav" :class="{ active: activeView === 'planning' }" @click="activeView = 'planning'">样本量规划</button>
        <button class="secondary-nav" :class="{ active: activeView === 'quality' }" @click="activeView = 'quality'">数据诊断</button>
        <button class="secondary-nav" :class="{ active: activeView === 'analysis' }" @click="activeView = 'analysis'">A/B 效应评估</button>
      </nav>

      <div class="version">V1.0 · 本地分析</div>
    </aside>

    <main v-if="activeView === 'dashboard'">
      <DashboardPanel @navigate="activeView = $event" />
    </main>
    <main v-else-if="activeView === 'workflow'">
      <WorkflowPanel />
    </main>
    <main v-else-if="activeView === 'planning'">
      <PlanningPanel />
    </main>
    <main v-else-if="activeView === 'quality'">
      <DataQualityPanel />
    </main>
    <main v-else-if="activeView === 'analysis'">
      <AnalysisPanel />
    </main>
    <main v-else>
      <ReportPanel />
    </main>
  </div>
</template>
