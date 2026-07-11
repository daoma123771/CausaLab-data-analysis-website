# CausaLab 智能统计分析与样本量评估平台 V1.0

CausaLab 是一个面向 CSV/Excel 表格数据的统计分析向导平台。用户上传房价、工资、汽车油耗、问卷或实验记录等二维表格后，系统自动完成数据画像、字段类型识别、统计方法推荐、样本量与数据条件评估，并逐步输出统计检验、数学建模解释和可复核分析报告。

## 技术架构

- 前端：Vue 3 + TypeScript + Vite
- 后端：FastAPI + Python
- 统计计算：NumPy、SciPy、statsmodels、Pandas
- 图表展示：ECharts
- 报告导出：python-docx
- 测试：pytest，前端使用 TypeScript/Vite 构建校验

## 核心功能

1. 分析向导：上传 CSV/Excel 后生成连续统计分析路线。
2. 数据画像：识别字段类型、目标变量候选、分组变量、缺失、重复和异常值。
3. 方法推荐：根据数据结构推荐描述统计、相关分析、t 检验、ANOVA、比例检验或线性回归。
4. 样本量评估：判断当前数据是否满足目标分析要求，并提示可能的数据缺口。
5. 统计分析与建模：可直接运行描述统计、相关分析、Welch t 检验、ANOVA、两比例 z 检验和多元线性回归。
6. 报告导出：生成可复核的 Word 分析报告。

## 目录结构

```text
causalab/
├── backend/             FastAPI 接口与统计计算服务
├── frontend/            Vue 交互界面
├── docs/                设计说明、用户手册、测试用例和软著材料
├── examples/            示例数据与示例报告
├── scripts/             辅助脚本
└── README.md
```

## 启动方式

后端：

```powershell
cd F:\...\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

前端：

```powershell
cd F:\...\frontend
npm run dev
```

浏览器访问前端开发服务地址后，优先按“工作台 → 分析向导 → 上传演示数据 → 选择推荐路线 → 运行统计分析/建模”的路径演示。旧版的实验规划、数据诊断、效应评估页面仍保留为专项工具。

## 演示数据

可使用 [examples/housing_sample.csv](examples/housing_sample.csv) 演示新版分析向导。该文件是合成的房价风格数据，包含房价目标变量、收入、房间数、房龄、距中心距离和地区字段，适合演示数据画像、方法推荐、样本量判断、相关分析、ANOVA 和线性回归建模。

也可以使用 [examples/ab_test_sample.csv](examples/ab_test_sample.csv) 演示数据诊断模块。该文件有意包含缺失值、重复记录和异常值，便于展示质量评分、字段识别、异常检测和诊断建议。

示例报告位于 [examples/CausaLab_示例分析报告.docx](examples/CausaLab_示例分析报告.docx)。


